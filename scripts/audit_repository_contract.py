from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PAIRS = [
    ("app/store.py", "SessionStore", "app/repositories/postgres/session.py", "PostgresSessionRepository"),
    ("app/auth_store.py", "AuthStore", "app/repositories/postgres/identity.py", "PostgresIdentityRepository"),
    ("app/artifact_store.py", "ArtifactStore", "app/repositories/postgres/artifact.py", "PostgresArtifactRepository"),
    ("app/evidence_store.py", "EvidenceStore", "app/repositories/postgres/evidence.py", "PostgresEvidenceRepository"),
    ("app/evidence_graph.py", "EvidenceGraphStore", "app/repositories/postgres/evidence_graph.py", "PostgresEvidenceGraphRepository"),
    ("app/workflow_store.py", "WorkflowStore", "app/repositories/postgres/workflow.py", "PostgresWorkflowRepository"),
    ("app/collaboration_store.py", "CollaborationStore", "app/repositories/postgres/collaboration.py", "PostgresCollaborationRepository"),
    ("app/knowledge.py", "KnowledgeStore", "app/repositories/postgres/knowledge.py", "PostgresKnowledgeRepository"),
    ("app/job_store.py", "JobStore", "app/repositories/postgres/jobs.py", "PostgresJobRepository"),
    ("app/model_store.py", "ModelConfigStore", "app/repositories/postgres/model.py", "PostgresModelConfigRepository"),
    ("app/commercial_store.py", "CommercialStore", "app/repositories/postgres/commercial.py", "PostgresCommercialRepository"),
    ("app/storage.py", "StorageRegistry", "app/repositories/postgres/storage_registry.py", "PostgresStorageRegistry"),
    ("app/unified_runtime_store.py", "UnifiedRuntimeStore", "app/repositories/postgres/unified_runtime.py", "PostgresUnifiedRuntimeRepository"),
    ("app/domain_intelligence.py", "DomainIntelligenceStore", "app/repositories/postgres/domain_intelligence.py", "PostgresDomainIntelligenceRepository"),
    ("app/repositories/interfaces/core.py", "ProjectRepositoryProtocol", "app/project_repository.py", "ProjectRepository"),
]


def public_methods(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                item.name
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and not item.name.startswith("_")
            }
    raise ValueError(f"class {class_name} not found in {path}")


def audit() -> dict:
    items = []
    ok = True
    for legacy_path, legacy_class, sa_path, sa_class in PAIRS:
        legacy = public_methods(ROOT / legacy_path, legacy_class)
        sqlalchemy = public_methods(ROOT / sa_path, sa_class)
        missing = sorted(legacy - sqlalchemy)
        ok = ok and not missing
        items.append({
            "legacy": legacy_class,
            "sqlalchemy": sa_class,
            "required_public_methods": sorted(legacy),
            "missing": missing,
            "extra": sorted(sqlalchemy - legacy),
        })
    return {"ok": ok, "pairs": len(items), "items": items}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit SQLite/PostgreSQL repository method parity.")
    parser.add_argument("--json-out", default="", help="Optional output path for the JSON report.")
    args = parser.parse_args()
    report = audit()
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    if args.json_out:
        output = Path(args.json_out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    raise SystemExit(0 if report["ok"] else 2)
