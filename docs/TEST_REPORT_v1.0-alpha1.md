# Test report · v1.0-alpha1

## Automated tests

The release adds tests for:

- PostgreSQL DDL compilation from baseline metadata.
- Repository container SQLite compatibility.
- Production database readiness fail-closed behavior.
- Generic role aliases.
- `enterprise_talent` preset.
- Legacy profile → canonical participant profile mapping.
- SQLite snapshot export and PostgreSQL import dry-run.
- Alembic baseline upgrade on a fresh SQLite test database.
- SQLAlchemy session repository parity using the baseline schema.
- Generic API aliases and participant profile endpoint.

## Environment limitation

A real PostgreSQL server and PostgreSQL Python driver are not available in the current execution environment. Therefore:

- PostgreSQL DDL compilation: tested.
- Alembic baseline behavior: tested against SQLite.
- PostgreSQL live connection: NOT VERIFIED.
- SQLite → live PostgreSQL import: NOT VERIFIED.
- pgvector: NOT IMPLEMENTED in this phase.

These boundaries are intentional and must remain visible in Production Readiness diagnostics.

## Final regression result

```text
pytest -vv
45 passed
```

Additional checks:

```text
python -m compileall app scripts alembic
PASS

student.html JavaScript
PASS

teacher.html JavaScript
PASS

admin.html JavaScript
PASS

login.html JavaScript
PASS

CareerOS_H5_Showcase.html JavaScript
PASS
```

API smoke on an isolated SQLite database:

```text
/api/health                         200
/api/product/config                 200
/api/admin/system/readiness         200
/api/admin/system/repositories      200
/participant                        200
/advisor                            200
/showcase                           200
participant-profile API             PASS
```
