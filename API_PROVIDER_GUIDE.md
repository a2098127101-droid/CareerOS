# CareerOS Open API Provider Guide

## Purpose

CareerOS v1.2 does not require AI capability to be tied to a fixed vendor list. A provider is an adapter configuration. Existing adapters support OpenAI-compatible APIs, OpenAI Responses, Anthropic, Gemini and a generic Custom REST mode.

## Recommended connection modes

### 1. OpenAI-compatible
Use this for services exposing OpenAI-like chat endpoints, including self-hosted gateways and many third-party model platforms.

Configure:
- Provider ID and display name
- Base URL
- API key
- Default model
- Auth type/header if nonstandard
- Optional chat path and models path
- Optional query parameters

### 2. Custom REST
Use this when the endpoint does not implement an OpenAI-compatible schema.

Example request template:

```json
{
  "model": "{{model}}",
  "prompt": "{{user}}",
  "messages": "{{messages}}",
  "temperature": "{{temperature}}",
  "max_tokens": "{{max_tokens}}"
}
```

Exact placeholder-only values such as `"{{messages}}"` are rendered as their native JSON type rather than a serialized string.

Example response mapping:

```text
result.answer.text
```

List indexes are supported with dotted paths such as:

```text
choices.0.message.content
```

## Authentication modes

Implemented:
- Bearer token
- API key header
- API key query parameter
- Basic auth token source
- OAuth2 Client Credentials
- Custom headers only
- None

OAuth2 Client Credentials uses the encrypted API Key / Credential field as the client secret and supports Token URL, Client ID, Scope and Audience. v1.2 acquires a token per call; centralized token caching/refresh optimization remains follow-up work.

For secrets, use the API Key / Credential field. It is encrypted by backend provider storage. `extra_headers` are non-secret configuration and must not contain credentials.

## Generic configuration fields

- `base_url`
- `chat_path`
- `http_method`
- `models_path`
- `auth_type`
- `auth_header_name`
- `auth_prefix`
- `api_key_query_name`
- `extra_headers` (non-secret)
- `query_params`
- `request_template`
- `response_path`
- `models_response_path`

## Model discovery

`GET /api/admin/providers/{provider_id}/models`

For OpenAI-compatible providers, `/models` is used by default unless overridden. For Custom REST, configure `models_path` and, when needed, `models_response_path`.

If the provider has no model-list endpoint, models may be entered manually.

## Provider test

Use the existing Provider Test flow for a real backend handshake. Offline Demo mode intentionally reports that a real backend is required rather than fabricating `Connected`.

## API Playground

Admin UI includes an API Playground backed by:

```text
POST /api/admin/providers/playground
```

Inputs:
- provider
- model
- system prompt
- user prompt
- temperature
- max tokens

Outputs include provider/model, text, latency and token usage where the provider returns usage fields.

## Example: enterprise internal REST model

```text
Kind: Custom REST
Base URL: https://ai.company.internal/api
Auth: API Key Header
Header: X-Company-Key
Chat Path: /generate
Method: POST
Response Path: result.text
```

Request template:

```json
{
  "model": "{{model}}",
  "input": "{{user}}"
}
```

No change to CareerOS business modules is required.
