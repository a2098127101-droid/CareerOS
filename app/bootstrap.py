from __future__ import annotations

import os

from .config import Settings
from .model_store import ModelConfigStore
from .models import ProviderUpsert, RouteUpsert

TASKS = ["profile", "coach", "writer", "reviewer", "critic", "revision"]


def bootstrap_model_config(store: ModelConfigStore, settings: Settings) -> None:
    """Import provider credentials from environment on first run without overwriting admin config."""
    existing_ids = {p["provider_id"] for p in store.list_providers()}

    candidates: list[ProviderUpsert] = []
    if settings.openai_api_key and "openai" not in existing_ids:
        candidates.append(ProviderUpsert(
            provider_id="openai",
            name="OpenAI",
            kind="openai_responses",
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            api_key=settings.openai_api_key,
            default_model=settings.openai_model,
        ))
    if os.getenv("DEEPSEEK_API_KEY") and "deepseek" not in existing_ids:
        candidates.append(ProviderUpsert(
            provider_id="deepseek",
            name="DeepSeek",
            kind="openai_compatible",
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            default_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        ))
    if os.getenv("ANTHROPIC_API_KEY") and "anthropic" not in existing_ids:
        candidates.append(ProviderUpsert(
            provider_id="anthropic",
            name="Anthropic Claude",
            kind="anthropic",
            base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            default_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
        ))
    if os.getenv("GEMINI_API_KEY") and "gemini" not in existing_ids:
        candidates.append(ProviderUpsert(
            provider_id="gemini",
            name="Google Gemini",
            kind="gemini",
            base_url=os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"),
            api_key=os.getenv("GEMINI_API_KEY"),
            default_model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        ))
    custom_key = os.getenv("CUSTOM_LLM_API_KEY")
    if custom_key and "custom" not in existing_ids:
        candidates.append(ProviderUpsert(
            provider_id="custom",
            name=os.getenv("CUSTOM_LLM_NAME", "Custom OpenAI-compatible"),
            kind="openai_compatible",
            base_url=os.getenv("CUSTOM_LLM_BASE_URL", "http://127.0.0.1:8001/v1"),
            api_key=custom_key,
            default_model=os.getenv("CUSTOM_LLM_MODEL", "default"),
        ))

    for provider in candidates:
        store.upsert_provider(provider)

    if store.list_routes():
        return
    providers = [p for p in store.list_providers() if p["enabled"] and p["has_api_key"]]
    if not providers:
        return
    preferred = os.getenv("DEFAULT_LLM_PROVIDER", "").strip()
    primary = next((p for p in providers if p["provider_id"] == preferred), providers[0])
    fallback = next((p for p in providers if p["provider_id"] != primary["provider_id"]), None)
    for task in TASKS:
        store.upsert_route(RouteUpsert(
            task=task,
            provider_id=primary["provider_id"],
            model=primary["default_model"],
            fallback_provider_id=fallback["provider_id"] if fallback else None,
            fallback_model=fallback["default_model"] if fallback else None,
            temperature=0.1 if task in {"profile", "reviewer"} else 0.3,
            max_tokens=6000 if task in {"writer", "revision"} else 3500,
        ))
