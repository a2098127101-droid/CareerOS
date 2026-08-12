from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api_versioning import _api_routes
from app.learner_agent.models import AgentAction
from app.learner_agent.tools import LearnerAgentTools
from app.main import app


REQUIRED = {
    ("GET", "/api/learner-agent/v1/manifest"),
    ("GET", "/api/learner-agent/v1/tools"),
    ("GET", "/api/learner-agent/v1/state"),
    ("GET", "/api/learner-agent/v1/memory"),
    ("GET", "/api/learner-agent/v1/decisions"),
    ("GET", "/api/learner-agent/v1/trajectory"),
    ("POST", "/api/learner-agent/v1/trajectory/{event_id}/label"),
    ("GET", "/api/learner-agent/v1/calibration"),
    ("POST", "/api/learner-agent/v1/calibration/refresh"),
    ("POST", "/api/learner-agent/v1/calibration/activate"),
    ("POST", "/api/learner-agent/v1/observe"),
    ("POST", "/api/learner-agent/v1/step"),
    ("POST", "/api/learner-agent/v1/evaluate"),
}


def route_contract() -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for route in _api_routes(app.router.routes):
        for method in route.methods or set():
            out.add((method, route.path))
    return out


def main() -> int:
    missing = sorted(REQUIRED - route_contract())
    if missing:
        print("LEARNER_AGENT_CONTRACT_MISSING")
        for method, path in missing:
            print(f"- {method} {path}")
        return 1
    required_components = {
        "state.py", "policy.py", "tools.py", "memory.py", "runtime.py", "evaluation.py", "registration.py",
        "trajectory.py", "calibration.py", "bridge.py",
    }
    existing = {p.name for p in (ROOT / "app" / "learner_agent").glob("*.py")}
    missing_components = required_components - existing
    if missing_components:
        print("LEARNER_AGENT_COMPONENTS_MISSING", sorted(missing_components))
        return 1
    if len(AgentAction) != 11:
        print("LEARNER_AGENT_ACTION_CONTRACT_CHANGED", len(AgentAction))
        return 1
    if len(LearnerAgentTools.CONTRACT) != 8:
        print("LEARNER_AGENT_TOOL_CONTRACT_CHANGED", len(LearnerAgentTools.CONTRACT))
        return 1
    for path in ["runtime.py", "trajectory.py", "calibration.py", "bridge.py"]:
        text = (ROOT / "app" / "learner_agent" / path).read_text(encoding="utf-8")
        if "sys.modules" in text or "app.main" in text or "sqlite3" in text:
            print("LEARNER_AGENT_COUPLING_VIOLATION", path)
            return 1
    tools_text = (ROOT / "app" / "learner_agent" / "tools.py").read_text(encoding="utf-8")
    if "sqlite3" in tools_text or "mark_capability_mastered" in tools_text or "generate_final_answer" in tools_text:
        print("LEARNER_AGENT_TOOL_BOUNDARY_VIOLATION")
        return 1
    print(
        f"LEARNER_AGENT_CONTRACT_OK routes={len(REQUIRED)} actions={len(AgentAction)} "
        f"tools={len(LearnerAgentTools.CONTRACT)} trajectory=on calibration=human-activated"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
