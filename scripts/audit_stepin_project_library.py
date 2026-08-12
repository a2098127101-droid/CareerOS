from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.project_repository import DEFAULT_TEMPLATE, PROJECT_LIBRARY_VERSION, ProjectRepository


def main() -> int:
    questions = " ".join(str(row.get("question_text") or "") for row in DEFAULT_TEMPLATE.get("questions") or [])
    forbidden = [token for token in ("目标岗位", "职业方向", "职业测评") if token in questions]
    rubric = ProjectRepository._latest_rubric()
    meta = rubric.get("_stepin_library") or {}
    errors = []
    if PROJECT_LIBRARY_VERSION != "2.2.0":
        errors.append(f"unexpected library version: {PROJECT_LIBRARY_VERSION}")
    if DEFAULT_TEMPLATE.get("name") != "真实任务综合实践":
        errors.append("default template is not practice-first")
    if DEFAULT_TEMPLATE.get("artifact_template_id") != "portfolio_v1":
        errors.append("default template must produce a portable practice artifact")
    if forbidden:
        errors.append("job-first questions remain: " + ",".join(forbidden))
    if meta.get("version") != PROJECT_LIBRARY_VERSION or not meta.get("agent_observable"):
        errors.append("library version/agent-observable marker missing")
    if len(DEFAULT_TEMPLATE.get("questions") or []) < 10:
        errors.append("practice project is too thin")
    if errors:
        print("STEPIN_PROJECT_LIBRARY_AUDIT_FAILED")
        for error in errors:
            print("-", error)
        return 1
    print(
        f"STEPIN_PROJECT_LIBRARY_OK version={PROJECT_LIBRARY_VERSION} "
        f"questions={len(DEFAULT_TEMPLATE['questions'])} artifact={DEFAULT_TEMPLATE['artifact_template_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
