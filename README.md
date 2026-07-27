# CareerOS v1.5 · Domain Intelligence

CareerOS is an evidence-grounded career intelligence platform. v1.5 promotes the core chain **Claim → Capability → Job Requirement → Gap** into persistent, versioned, explainable and auditable server-side domain entities.

> Release status: internal Beta / GitHub-ready source release. Domain Intelligence is implemented and regression-tested. Production infrastructure, calibrated assessment methodology and standard-browser staging certification remain separate release gates.

## What v1.5 adds

- First-class persistent claims and claim versions.
- Versioned capability definitions and capability assessment history.
- Claim ↔ Evidence and Claim ↔ Capability relations.
- Versioned job-requirement snapshots and Requirement ↔ Capability mappings.
- Versioned career gaps with optimistic locking and lifecycle status.
- Potential score versus verified score, with contribution-level explanations.
- Domain audit events for create, update, recompute, mapping and status changes.
- SQLite and SQLAlchemy/PostgreSQL repository parity.
- Canonical `/api/domain/v1` API and Unified H5 consumption.
- Evidence Trust lifecycle retained: self-reported evidence is not treated as verified evidence.

## Quick start

### Windows

1. Extract the repository.
2. Double-click `OPEN_CareerOS.cmd`.
3. Open the URL shown by the launcher.

### Python

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Default local demo accounts are documented in `.env.example`. Never enable demo seeding in production.

## Domain Intelligence API

```text
POST  /api/domain/v1/recompute
GET   /api/domain/v1/snapshot
GET   /api/domain/v1/claims
PATCH /api/domain/v1/claims/{claim_id}
GET   /api/domain/v1/claims/{claim_id}/versions
GET   /api/domain/v1/capabilities
GET   /api/domain/v1/capabilities/{capability_id}/explain
GET   /api/domain/v1/capabilities/{capability_id}/versions
GET   /api/domain/v1/requirements
GET   /api/domain/v1/requirements/{requirement_id}/versions
GET   /api/domain/v1/gaps
PATCH /api/domain/v1/gaps/{gap_id}
GET   /api/domain/v1/gaps/{gap_id}/versions
GET   /api/domain/v1/audit
```

## Validation

- Automated tests: **161/161 passed**
- SQLite migration: **22/22**
- Alembic head: `0010_immutable_runtime_tenant_hardening`
- Immutable published-migration guard and upgrade-from-original-0007 test.
- Canonical `/api/v1` compatibility surface with OpenAPI cookie authentication.
- Deterministic Demo retrieval evaluation and disposable staging infrastructure probe.
- Chrome multi-role browser E2E.

Real generation-model, semantic Embedding and remote Reranker calls remain
environment-dependent gates and were not tested without credentials.

## Important boundaries

The deterministic v1.5 score is an explainable evidence-coverage indicator. It is **not** a psychometric test, professional certification or validated predictor of job performance. See `REMAINING_GAPS_v1.5.md` and `PRODUCTION_READINESS_v1.5.md`.

## Documentation

- `ARCHITECTURE_v1.5.md`
- `DOMAIN_INTELLIGENCE_MODEL.md`
- `API_DOMAIN_INTELLIGENCE_GUIDE.md`
- `MIGRATION_GUIDE_v1.5.md`
- `TEST_REPORT_v1.5.md`
- `PRODUCTION_READINESS_v1.5.md`
- `REMAINING_GAPS_v1.5.md`
- `GITHUB_UPLOAD_GUIDE.md`
- `CHANGELOG_v1.5.md`
- `RELEASE_NOTES_v1.5.md`
- `SOURCE_PROVENANCE_v1.5.md`
