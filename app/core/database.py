from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    text,
)
from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class DatabaseCapabilityReport:
    backend: str
    configured_url: bool
    sqlalchemy_available: bool
    postgres_driver_available: bool
    production_ready: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


def postgres_driver_available() -> bool:
    return importlib.util.find_spec("psycopg") is not None or importlib.util.find_spec("psycopg2") is not None


def normalize_database_url(database_url: str, db_path: str) -> str:
    raw = (database_url or "").strip()
    if not raw:
        return f"sqlite:///{Path(db_path).resolve().as_posix()}"
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]
    if raw.startswith("postgresql://") and "+" not in raw.split("://", 1)[0]:
        # Prefer psycopg v3 when installed. The explicit driver keeps runtime errors deterministic.
        raw = "postgresql+psycopg://" + raw.split("://", 1)[1]
    return raw


def database_backend(database_url: str, db_path: str) -> str:
    url = normalize_database_url(database_url, db_path)
    return "postgresql" if url.startswith("postgresql") else "sqlite"


def create_database_engine(database_url: str, db_path: str, *, echo: bool = False) -> Engine:
    url = normalize_database_url(database_url, db_path)
    kwargs: dict[str, Any] = {"future": True, "pool_pre_ping": True, "echo": echo}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if url.startswith("postgresql"):
        _install_postgres_tenant_context(engine)
    return engine


def _tenant_from_parameters(parameters: Any) -> str:
    candidate = parameters
    if isinstance(candidate, (list, tuple)) and candidate and isinstance(candidate[0], dict):
        candidate = candidate[0]
    if not isinstance(candidate, dict):
        return ""
    for key in ("tenant", "tenant_id", "target_tenant"):
        value = candidate.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _install_postgres_tenant_context(engine: Engine) -> None:
    """Set transaction-local RLS context before tenant-scoped statements.

    Repository parameters take precedence over the request context. This keeps
    explicit cross-tenant administration auditable while ordinary requests use
    the authenticated principal established by the API dependency.
    """
    from ..tenant_context import current_tenant_id, platform_admin_context

    @event.listens_for(engine, "before_cursor_execute")
    def _set_rls_context(conn, cursor, statement, parameters, context, executemany):
        if "set_config('app.tenant_id'" in statement:
            return
        tenant_id = _tenant_from_parameters(parameters) or current_tenant_id()
        if tenant_id:
            cursor.execute(
                "SELECT set_config('app.tenant_id', %s, true)",
                (tenant_id,),
            )
        cursor.execute(
            "SELECT set_config('app.platform_admin', %s, true)",
            ("on" if platform_admin_context() else "off",),
        )


def database_capabilities(*, database_url: str, db_path: str, repository_backend: str, app_env: str) -> DatabaseCapabilityReport:
    backend = database_backend(database_url, db_path)
    blockers: list[str] = []
    warnings: list[str] = []
    driver = postgres_driver_available()
    requested = (repository_backend or "sqlite").strip().lower()

    if requested == "postgresql" and backend != "postgresql":
        blockers.append("REPOSITORY_BACKEND=postgresql requires a PostgreSQL DATABASE_URL")
    if backend == "postgresql" and not driver:
        blockers.append("PostgreSQL URL is configured but psycopg/psycopg2 is not installed")
    if app_env == "production":
        if backend != "postgresql":
            blockers.append("Production runtime requires PostgreSQL; SQLite remains development/local only")
        if requested != "postgresql":
            blockers.append("Production runtime requires REPOSITORY_BACKEND=postgresql")
    if requested == "sqlite" and backend == "postgresql":
        warnings.append("DATABASE_URL points to PostgreSQL but runtime repositories are still configured for SQLite")
    if requested == "postgresql":
        warnings.append("v1.0-beta1 retains pgvector-aware semantic retrieval while centralizing schema ownership and adding configurable workflow/artifact engines; live PostgreSQL/pgvector integration must still be verified in the target environment")

    return DatabaseCapabilityReport(
        backend=backend,
        configured_url=bool((database_url or "").strip()),
        sqlalchemy_available=True,
        postgres_driver_available=driver,
        production_ready=not blockers and requested == "postgresql" and backend == "postgresql",
        blockers=tuple(blockers),
        warnings=tuple(warnings),
    )


