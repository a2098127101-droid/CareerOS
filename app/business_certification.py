from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from .auth_store import Principal
from .rag_evaluation import RAGEvalCase, evaluate_rag
from .runtime_certification import runtime_environment_fingerprint


@dataclass
class BusinessCheck:
    name: str
    status: str  # PASS | FAIL | NOT_CONFIGURED | NOT_VERIFIED
    detail: str
    evidence: dict[str, Any]
    required: bool = True


def _signature_payload(report: dict[str, Any]) -> bytes:
    clean = {k: v for k, v in report.items() if k != "signature"}
    return json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_business_certification(report: dict[str, Any], secret_key: str) -> dict[str, Any]:
    signed = dict(report)
    signed["signature"] = hmac.new(secret_key.encode("utf-8"), _signature_payload(signed), hashlib.sha256).hexdigest()
    return signed


def write_business_certification(report: dict[str, Any], path: str, *, secret_key: str) -> dict[str, Any]:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    signed = sign_business_certification(report, secret_key)
    target.write_text(json.dumps(signed, ensure_ascii=False, indent=2), encoding="utf-8")
    return signed


def load_business_certification(path: str | Path, *, settings) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {"valid": False, "reason": "business certification file not found", "path": str(target)}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"valid": False, "reason": f"invalid business certification file: {exc}", "path": str(target)}
    reasons: list[str] = []
    if data.get("format") != "careeros-business-certification-v1":
        reasons.append("unsupported business certification format")
    if data.get("environment_fingerprint") != runtime_environment_fingerprint(settings):
        reasons.append("business certification belongs to a different deployment configuration")
    signature = str(data.get("signature") or "")
    expected = hmac.new(settings.app_secret_key.encode("utf-8"), _signature_payload(data), hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        reasons.append("business certification signature is missing or invalid")
    if not data.get("all_required_pass"):
        reasons.append("one or more required business checks did not pass")
    try:
        generated = datetime.fromisoformat(str(data.get("generated_at") or "").replace("Z", "+00:00"))
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - generated.astimezone(timezone.utc)).total_seconds() / 3600
        if age_hours > max(1, int(settings.business_certification_max_age_hours)):
            reasons.append(f"business certification is stale ({age_hours:.1f}h old)")
    except Exception:
        reasons.append("business certification generated_at is invalid")
    return {**data, "valid": not reasons, "reason": "; ".join(reasons), "path": str(target)}


