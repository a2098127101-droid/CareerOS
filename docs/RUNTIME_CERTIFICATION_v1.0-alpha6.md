# Runtime Certification · v1.0-alpha6

## CLI

```bash
python scripts/certify_runtime.py --out data/runtime_certification.json
```

Optional destructive temporary object round-trip:

```bash
python scripts/certify_runtime.py --storage-roundtrip
```

Optional LLM connectivity check is enabled by default. Use `--skip-llm` when no billable provider should be contacted.

## What is checked

- target PostgreSQL certification file validity;
- Redis ping;
- S3-compatible object upload/get/delete when explicitly requested;
- remote semantic embedding call without silent local-hash promotion;
- live LLM provider connectivity when enabled.

The tool intentionally returns a non-zero exit code unless all requested required checks pass.

## Admin API

- `GET /api/admin/system/runtime-certification`
- `POST /api/admin/system/runtime-certification`

The POST route is restricted to platform administrators because it can contact billable/external infrastructure.
