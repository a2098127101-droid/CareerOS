# CareerOS v1.2 Change Log

## Release position

`1.2.0-beta-domain-closure-open-api` is a pre-release development candidate. It materially upgrades domain linkage and provider extensibility, but it is **not** a claim of production certification.

## Implemented

### Domain closure in Showcase
- Introduced State Schema v2.
- Added stable task normalization and origin metadata.
- Added Evidence capability inference and Evidence-driven capability profile derivation.
- Added target-job requirement extraction, Evidence matching, dynamic match score and gap derivation.
- Added gap-to-task generation with duplicate prevention.
- Added dependency warning before deleting Evidence referenced by artifacts.
- Added artifact Evidence ID linkage.
- Replaced active fixed dashboard KPIs and fixed review score labels with state-derived values or explicit unreviewed states.

### Unified runtime foundation
- Added `LocalDemoAdapter` and `ApiAdapter` foundation in the H5 application.
- Added runtime mode and API base URL settings.
- Provider operations can use the real FastAPI backend in API mode.
- Default workspace setting now affects boot routing.
- Added schema-wrapped backup export and JSON restore.

### Open API Gateway
- Added `custom_rest` provider kind.
- Added vendor-neutral auth/config metadata: auth type, auth header name, prefix, API-key query name, chat/models paths, HTTP method, request template, response mapping, models mapping and query parameters.
- Reused provider metadata storage without introducing a new database table migration.
- Added Custom REST request execution and response extraction.
- Added provider model discovery endpoint.
- Added provider playground endpoint and Admin UI.
- Added real provider test behavior; offline H5 does not fabricate connectivity.
- Added configurable non-secret extra headers. Secrets must use the encrypted API-key field.

### Data quality and UX
- Replaced simplistic comma splitting with an RFC4180-style CSV parser for Showcase job imports.
- Removed fabricated local retrieval probability-like scores.
- Added state-driven system/advisor/student default dashboard patches.
- Preserved multi-language selector and RTL support from v1.1.

## Partially implemented
- `ApiAdapter` is currently wired deeply for Provider operations; other domain entities still primarily use the local H5 store in Showcase mode.
- Evidence → Capability → Job → Gap → Task linkage is implemented in the H5 domain engine, but the full normalized relational graph is not yet persisted as dedicated backend link tables.
- Provider auth supports bearer/API-key header/API-key query/basic/OAuth2 client credentials/custom-header/none patterns. OAuth2 token acquisition is implemented without token caching; production secret rotation and centralized token caching remain follow-up hardening.
- Existing translation system remains mixed with legacy text-based replacement; a full translation-key migration is pending.

## Not yet implemented / external requirements
- Full entity-wide API adapter migration.
- Real PostgreSQL/pgvector + Redis + object storage deployment certification.
- Real semantic embedding/reranking certification.
- DOCX/PDF/PPTX production renderers.
- Enterprise SSO/SCIM and production billing.
- Full E2E browser suite in CI for every route/action/language combination.