class BusinessE2ECertification:
    """Exercise the real CareerOS HTTP business path against the configured runtime.

    The certifier provisions deterministic certification tenants/users directly through the active repository,
    then uses authenticated HTTP requests to the running API. It intentionally requires live Agent task usage
    records, so deterministic demo fallbacks cannot satisfy the AI part of the gate.
    """

    def __init__(self, *, settings, repositories, base_url: str):
        self.settings = settings
        self.repositories = repositories
        self.base_url = base_url.rstrip("/")
        self.tenant_a = "runtime-cert-a"
        self.tenant_b = "runtime-cert-b"
        self.run_marker = uuid4().hex[:12]
        self.created_sources: list[tuple[str, str]] = []
        self.created_sessions: list[tuple[str, str]] = []
        self.created_users: list[tuple[str, str]] = []
        self.created_jobs: list[tuple[str, str]] = []

    def _origin(self) -> str:
        return self.settings.allowed_origins[0] if self.settings.allowed_origins else self.base_url

    def _provision_principal(self, tenant_id: str, label: str) -> tuple[Principal, str]:
        """Create an ephemeral certification principal with non-reusable credentials.

        Certification identities must never leave a known default password in a staging/production database.
        Each run therefore uses a unique invalid.local address plus a cryptographically random password, and
        cleanup de-identifies/archives the created identity after the certificate is produced.
        """
        identity = self.repositories.identity
        identity.ensure_tenant(tenant_id, f"CareerOS Runtime Certification {tenant_id[-1].upper()}", tenant_type="organization", product_preset="career_development")
        email = f"runtime-cert-{label}-{self.run_marker}@invalid.local"
        user = identity.ensure_user(
            email=email,
            password=secrets.token_urlsafe(48),
            display_name="Runtime Certification User",
            tenant_id=tenant_id,
            role="participant",
        )
        self.created_users.append((user["user_id"], tenant_id))
        principal = Principal(
            user_id=user["user_id"], email=user["email"], display_name=user.get("display_name") or "Runtime Certification User",
            tenant_id=tenant_id, role="participant", authenticated=True,
        )
        return principal, identity.create_session(principal)

    @staticmethod
    def _response_ok(response: httpx.Response, label: str) -> dict[str, Any]:
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"{label} failed: HTTP {response.status_code}: {response.text[:500]}")
        try:
            return response.json()
        except Exception as exc:
            raise RuntimeError(f"{label} returned non-JSON response") from exc

    def _client(self, token: str) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            timeout=max(60.0, float(self.settings.embedding_timeout_seconds) + 30.0),
            headers={"Origin": self._origin(), "X-CareerOS-Certification": "business-e2e-v1"},
            cookies={"careeros_session": token},
            follow_redirects=True,
        )

    def _cleanup_session(self, session_id: str, tenant_id: str) -> None:
        # Best-effort cleanup; certification result must not be hidden by cleanup failures.
        for repo in (
            self.repositories.evidence_graph,
            self.repositories.evidence,
            self.repositories.artifacts,
            self.repositories.workflows,
            self.repositories.collaboration,
            self.repositories.sessions,
        ):
            try:
                repo.delete_session(session_id, tenant_id=tenant_id)
            except Exception:
                pass

    def _cleanup(self) -> dict[str, int]:
        result = {"sources_deleted": 0, "sessions_deleted": 0, "users_deidentified": 0, "jobs_deactivated": 0, "cleanup_errors": 0}
        for source_id, tenant_id in self.created_sources:
            try:
                self.repositories.knowledge.delete_source(source_id, tenant_id=tenant_id)
                result["sources_deleted"] += 1
            except Exception:
                result["cleanup_errors"] += 1
        for session_id, tenant_id in self.created_sessions:
            try:
                self._cleanup_session(session_id, tenant_id)
                result["sessions_deleted"] += 1
            except Exception:
                result["cleanup_errors"] += 1
        for job_id, tenant_id in self.created_jobs:
            try:
                self.repositories.jobs.upsert({
                    "job_id": job_id, "title": "Runtime Certification Job", "company": "CareerOS Certification",
                    "skills": [], "description": "Inactive runtime certification fixture", "source": "runtime_certification", "active": False,
                }, tenant_id=tenant_id)
                result["jobs_deactivated"] += 1
            except Exception:
                result["cleanup_errors"] += 1
        for user_id, tenant_id in self.created_users:
            try:
                self.repositories.identity.anonymize_user_identity(user_id=user_id, tenant_id=tenant_id)
                result["users_deidentified"] += 1
            except Exception:
                result["cleanup_errors"] += 1
        return result

    def check_semantic_rag_quality(self) -> BusinessCheck:
        if not self.settings.embedding_provider or self.settings.embedding_provider == "local_hash":
            return BusinessCheck("semantic_rag_quality", "NOT_CONFIGURED", "real semantic embedding provider is not configured", {})
        marker = uuid4().hex[:10]
        docs = [
            ("Current Official 2026", f"Certification marker {marker}. The current 2026 rule requires evidence trace before final approval.", "official", "2026", 100),
            ("Old Official 2025", f"Certification marker {marker}. The old 2025 rule allowed approval without the new evidence trace requirement.", "official", "2025", 90),
            ("Internal 2026 Note", f"Certification marker {marker}. Internal guidance discusses evidence trace but is not the authoritative rule.", "internal", "2026", 60),
        ]
        try:
            source_ids = []
            for idx, (title, text, authority, year, priority) in enumerate(docs):
                row = self.repositories.knowledge.ingest(
                    title=title, filename=f"cert-{idx}.txt", mime_type="text/plain", text=text,
                    scope="global", category="policy", authority=authority, effective_year=year,
                    priority=priority, tenant_id=self.tenant_a,
                )
                source_ids.append(row["source_id"])
                self.created_sources.append((row["source_id"], self.tenant_a))
            result = evaluate_rag(
                self.repositories.knowledge,
                [RAGEvalCase(
                    query=f"2026 current certification marker {marker} evidence trace requirement",
                    expected_source_id=source_ids[0], expected_authority="official", expected_year="2026", scope="global",
                )],
                tenant_id=self.tenant_a, k=10,
            )
            metrics = result["metrics"]
            tenant_b_hits = self.repositories.knowledge.search(
                f"2026 current certification marker {marker} evidence trace requirement",
                scope="global", top_k=10, tenant_id=self.tenant_b, effective_year="2026",
            )
            leaked = any(getattr(hit, "source_id", "") in set(source_ids) for hit in tenant_b_hits)
            passed = (
                metrics.get("recall_at_5", 0) >= 1.0
                and metrics.get("authority_accuracy", 0) >= 1.0
                and metrics.get("temporal_accuracy", 0) >= 1.0
                and not leaked
            )
            return BusinessCheck(
                "semantic_rag_quality", "PASS" if passed else "FAIL",
                "semantic hybrid retrieval selected the current authoritative source without cross-tenant leakage" if passed else "semantic RAG quality or tenant-isolation thresholds were not met",
                {"metrics": metrics, "run_id": result.get("run_id"), "expected_source_id": source_ids[0], "cross_tenant_knowledge_leak": leaked},
            )
        except Exception as exc:
            return BusinessCheck("semantic_rag_quality", "FAIL", str(exc), {})

    def check_business_flow_and_tenant_isolation(self) -> BusinessCheck:
        identity = self.repositories.identity
        commercial = self.repositories.commercial
        try:
            pa, token_a = self._provision_principal(self.tenant_a, "a")
            pb, token_b = self._provision_principal(self.tenant_b, "b")
            commercial.set_plan(self.tenant_a, "enterprise")
            commercial.set_plan(self.tenant_b, "enterprise")

            before_usage = self.repositories.models.usage_summary(limit=200, tenant_id=self.tenant_a)["summary"]["calls"]
            started = time.perf_counter()
            with self._client(token_a) as a, self._client(token_b) as b:
                health = self._response_ok(a.get("/api/health"), "health")
                required_tasks = {"profile", "coach", "writer", "reviewer", "critic", "revision"}
                disabled = [task for task in required_tasks if not health.get("tasks", {}).get(task, {}).get("enabled")]
                if disabled:
                    return BusinessCheck("business_e2e", "FAIL", f"required live Agent tasks are disabled: {', '.join(sorted(disabled))}", {"disabled_tasks": disabled})

                state_a = self._response_ok(a.post("/api/sessions"), "create session A")
                state_b = self._response_ok(b.post("/api/sessions"), "create session B")
                sid_a, sid_b = state_a["session_id"], state_b["session_id"]
                self.created_sessions.extend([(sid_a, self.tenant_a), (sid_b, self.tenant_b)])

                profile = self._response_ok(a.post(
                    f"/api/sessions/{sid_a}/profile/extract",
                    json={"text": "目标方向：Product Analyst\n技能：SQL\n真实经历：完成一个结构化数据分析项目，并形成可核验分析报告。"},
                ), "profile extraction")
                if not profile.get("profile", {}).get("target_job"):
                    raise RuntimeError("profile extraction did not establish target_job")

                coach = self._response_ok(a.post("/api/chat", json={"session_id": sid_a, "message": "基于我的真实证据，给出下一步最关键行动。"}), "coach")
                if not str(coach.get("reply") or "").strip():
                    raise RuntimeError("coach returned empty reply")

                upload = self._response_ok(a.post(
                    "/api/files/parse", data={"session_id": sid_a},
                    files={"file": ("certification.txt", b"Verified certification evidence file for tenant isolation.", "text/plain")},
                ), "private file upload")
                object_id = str((upload.get("storage") or {}).get("object_id") or "")
                if not object_id:
                    raise RuntimeError("private file upload did not persist an object_id")

                certification_job_id = "JOB-RUNTIME-CERT-A"
                self.repositories.jobs.upsert({
                    "job_id": certification_job_id, "title": "Product Analyst", "company": "CareerOS Certification",
                    "industry": "Technology", "skills": ["SQL", "Python"],
                    "description": "Certification fixture requires SQL and Python. Job requirements never imply participant capability.",
                    "source": "runtime_certification", "active": True,
                }, tenant_id=self.tenant_a)
                # Force current Job Intelligence decomposition to run instead of reusing derived requirements
                # left by a previous certification run for this deterministic fixture job.
                self.repositories.jobs.replace_requirements(certification_job_id, [], tenant_id=self.tenant_a)
                self.created_jobs.append((certification_job_id, self.tenant_a))
                job_match = self._response_ok(
                    a.post(f"/api/jobs/{certification_job_id}/match", json={"session_id": sid_a}),
                    "job intelligence",
                )
                requirement_rows = job_match.get("requirements") or []
                statuses = {str(row.get("status") or "") for row in requirement_rows}
                if "MATCHED" not in statuses or not statuses.intersection({"MISSING", "PARTIAL", "UNKNOWN"}):
                    raise RuntimeError(f"job intelligence did not distinguish supported from unsupported requirements: {sorted(statuses)}")

                draft = self._response_ok(a.post("/api/draft/generate", json={"session_id": sid_a, "document_type": "career_report", "extra_instructions": "仅使用已确认事实，不得编造数字。"}), "writer")
                artifact = draft.get("artifact") or {}
                artifact_id = artifact.get("artifact_id")
                if not artifact_id or not str(draft.get("draft") or "").strip():
                    raise RuntimeError("writer did not persist a non-empty artifact")

                review = self._response_ok(a.post("/api/review", json={"session_id": sid_a}), "reviewer")
                if "review" not in review or "total_score" not in review["review"]:
                    raise RuntimeError("reviewer did not return a structured review")

                evidence_verification = self._response_ok(
                    a.post(f"/api/sessions/{sid_a}/evidence-verify", json={"claim_ids": []}),
                    "evidence verification",
                )
                if int(evidence_verification.get("verified") or 0) < 1:
                    raise RuntimeError("evidence verification did not verify any artifact claim")

                revised = self._response_ok(a.post("/api/revise", json={"session_id": sid_a}), "revision")
                if not str(revised.get("revised_draft") or "").strip():
                    raise RuntimeError("revision returned empty output")

                versions = self._response_ok(a.get(f"/api/artifacts/{artifact_id}/versions"), "artifact versions")
                if len(versions.get("versions") or []) < 2:
                    raise RuntimeError("artifact version chain did not contain draft + revision")
                trace = self._response_ok(a.get(f"/api/artifacts/{artifact_id}/trace"), "artifact trace")
                if not isinstance(trace, dict):
                    raise RuntimeError("artifact trace missing")

                # Server-side cross-tenant attack suite: a valid tenant B session must not access tenant A resources.
                attack_results = {
                    "session": b.get(f"/api/sessions/{sid_a}").status_code,
                    "workflow": b.get(f"/api/sessions/{sid_a}/workflow").status_code,
                    "evidence": b.get(f"/api/sessions/{sid_a}/evidence").status_code,
                    "evidence_graph": b.get(f"/api/sessions/{sid_a}/evidence-graph").status_code,
                    "feedback": b.get(f"/api/sessions/{sid_a}/feedback").status_code,
                    "artifact": b.get(f"/api/artifacts/{artifact_id}").status_code,
                    "versions": b.get(f"/api/artifacts/{artifact_id}/versions").status_code,
                    "artifact_trace": b.get(f"/api/artifacts/{artifact_id}/trace").status_code,
                    "file_access": b.get(f"/api/files/{object_id}/access").status_code,
                    "job_match": b.post(f"/api/jobs/{certification_job_id}/match", json={"session_id": sid_b}).status_code,
                }
                if any(code not in {403, 404} for code in attack_results.values()):
                    raise RuntimeError(f"cross-tenant access control failed: {attack_results}")
                deleted = a.delete(f"/api/files/{object_id}")
                if deleted.status_code != 200:
                    raise RuntimeError(f"private file cleanup failed: HTTP {deleted.status_code}")

            usage = self.repositories.models.usage_summary(limit=200, tenant_id=self.tenant_a)
            after_calls = usage["summary"]["calls"]
            successful_tasks = {str(row.get("task") or "") for row in usage.get("recent", []) if int(row.get("success") or 0) == 1}
            # critic is invoked from revision and must also be real when configured.
            required_usage = {"profile", "coach", "writer", "reviewer", "critic", "revision"}
            missing_usage = sorted(required_usage - successful_tasks)
            if after_calls <= before_usage or missing_usage:
                raise RuntimeError(f"business flow used fallback or failed live Agent calls; missing successful usage: {missing_usage}")

            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            return BusinessCheck(
                "business_e2e", "PASS", "authenticated Coach→Writer→Reviewer→Revision flow and cross-tenant attack suite passed",
                {
                    "session_id": sid_a, "artifact_id": artifact_id, "artifact_versions": len(versions.get("versions") or []),
                    "cross_tenant_statuses": attack_results, "successful_agent_tasks": sorted(successful_tasks & required_usage),
                    "evidence_claims_verified": int(evidence_verification.get("verified") or 0),
                    "job_intelligence_statuses": sorted(statuses),
                    "llm_calls_delta": after_calls - before_usage, "latency_ms": latency_ms,
                },
            )
        except Exception as exc:
            return BusinessCheck("business_e2e", "FAIL", str(exc), {})

    def run(self) -> dict[str, Any]:
        checks: list[BusinessCheck] = []
        cleanup: dict[str, int] = {}
        try:
            checks.append(self.check_semantic_rag_quality())
            checks.append(self.check_business_flow_and_tenant_isolation())
        finally:
            cleanup = self._cleanup()
        all_required_pass = all(c.status == "PASS" for c in checks if c.required) and cleanup.get("cleanup_errors", 0) == 0
        return {
            "format": "careeros-business-certification-v1",
            "certification_version": "1.0-beta1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "environment": self.settings.app_env,
            "environment_fingerprint": runtime_environment_fingerprint(self.settings),
            "all_required_pass": all_required_pass,
            "checks": [asdict(c) for c in checks],
            "cleanup": cleanup,
        }
