from __future__ import annotations

import csv
import io
import json
import sqlite3
import threading
from pathlib import Path
from uuid import uuid4


class JobStore:
    """Structured job data store. Live/structured job facts should not be flattened into generic RAG text."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Ensure the canonical SQLite compatibility schema via the centralized migration layer.

        Store modules no longer own CREATE TABLE/CREATE INDEX DDL. The checked-in schema manifest
        and versioned migrations are the single compatibility source used by both local SQLite and
        Alembic/PostgreSQL provisioning.
        """
        from .migrations import run_migrations
        run_migrations(str(self.db_path))

    def upsert(self, data: dict, *, tenant_id: str | None = None) -> dict:
        job_id = (data.get("job_id") or "").strip() or f"JOB-{uuid4().hex[:12].upper()}"
        skills = data.get("skills", [])
        if isinstance(skills, str):
            skills = [x.strip() for x in skills.replace("；", ",").replace(";", ",").split(",") if x.strip()]
        def num(v):
            try:
                return float(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                return None
        tenant_id = tenant_id or str(data.get("tenant_id") or "global")
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs(job_id,tenant_id,title,company,city,industry,salary_min,salary_max,skills_json,description,source,source_url,active,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                ON CONFLICT(job_id) DO UPDATE SET
                  tenant_id=excluded.tenant_id, title=excluded.title, company=excluded.company, city=excluded.city, industry=excluded.industry,
                  salary_min=excluded.salary_min, salary_max=excluded.salary_max, skills_json=excluded.skills_json,
                  description=excluded.description, source=excluded.source, source_url=excluded.source_url,
                  active=excluded.active, updated_at=CURRENT_TIMESTAMP
                """,
                (
                    job_id, tenant_id, str(data.get("title", "")).strip(), str(data.get("company", "")).strip(),
                    str(data.get("city", "")).strip(), str(data.get("industry", "")).strip(),
                    num(data.get("salary_min")), num(data.get("salary_max")), json.dumps(skills, ensure_ascii=False),
                    str(data.get("description", "")).strip(), str(data.get("source", "manual")).strip(),
                    str(data.get("source_url", "")).strip(), int(bool(data.get("active", True))),
                ),
            )
            conn.commit()
        return self.get(job_id)

    def get(self, job_id: str, *, tenant_id: str | None = None) -> dict:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id=?" + (" AND tenant_id IN (?,'global')" if tenant_id is not None else ""), ((job_id,tenant_id) if tenant_id is not None else (job_id,))).fetchone()
        if not row:
            raise KeyError(job_id)
        return self._row(row)

    def search(self, query: str = "", city: str = "", industry: str = "", limit: int = 20, *, tenant_id: str = "global") -> list[dict]:
        clauses = ["active=1", "tenant_id IN (?,'global')"]
        params: list = [tenant_id]
        if query.strip():
            clauses.append("(title LIKE ? OR company LIKE ? OR description LIKE ? OR skills_json LIKE ?)")
            token = f"%{query.strip()}%"
            params.extend([token, token, token, token])
        if city.strip():
            clauses.append("city LIKE ?")
            params.append(f"%{city.strip()}%")
        if industry.strip():
            clauses.append("industry LIKE ?")
            params.append(f"%{industry.strip()}%")
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM jobs WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT ?", tuple(params)
            ).fetchall()
        return [self._row(r) for r in rows]

    def ingest_csv(self, content: bytes, source: str = "csv", *, tenant_id: str = "global") -> dict:
        text = content.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        count = 0
        errors: list[str] = []
        for idx, row in enumerate(reader, start=2):
            if not (row.get("title") or "").strip():
                errors.append(f"第 {idx} 行缺少 title")
                continue
            try:
                row["source"] = row.get("source") or source
                self.upsert(row, tenant_id=tenant_id)
                count += 1
            except Exception as exc:
                errors.append(f"第 {idx} 行：{exc}")
        return {"imported": count, "errors": errors[:30]}

    def replace_requirements(self, job_id: str, requirements: list[dict], *, tenant_id: str) -> int:
        # Ensure the job itself is visible inside the tenant/global scope before writing derived requirements.
        self.get(job_id, tenant_id=tenant_id)
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM job_requirements WHERE job_id=? AND tenant_id=?", (job_id, tenant_id))
            count = 0
            for item in requirements:
                requirement_id = str(item.get("requirement_id") or f"REQ-{uuid4().hex[:14].upper()}")
                conn.execute(
                    """INSERT INTO job_requirements(requirement_id,tenant_id,job_id,category,requirement_text,normalized_key,importance,source_type)
                    VALUES(?,?,?,?,?,?,?,?)""",
                    (requirement_id, tenant_id, job_id, str(item.get("category") or "requirement"),
                     str(item.get("text") or item.get("requirement_text") or ""),
                     str(item.get("normalized_key") or ""), max(1, min(int(item.get("importance") or 3), 5)),
                     str(item.get("source_type") or "derived")),
                )
                count += 1
            conn.commit()
        return count

    def list_requirements(self, job_id: str, *, tenant_id: str) -> list[dict]:
        # Tenant-local derived requirements take precedence; global rows remain readable for global jobs.
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM job_requirements WHERE job_id=? AND tenant_id IN (?,'global')
                ORDER BY CASE WHEN tenant_id=? THEN 0 ELSE 1 END, importance DESC, created_at""",
                (job_id, tenant_id, tenant_id),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_job(self, job_id: str, *, tenant_id: str) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT tenant_id FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if not row or row["tenant_id"] not in {tenant_id}:
                return False
            conn.execute("DELETE FROM job_requirements WHERE job_id=? AND tenant_id=?", (job_id, tenant_id))
            cur = conn.execute("DELETE FROM jobs WHERE job_id=? AND tenant_id=?", (job_id, tenant_id))
            conn.commit()
            return bool(cur.rowcount)

    def stats(self, *, tenant_id: str = "global") -> dict:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) total,COUNT(DISTINCT city) cities,COUNT(DISTINCT industry) industries FROM jobs WHERE active=1 AND tenant_id IN (?,'global')", (tenant_id,)).fetchone()
        return dict(row)

    @staticmethod
    def _row(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["skills"] = json.loads(d.pop("skills_json") or "[]")
        d["active"] = bool(d["active"])
        return d
