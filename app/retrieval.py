from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass
from typing import Iterable

import httpx

from .network_security import validate_outbound_url


def _tokenize(text: str) -> list[str]:
    value = (text or "").lower()
    terms = re.findall(r"[a-z0-9_+-]{2,}", value)
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", value):
        if len(run) <= 8:
            terms.append(run)
        terms.extend(run[index:index + 2] for index in range(len(run) - 1))
    return [term for term in terms if term.strip()][:5000]


def retrieval_terms(text: str) -> list[str]:
    return list(dict.fromkeys(_tokenize(text)))[:80]


def bm25_scores(
    query: str,
    documents: Iterable[str],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    """Compute normalized Okapi BM25 scores for a bounded candidate corpus."""
    docs = [_tokenize(document) for document in documents]
    query_tokens = retrieval_terms(query)
    if not docs or not query_tokens:
        return [0.0] * len(docs)
    average_length = sum(len(document) for document in docs) / max(1, len(docs))
    document_frequency: dict[str, int] = {}
    for term in query_tokens:
        document_frequency[term] = sum(1 for document in docs if term in document)
    raw: list[float] = []
    corpus_size = len(docs)
    for document in docs:
        frequencies: dict[str, int] = {}
        for token in document:
            frequencies[token] = frequencies.get(token, 0) + 1
        score = 0.0
        length_normalizer = 1.0 - b + b * len(document) / max(average_length, 1.0)
        for term in query_tokens:
            frequency = frequencies.get(term, 0)
            if not frequency:
                continue
            frequency_docs = document_frequency.get(term, 0)
            inverse_frequency = math.log(
                1.0 + (corpus_size - frequency_docs + 0.5) / (frequency_docs + 0.5)
            )
            score += inverse_frequency * (
                frequency * (k1 + 1.0)
                / (frequency + k1 * length_normalizer)
            )
        raw.append(score)
    maximum = max(raw, default=0.0)
    return [score / maximum if maximum > 0 else 0.0 for score in raw]


@dataclass(frozen=True)
class RerankerConfig:
    provider: str = "disabled"
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout_seconds: int = 30
    max_retries: int = 2
    retry_backoff_seconds: float = 0.5


@dataclass
class RerankerResult:
    scores: list[float]
    provider: str
    model: str
    active: bool
    warning: str = ""


class RerankerGateway:
    """Pluggable HTTP reranker with explicit no-op fallback.

    Supported provider contracts use the common ``query/documents/results``
    schema exposed by Cohere, Jina, Voyage, and compatible private gateways.
    """

    REMOTE_PROVIDERS = {"cohere", "jina", "voyage", "compatible"}
    DEFAULT_PATHS = {
        "cohere": "/v2/rerank",
        "jina": "/v1/rerank",
        "voyage": "/v1/rerank",
        "compatible": "/v1/rerank",
    }

    def __init__(self, config: RerankerConfig | None = None):
        self.config = config or RerankerConfig()

    @property
    def enabled(self) -> bool:
        return (
            self.config.provider in self.REMOTE_PROVIDERS
            and bool(self.config.base_url and self.config.api_key and self.config.model)
        )

    def _url(self) -> str:
        base = self.config.base_url.rstrip("/")
        suffix = self.DEFAULT_PATHS.get(self.config.provider, "/v1/rerank")
        if base.endswith("/rerank"):
            return validate_outbound_url(base)
        return validate_outbound_url(base + suffix)

    def rerank(self, query: str, documents: list[str], *, top_n: int) -> RerankerResult:
        if not documents:
            return RerankerResult([], self.config.provider, self.config.model, False)
        if not self.enabled:
            return RerankerResult(
                [0.0] * len(documents),
                self.config.provider or "disabled",
                self.config.model,
                False,
                "remote reranker is not configured",
            )
        payload = {
            "model": self.config.model,
            "query": query,
            "documents": documents,
            "top_n": min(max(1, int(top_n)), len(documents)),
        }
        last_error = ""
        for attempt in range(max(0, self.config.max_retries) + 1):
            try:
                with httpx.Client(timeout=self.config.timeout_seconds) as client:
                    response = client.post(
                        self._url(),
                        headers={
                            "Authorization": f"Bearer {self.config.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                if response.status_code in {408, 429, 500, 502, 503, 504}:
                    if attempt < self.config.max_retries:
                        last_error = f"Reranker HTTP {response.status_code}"
                        time.sleep(self.config.retry_backoff_seconds * (2**attempt))
                        continue
                response.raise_for_status()
                data = response.json()
                results = data.get("results") or data.get("data") or []
                scores = [0.0] * len(documents)
                for item in results:
                    index = int(item.get("index", -1))
                    score = item.get("relevance_score", item.get("score", 0.0))
                    if 0 <= index < len(scores):
                        scores[index] = max(0.0, min(1.0, float(score)))
                return RerankerResult(
                    scores,
                    self.config.provider,
                    self.config.model,
                    True,
                )
            except Exception as exc:
                last_error = str(exc)
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_backoff_seconds * (2**attempt))
                    continue
        return RerankerResult(
            [0.0] * len(documents),
            self.config.provider,
            self.config.model,
            False,
            f"remote reranker unavailable: {last_error}",
        )