def _sa_type(sqlite_type: str):
    t = (sqlite_type or "TEXT").upper()
    if "INT" in t:
        return Integer()
    if any(k in t for k in ("REAL", "FLOA", "DOUB")):
        return Float()
    if "BLOB" in t:
        return LargeBinary()
    if "DATE" in t or "TIME" in t:
        return DateTime(timezone=True)
    if "BOOL" in t:
        return Boolean()
    # Keep opaque identifiers and JSON-as-text compatible across SQLite/PostgreSQL.
    return Text()


def _server_default(value: str | None):
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    # Existing defaults are SQL literals (CURRENT_TIMESTAMP, 'active', 0, 1, '{}', ...).
    return text(raw)


def load_schema_manifest(path: str | Path | None = None) -> dict[str, Any]:
    manifest_path = Path(path) if path else Path(__file__).resolve().parents[1] / "schema_manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def build_metadata_from_manifest(path: str | Path | None = None) -> MetaData:
    manifest = load_schema_manifest(path)
    metadata = MetaData()

    # First pass creates tables/columns without FK constraints so cross-table references are resolvable.
    for table_name, spec in manifest["tables"].items():
        columns = []
        pk_cols: list[str] = []
        for col in spec.get("columns", []):
            if int(col.get("pk") or 0) > 0:
                pk_cols.append(col["name"])
            columns.append(
                Column(
                    col["name"],
                    _sa_type(col.get("type", "TEXT")),
                    nullable=not bool(col.get("notnull")),
                    server_default=_server_default(col.get("default")),
                )
            )
        constraints = []
        if pk_cols:
            constraints.append(PrimaryKeyConstraint(*pk_cols, name=f"pk_{table_name}"))
        for idx, unique_cols in enumerate(spec.get("unique_constraints", []), 1):
            if unique_cols and set(unique_cols) != set(pk_cols):
                constraints.append(UniqueConstraint(*unique_cols, name=f"uq_{table_name}_{idx}"))
        Table(table_name, metadata, *columns, *constraints)

    # Second pass appends FK constraints and indexes.
    for table_name, spec in manifest["tables"].items():
        table = metadata.tables[table_name]
        for i, fk in enumerate(spec.get("foreign_keys", []), 1):
            if fk.get("table") not in metadata.tables:
                continue
            table.append_constraint(
                ForeignKeyConstraint(
                    [fk["from"]],
                    [f"{fk['table']}.{fk['to']}"],
                    name=f"fk_{table_name}_{i}_{fk['from']}",
                    ondelete=None if fk.get("on_delete") in {None, "NO ACTION"} else fk.get("on_delete"),
                    onupdate=None if fk.get("on_update") in {None, "NO ACTION"} else fk.get("on_update"),
                )
            )
        for idx in spec.get("indexes", []):
            cols = [table.c[c] for c in idx.get("columns", []) if c in table.c]
            if cols:
                Index(idx["name"], *cols, unique=bool(idx.get("unique")))
    return metadata


BASELINE_METADATA = build_metadata_from_manifest()


def schema_health(engine: Engine, expected_tables: set[str] | None = None) -> dict[str, Any]:
    """Inspect runtime schema without mutating it.

    Production PostgreSQL startup uses this as a fail-closed guard. Schema creation remains the
    responsibility of Alembic; repositories never auto-create tables in production.
    """
    from sqlalchemy import inspect
    inspector = inspect(engine)
    present = set(inspector.get_table_names())
    expected = expected_tables or set(BASELINE_METADATA.tables.keys())
    missing = sorted(expected - present)
    return {"present_count": len(present), "expected_count": len(expected), "missing": missing, "ready": not missing}
