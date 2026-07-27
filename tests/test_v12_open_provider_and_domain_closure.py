from pathlib import Path

from app.model_store import ModelConfigStore
from app.models import ProviderUpsert
from app.llm_gateway import LLMGateway


def test_custom_rest_provider_config_roundtrips_without_leaking_secret(tmp_path: Path):
    store = ModelConfigStore(str(tmp_path / 'm.db'), 'secret-for-v12')
    store.upsert_provider(ProviderUpsert(
        provider_id='internal-ai',
        name='Internal AI Gateway',
        kind='custom_rest',
        base_url='https://ai.example.test',
        api_key='super-secret-token',
        default_model='company-model',
        auth_type='api_key_header',
        auth_header_name='X-Company-Key',
        chat_path='/generate',
        models_path='/models',
        request_template={'model': '{{model}}', 'prompt': '{{user}}'},
        response_path='result.text',
        query_params={'api-version': '2026-07'},
        extra_headers={'X-Client': 'CareerOS', 'Authorization-Proxy': 'should-not-leak'},
    ))
    public = store.list_providers()[0]
    assert public['kind'] == 'custom_rest'
    assert public['api_key'] is None
    assert public['config']['chat_path'] == '/generate'
    assert public['config']['response_path'] == 'result.text'
    assert public['config']['request_template']['prompt'] == '{{user}}'
    assert public['extra_headers']['X-Client'] == 'CareerOS'
    assert public['extra_headers']['Authorization-Proxy'] == '••••'
    internal = store.get_provider('internal-ai')
    assert internal is not None
    assert internal.api_key == 'super-secret-token'
    assert internal.config['auth_type'] == 'api_key_header'
    assert '__careeros_provider_config__' not in internal.extra_headers


def test_custom_rest_template_and_response_mapping_helpers():
    rendered = LLMGateway._render_template(
        {'model': '{{model}}', 'payload': '{{messages}}', 'prompt': 'Q={{user}}'},
        {'model': 'm1', 'messages': [{'role': 'user', 'content': 'hello'}], 'user': 'hello'},
    )
    assert rendered['model'] == 'm1'
    assert isinstance(rendered['payload'], list)
    assert rendered['prompt'] == 'Q=hello'
    assert LLMGateway._deep_get({'result': {'answer': {'text': 'OK'}}}, 'result.answer.text') == 'OK'


def test_showcase_v12_contains_domain_closure_and_open_api_gateway():
    html = Path('CareerOS_H5_Showcase.html').read_text(encoding='utf-8')
    required = [
        'V12_STATE_SCHEMA=2',
        'deriveJobMatch',
        'deriveCapabilities',
        'generateGapTasks',
        'class LocalDemoAdapter',
        'class ApiAdapter',
        'Custom REST API',
        'request_template',
        'response_path',
        'data-import-all',
        'schemaVersion:V14_STATE_SCHEMA',
        'patchDefaultDashboardData',
        'xProviderAuthHeader',
        'xProviderQueryParams',
    ]
    for marker in required:
        assert marker in html
    assert 'keyword score ${(0.92-i*.08).toFixed(2)}' not in html

import httpx
import pytest
from app.model_store import ProviderRecord


@pytest.fixture
def public_test_dns(monkeypatch):
    """Keep mocked provider tests independent from enterprise DNS interception."""
    monkeypatch.setattr(
        "app.network_security.socket.getaddrinfo",
        lambda *args, **kwargs: [
            (2, 1, 6, "", ("93.184.216.34", 443)),
        ],
    )


@pytest.mark.asyncio
async def test_custom_rest_provider_executes_request_and_maps_response(monkeypatch, public_test_dns):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured['url'] = str(request.url)
        captured['auth'] = request.headers.get('X-Test-Key')
        captured['json'] = __import__('json').loads(request.content.decode())
        return httpx.Response(200, json={'result': {'text': 'CUSTOM_OK'}, 'usage': {'total_tokens': 7}})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        return real_client(transport=transport, timeout=kwargs.get('timeout'))

    monkeypatch.setattr('app.llm_gateway.httpx.AsyncClient', client_factory)
    provider = ProviderRecord(
        provider_id='custom', name='Custom', kind='custom_rest', base_url='https://unit.test/api',
        api_key='secret', default_model='m1', enabled=True, timeout_seconds=30,
        extra_headers={}, config={
            'auth_type': 'api_key_header', 'auth_header_name': 'X-Test-Key',
            'chat_path': '/generate', 'request_template': {'model': '{{model}}', 'prompt': '{{user}}'},
            'response_path': 'result.text', 'query_params': {'v': '1'},
        },
    )
    gateway = LLMGateway(store=None)  # private call does not touch store
    text, usage = await gateway._call_provider(provider, model='m1', system='sys', user='hello', temperature=0.2, max_tokens=32)
    assert text == 'CUSTOM_OK'
    assert usage['total_tokens'] == 7
    assert captured['auth'] == 'secret'
    assert captured['json'] == {'model': 'm1', 'prompt': 'hello'}
    assert 'v=1' in captured['url']

@pytest.mark.asyncio
async def test_oauth2_client_credentials_custom_rest_flow(monkeypatch, public_test_dns):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url), request.headers.get('Authorization'), request.content.decode(errors='ignore')))
        if str(request.url) == 'https://identity.test/oauth/token':
            body = request.content.decode()
            assert 'grant_type=client_credentials' in body
            assert 'client_id=career-os' in body
            assert 'client_secret=client-secret' in body
            assert 'scope=inference' in body
            return httpx.Response(200, json={'access_token': 'runtime-token', 'token_type': 'Bearer'})
        assert request.headers.get('Authorization') == 'Bearer runtime-token'
        return httpx.Response(200, json={'answer': {'text': 'OAUTH_OK'}})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        return real_client(transport=transport, timeout=kwargs.get('timeout'))

    monkeypatch.setattr('app.llm_gateway.httpx.AsyncClient', client_factory)
    provider = ProviderRecord(
        provider_id='oauth-custom', name='OAuth Custom', kind='custom_rest', base_url='https://api.test',
        api_key='client-secret', default_model='m1', enabled=True, timeout_seconds=30,
        extra_headers={}, config={
            'auth_type': 'oauth2_client_credentials',
            'oauth_token_url': 'https://identity.test/oauth/token',
            'oauth_client_id': 'career-os',
            'oauth_scope': 'inference',
            'chat_path': '/generate',
            'request_template': {'prompt': '{{user}}'},
            'response_path': 'answer.text',
        },
    )
    gateway = LLMGateway(store=None)
    text, _usage = await gateway._call_provider(provider, model='m1', system='sys', user='hello', temperature=0.2, max_tokens=32)
    assert text == 'OAUTH_OK'
    assert len(calls) == 2
