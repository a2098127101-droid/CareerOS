from __future__ import annotations

import hashlib
import math
import re
import time
from dataclasses import dataclass
from typing import Iterable

import httpx


class EmbeddingGatewayError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: str = "local_hash"
    base_url: str = ""
    api_key: str = ""
    model: str = "local-hash-v1"
    dimensions: int = 256
    timeout_seconds: int = 60
    max_batch_size: int = 64
    max_retries: int = 2
    retry_backoff_seconds: float = 0.5


@dataclass
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    provider: str
    dimensions: int = 0
    warning: str = ""


def local_hash_embedding(text: str, dims: int = 256) -> list[float]:
    """Deterministic offline fallback. This is not a semantic embedding model."""
    value = (text or "").lower()
    features = re.findall(r"[a-z0-9_+-]{2,}", value)
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", value):
        features.extend(run[i:i + 2] for i in range(len(run) - 1))
        if len(run) <= 8:
            features.append(run)
    vec = [0.0] * max(32, int(dims))
    for feature in features[:5000]:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], "big") % len(vec)
        sign = -1.0 if digest[4] & 1 else 1.0
        vec[idx] += sign * (1.0 + min(len(feature), 8) / 8.0)
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [round(x / norm, 8) for x in vec]


class EmbeddingGateway:
    """Pluggable embeddings with explicit, truthful local fallback.

    Providers currently share an OpenAI-compatible HTTP contract:
    - local_hash: deterministic offline fallback, never advertised as semantic
    - openai_compatible
    - bge_compatible
    - jina_compatible
    - private_api

    Provider-specific adapters can be introduced later without changing the retrieval contract.
    """

    REMOTE_PROVIDERS = {"openai_compatible", "bge_compatible", "jina_compatible", "private_api"}

    def __init__(self, config: EmbeddingConfig):
        self.config = config

    @property
    def semantic_enabled(self) -> bool:
        return self.config.provider in self.REMOTE_PROVIDERS and bool(
            self.config.api_key and self.config.base_url and self.config.model
        )

    @property
    def model_name(self) -> str:
        return self.config.model if self.semantic_enabled else "local-hash-v1"

    def _local(self, items: list[str], warning: str = "") -> EmbeddingResult:
        vectors = [local_hash_embedding(x, self.config.dimensions) for x in items]
        return EmbeddingResult(
            vectors=vectors,
            model="local-hash-v1",
            provider="local_hash",
            dimensions=len(vectors[0]) if vectors else max(32, int(self.config.dimensions)),
            warning=warning,
        )

    def _embed_batch(self, items: list[str]) -> EmbeddingResult:
        url = self.config.base_url.rstrip("/") + "/embeddings"
        headers = {"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"}
        payload: dict = {"model": self.config.model, "input": items}
        if self.config.dimensions > 0:
            payload["dimensions"] = self.config.dimensions
        last_error = ""
        for attempt in range(max(0, self.config.max_retries) + 1):
            try:
                with httpx.Client(timeout=self.config.timeout_seconds) as client:
                    response = client.post(url, headers=headers, json=payload)
                if response.status_code in {408, 429, 500, 502, 503, 504} and attempt < self.config.max_retries:
                    last_error = f"Embedding HTTP {response.status_code}: {response.text[:800]}"
                    time.sleep(self.config.retry_backoff_seconds * (2 ** attempt))
                    continue
                if not response.is_success:
                    raise EmbeddingGatewayError(f"Embedding HTTP {response.status_code}: {response.text[:1200]}")
                data = response.json()
                vectors = [
                    list(map(float, row["embedding"]))
                    for row in sorted(data.get("data", []), key=lambda x: int(x.get("index", 0)))
                ]
                if len(vectors) != len(items):
                    raise EmbeddingGatewayError("Embedding response count mismatch")
                dims = len(vectors[0]) if vectors else 0
                if vectors and any(len(v) != dims for v in vectors):
                    raise EmbeddingGatewayError("Embedding response dimension mismatch")
                return EmbeddingResult(
                    vectors=vectors,
                    model=self.config.model,
                    provider=self.config.provider,
                    dimensions=dims,
                )
            except Exception as exc:
                last_error = str(exc) if isinstance(exc, EmbeddingGatewayError) else f"Embedding request failed: {exc}"
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_backoff_seconds * (2 ** attempt))
                    continue
                return self._local(items, warning=last_error)
        return self._local(items, warning=last_error or "Embedding provider unavailable")

    def embed(self, texts: Iterable[str]) -> EmbeddingResult:
        items = [str(x or "") for x in texts]
        if not items:
            return EmbeddingResult(vectors=[], model=self.model_name, provider=self.config.provider, dimensions=0)
        if not self.semantic_enabled:
            return self._local(items)

        batch_size = max(1, int(self.config.max_batch_size or 64))
        all_vectors: list[list[float]] = []
        warning = ""
        provider = self.config.provider
        model = self.config.model
        dims = 0
        for start in range(0, len(items), batch_size):
            result = self._embed_batch(items[start:start + batch_size])
            all_vectors.extend(result.vectors)
            if result.warning:
                warning = result.warning
            # A failed remote batch explicitly falls back. Do not claim a semantic model for mixed output.
            if result.provider == "local_hash":
                provider = "local_hash"
                model = "local-hash-v1"
            dims = result.dimensions or dims
        return EmbeddingResult(vectors=all_vectors, model=model, provider=provider, dimensions=dims, warning=warning)
