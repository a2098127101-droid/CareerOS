from pathlib import Path

from app.model_store import ModelConfigStore
from app.models import ProviderUpsert, RouteUpsert


def test_provider_secret_is_masked_and_roundtrips(tmp_path: Path):
    store = ModelConfigStore(str(tmp_path / "m.db"), "a-real-test-secret")
    store.upsert_provider(ProviderUpsert(
        provider_id="deepseek",
        name="DeepSeek",
        kind="openai_compatible",
        base_url="https://api.deepseek.com",
        api_key="sk-1234567890abcdef",
        default_model="deepseek-chat",
    ))
    public = store.list_providers()[0]
    assert public["api_key"] is None
    assert public["has_api_key"] is True
    assert "1234567890abcdef" not in public["api_key_masked"]
    internal = store.get_provider("deepseek")
    assert internal is not None
    assert internal.api_key == "sk-1234567890abcdef"


def test_routes_can_assign_different_models(tmp_path: Path):
    store = ModelConfigStore(str(tmp_path / "m.db"), "secret")
    store.upsert_provider(ProviderUpsert(
        provider_id="p1", name="P1", kind="openai_compatible", base_url="https://example.com/v1",
        api_key="key-1111111111", default_model="m1"
    ))
    store.upsert_provider(ProviderUpsert(
        provider_id="p2", name="P2", kind="anthropic", base_url="https://api.anthropic.com",
        api_key="key-2222222222", default_model="m2"
    ))
    store.upsert_route(RouteUpsert(
        task="writer", provider_id="p1", model="m1-large",
        fallback_provider_id="p2", fallback_model="m2", temperature=0.3, max_tokens=6000
    ))
    route = store.get_route("writer")
    assert route is not None
    assert route.provider_id == "p1"
    assert route.fallback_provider_id == "p2"
    assert route.max_tokens == 6000
