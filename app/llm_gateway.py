from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from .model_store import ModelConfigStore, ProviderRecord
from .commercial_store import CommercialStore
from .privacy import minimize_for_model

T = TypeVar("T", bound=BaseModel)


TASK_CAPABILITY_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "profile": {"required_capabilities": ["json_schema"], "min_context_window": 16000},
    "coach": {"required_capabilities": ["streaming"], "min_context_window": 16000},
    "writer": {"required_capabilities": [], "min_context_window": 32000},
    "reviewer": {"required_capabilities": ["json_schema"], "min_context_window": 32000},
    "critic": {"required_capabilities": [], "min_context_window": 32000},
    "revision": {"required_capabilities": [], "min_context_window": 32000},
}


class LLMGatewayError(RuntimeError):
    pass


@dataclass
class LLMResult:
    text: str
    provider_id: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0


class LLMGateway:
    def __init__(
        self,
        store: ModelConfigStore,
        commercial_store: CommercialStore | None = None,
        *,
        retry_attempts: int = 2,
        retry_backoff_seconds: float = 0.8,
        circuit_failure_threshold: int = 5,
        circuit_cooldown_seconds: int = 60,
        pii_redaction_enabled: bool = False,
    ):
        self.store = store
        self.commercial_store = commercial_store
        self.retry_attempts = max(1, int(retry_attempts))
        self.retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))
        self.circuit_failure_threshold = max(1, int(circuit_failure_threshold))
        self.circuit_cooldown_seconds = max(5, int(circuit_cooldown_seconds))
        self.pii_redaction_enabled = bool(pii_redaction_enabled)
        self._circuit: dict[str, dict[str, float | int]] = {}

    def _circuit_open(self, provider_id: str) -> bool:
        state = self._circuit.get(provider_id) or {}
        opened_at = float(state.get("opened_at") or 0)
        if not opened_at:
            return False
        if time.time() - opened_at >= self.circuit_cooldown_seconds:
            self._circuit.pop(provider_id, None)
            return False
        return True

    def _record_provider_failure(self, provider_id: str) -> None:
        state = self._circuit.setdefault(provider_id, {"failures": 0, "opened_at": 0})
        state["failures"] = int(state.get("failures") or 0) + 1
        if int(state["failures"]) >= self.circuit_failure_threshold:
            state["opened_at"] = time.time()

    def _record_provider_success(self, provider_id: str) -> None:
        self._circuit.pop(provider_id, None)

    @property
    def enabled(self) -> bool:
        for route in self.store.list_routes():
            if str(route.get("provider_id", "")).lower() == "auto" or str(route.get("model", "")).lower() == "auto":
                if self.recommend_models_for_task(str(route.get("task") or "")):
                    return True
                continue
            provider = self.store.get_provider(route["provider_id"])
            if provider and provider.enabled and provider.api_key:
                return True
        return False

    def recommend_models_for_task(self, task: str, *, required_capabilities: list[str] | None = None) -> list[dict[str, Any]]:
        defaults = TASK_CAPABILITY_REQUIREMENTS.get(task, {})
        required = list(required_capabilities if required_capabilities is not None else defaults.get("required_capabilities", []))
        return self.store.recommend_models(required_capabilities=required, min_context_window=int(defaults.get("min_context_window", 0)))

    def _route_attempts(self, task: str, route) -> list[tuple[str, str]]:
        if str(route.provider_id).lower() == "auto" or str(route.model).lower() == "auto":
            candidates = self.recommend_models_for_task(task)
            if str(route.provider_id).lower() != "auto":
                candidates = [c for c in candidates if c.get("provider_id") == route.provider_id]
            attempts = [(str(c["provider_id"]), str(c["model"])) for c in candidates[:3]]
            if attempts:
                return attempts
        attempts = [(route.provider_id, route.model)]
        if route.fallback_provider_id and route.fallback_model:
            attempts.append((route.fallback_provider_id, route.fallback_model))
        return attempts

    async def complete(self, task: str, system: str, user: str, *, tenant_id: str = "global") -> LLMResult:
        route = self.store.get_route(task)
        if not route:
            raise LLMGatewayError(f"Agent task '{task}' 尚未配置模型路由")
        if self.commercial_store is not None:
            allowed, reason = self.commercial_store.check_ai_quota(tenant_id)
            if not allowed:
                raise LLMGatewayError(reason)
        user, _redactions = minimize_for_model(user, enabled=self.pii_redaction_enabled)

        attempts = self._route_attempts(task, route)

        last_error = ""
        for provider_id, model in attempts:
            provider = self.store.get_provider(provider_id)
            if not provider or not provider.enabled:
                last_error = f"provider {provider_id} 不存在或已禁用"
                continue
            if not provider.api_key:
                last_error = f"provider {provider_id} 未配置 API Key"
                continue
            if self._circuit_open(provider_id):
                last_error = f"provider {provider_id} circuit open; fallback activated"
                continue

            for retry_index in range(self.retry_attempts):
                started = time.perf_counter()
                try:
                    text, usage = await self._call_provider(
                        provider,
                        model=model,
                        system=system,
                        user=user,
                        temperature=route.temperature,
                        max_tokens=route.max_tokens,
                    )
                    latency = int((time.perf_counter() - started) * 1000)
                    result = LLMResult(
                        text=text, provider_id=provider_id, model=model,
                        input_tokens=usage.get("input_tokens", 0), output_tokens=usage.get("output_tokens", 0),
                        total_tokens=usage.get("total_tokens", 0), latency_ms=latency,
                    )
                    self._record_provider_success(provider_id)
                    self.store.record_usage(
                        task=task, provider_id=provider_id, model=model,
                        input_tokens=result.input_tokens, output_tokens=result.output_tokens, total_tokens=result.total_tokens,
                        latency_ms=latency, success=True, tenant_id=tenant_id,
                    )
                    return result
                except Exception as exc:
                    latency = int((time.perf_counter() - started) * 1000)
                    last_error = str(exc)
                    retryable = any(code in last_error for code in ("HTTP 408", "HTTP 409", "HTTP 429", "HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504", "timeout", "Timeout"))
                    if retryable and retry_index + 1 < self.retry_attempts:
                        await asyncio.sleep(self.retry_backoff_seconds * (2 ** retry_index))
                        continue
                    self._record_provider_failure(provider_id)
                    self.store.record_usage(
                        task=task, provider_id=provider_id, model=model, latency_ms=latency, success=False,
                        error=last_error, tenant_id=tenant_id,
                    )
                    break
        raise LLMGatewayError(last_error or "所有模型路由均调用失败")

    async def stream_complete(self, task: str, system: str, user: str, *, tenant_id: str = "global"):
        """Yield model text chunks. Native OpenAI-compatible streaming is used when declared; otherwise truthfully falls back to buffered completion."""
        route = self.store.get_route(task)
        if not route:
            raise LLMGatewayError(f"Agent task '{task}' 尚未配置模型路由")
        user, _redactions = minimize_for_model(user, enabled=self.pii_redaction_enabled)
        attempts = self._route_attempts(task, route)
        if not attempts:
            raise LLMGatewayError("no compatible model candidate")
        provider_id, model = attempts[0]
        provider = self.store.get_provider(provider_id)
        capability = self.store.get_model_capability(provider_id, model) or {}
        if provider and provider.enabled and provider.api_key and provider.kind == "openai_compatible" and capability.get("supports_streaming"):
            started = time.perf_counter()
            chunks: list[str] = []
            try:
                timeout = httpx.Timeout(provider.timeout_seconds)
                headers = dict(provider.extra_headers)
                headers.update({"Authorization": f"Bearer {provider.api_key}", "Content-Type": "application/json"})
                body = {"model": model, "messages": [{"role": "system", "content": system},{"role": "user", "content": user}], "temperature": route.temperature, "max_tokens": route.max_tokens, "stream": True}
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream("POST", provider.base_url.rstrip("/") + "/chat/completions", headers=headers, json=body) as response:
                        if not response.is_success:
                            raw = (await response.aread()).decode("utf-8", errors="ignore")[:3000]
                            raise LLMGatewayError(f"HTTP {response.status_code}: {raw}")
                        async for line in response.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            payload=line[5:].strip()
                            if not payload or payload == "[DONE]":
                                continue
                            try:
                                data=json.loads(payload)
                                delta=data.get("choices",[{}])[0].get("delta",{}).get("content") or ""
                            except Exception:
                                delta=""
                            if delta:
                                chunks.append(delta)
                                yield {"type":"delta","text":delta,"provider_id":provider_id,"model":model,"native":True}
                latency=int((time.perf_counter()-started)*1000)
                self.store.record_usage(task=task,provider_id=provider_id,model=model,latency_ms=latency,success=True,tenant_id=tenant_id)
                yield {"type":"done","text":"".join(chunks),"provider_id":provider_id,"model":model,"native":True,"latency_ms":latency}
                return
            except Exception as exc:
                self.store.record_usage(task=task,provider_id=provider_id,model=model,latency_ms=int((time.perf_counter()-started)*1000),success=False,error=str(exc),tenant_id=tenant_id)
                # fall through to buffered compatibility path
        result = await self.complete(task, system, user, tenant_id=tenant_id)
        text=result.text
        step=96
        for i in range(0,len(text),step):
            yield {"type":"delta","text":text[i:i+step],"provider_id":result.provider_id,"model":result.model,"native":False}
        yield {"type":"done","text":text,"provider_id":result.provider_id,"model":result.model,"native":False,"latency_ms":result.latency_ms}

    async def complete_json(self, task: str, system: str, user: str, schema: type[T], *, tenant_id: str = "global") -> tuple[T, LLMResult]:
        json_system = system + "\n\n只输出严格 JSON，不要 Markdown 代码块，不要附加解释。"
        result = await self.complete(task, json_system, user, tenant_id=tenant_id)
        payload = self._extract_json(result.text)
        return schema.model_validate(payload), result

    async def test_provider(self, provider_id: str, model: str | None = None) -> dict[str, Any]:
        provider = self.store.get_provider(provider_id)
        if not provider:
            raise LLMGatewayError("provider not found")
        started = time.perf_counter()
        text, usage = await self._call_provider(
            provider,
            model=model or provider.default_model,
            system="You are a connectivity test. Reply with exactly: OK",
            user="ping",
            temperature=0,
            max_tokens=16,
        )
        return {
            "ok": True,
            "provider_id": provider_id,
            "model": model or provider.default_model,
            "reply": text[:200],
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "usage": usage,
        }

    async def _call_provider(
        self,
        provider: ProviderRecord,
        *,
        model: str,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
    ) -> tuple[str, dict[str, int]]:
        timeout = httpx.Timeout(provider.timeout_seconds)
        headers = dict(provider.extra_headers)
        async with httpx.AsyncClient(timeout=timeout) as client:
            if provider.kind == "openai_compatible":
                url = provider.base_url.rstrip("/") + "/chat/completions"
                headers.update({"Authorization": f"Bearer {provider.api_key}", "Content-Type": "application/json"})
                body = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                r = await client.post(url, headers=headers, json=body)
                self._raise_for_status(r)
                data = r.json()
                text = data["choices"][0]["message"].get("content") or ""
                u = data.get("usage") or {}
                return text, {
                    "input_tokens": int(u.get("prompt_tokens") or 0),
                    "output_tokens": int(u.get("completion_tokens") or 0),
                    "total_tokens": int(u.get("total_tokens") or 0),
                }

            if provider.kind == "openai_responses":
                url = provider.base_url.rstrip("/") + "/responses"
                headers.update({"Authorization": f"Bearer {provider.api_key}", "Content-Type": "application/json"})
                body = {
                    "model": model,
                    "instructions": system,
                    "input": user,
                    "max_output_tokens": max_tokens,
                }
                r = await client.post(url, headers=headers, json=body)
                self._raise_for_status(r)
                data = r.json()
                text = data.get("output_text") or self._extract_openai_response_text(data)
                u = data.get("usage") or {}
                return text, {
                    "input_tokens": int(u.get("input_tokens") or 0),
                    "output_tokens": int(u.get("output_tokens") or 0),
                    "total_tokens": int(u.get("total_tokens") or 0),
                }

            if provider.kind == "anthropic":
                url = provider.base_url.rstrip("/") + "/v1/messages"
                headers.update({
                    "x-api-key": provider.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                })
                body = {
                    "model": model,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                r = await client.post(url, headers=headers, json=body)
                self._raise_for_status(r)
                data = r.json()
                text = "\n".join(x.get("text", "") for x in data.get("content", []) if x.get("type") == "text")
                u = data.get("usage") or {}
                inp = int(u.get("input_tokens") or 0)
                out = int(u.get("output_tokens") or 0)
                return text, {"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out}

            if provider.kind == "gemini":
                # Gemini Interactions API (current primary text-generation API).
                url = provider.base_url.rstrip("/") + "/interactions"
                headers.update({"Content-Type": "application/json", "x-goog-api-key": provider.api_key})
                body = {
                    "model": model,
                    "input": user,
                    "system_instruction": system,
                    "generation_config": {"temperature": temperature},
                }
                r = await client.post(url, headers=headers, json=body)
                self._raise_for_status(r)
                data = r.json()
                text = str(data.get("output_text") or "")
                if not text:
                    # REST responses expose model steps; extract the last text blocks defensively.
                    texts: list[str] = []
                    for step in data.get("steps", []) or []:
                        content = step.get("content") if isinstance(step, dict) else None
                        if isinstance(content, str):
                            texts.append(content)
                        elif isinstance(content, list):
                            for part in content:
                                if isinstance(part, dict) and part.get("text"):
                                    texts.append(str(part["text"]))
                    text = "\n".join(texts[-3:])
                u = data.get("usage") or data.get("usage_metadata") or data.get("usageMetadata") or {}
                inp = int(u.get("input_tokens") or u.get("promptTokenCount") or 0)
                out = int(u.get("output_tokens") or u.get("candidatesTokenCount") or 0)
                total = int(u.get("total_tokens") or u.get("totalTokenCount") or (inp + out))
                return text, {"input_tokens": inp, "output_tokens": out, "total_tokens": total}

        raise LLMGatewayError(f"不支持的 provider kind: {provider.kind}")

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        body = response.text[:3000]
        raise LLMGatewayError(f"HTTP {response.status_code}: {body}")

    @staticmethod
    def _extract_openai_response_text(data: dict[str, Any]) -> str:
        texts: list[str] = []
        for item in data.get("output", []) or []:
            for content in item.get("content", []) or []:
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    texts.append(str(content["text"]))
        return "\n".join(texts)

    @staticmethod
    def _extract_json(text: str) -> Any:
        raw = text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
        raw = re.sub(r"\s*```$", "", raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                return json.loads(raw[start:end + 1])
            raise LLMGatewayError("模型未返回可解析 JSON")
