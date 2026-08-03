from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOMAIN_REF = "origin/agent/release-v1.5-domain-intelligence"
STATIC = ROOT / "app" / "static"


def run(*args: str) -> None:
    subprocess.run(list(args), cwd=ROOT, check=True, text=True, encoding="utf-8")


def replace(path: Path, old: str, new: str, *, required: bool = True) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if required:
            raise RuntimeError(f"regression-fix anchor missing: {path}: {old[:120]!r}")
        return
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def restore_test_dependency_lock() -> None:
    # PR #8 introduced async provider tests and the corresponding fully hashed lock entry.
    run("git", "checkout", DOMAIN_REF, "--", "requirements.lock")


def add_i18n_to_focused_workspaces() -> None:
    for name in ("projects.html", "student.html", "teacher.html", "governance.html"):
        path = STATIC / name
        text = path.read_text(encoding="utf-8")
        if "/static/i18n.js" in text:
            continue
        anchor = '<script src="/static/vendor/lucide.min.js"></script>'
        if anchor not in text:
            raise RuntimeError(f"i18n script anchor missing in {name}")
        path.write_text(
            text.replace(anchor, anchor + '<script src="/static/i18n.js"></script>', 1),
            encoding="utf-8",
        )


def rewrite_ui_contract() -> None:
    path = ROOT / "tests" / "test_ui_interaction_contract.py"
    source = path.read_text(encoding="utf-8")
    tail_anchor = "def test_workspace_module_contract_and_interaction_apis"
    if tail_anchor not in source:
        raise RuntimeError("workspace API contract test anchor missing")
    tail = tail_anchor + source.split(tail_anchor, 1)[1]
    header = '''from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
STATIC = ROOT / "app" / "static"


def test_student_workspace_is_project_first_and_bound_to_real_apis():
    html = (STATIC / "student.html").read_text(encoding="utf-8")
    projects = (STATIC / "projects.html").read_text(encoding="utf-8")
    for token in (
        "Project Copilot", "params.get('project_id')", "params.get('session_id')",
        "/api/chat", "/api/files/parse", "/milestone?milestone=",
        "currentArtifactText", "downloadArtifact", "completeProject",
    ):
        assert token in html
    for token in (
        "/api/v1/me/next-action", "/api/v1/project-templates",
        "/api/v1/projects", "保存并判断下一步", "只处理当前最重要的任务",
    ):
        assert token in projects
    # The contracted student flow is intentionally reduced; the old feature-catalogue
    # navigation must not be reintroduced as the primary workspace.
    assert "data-student-view" not in html
    assert "student-workspace.js" not in html


def test_teacher_workspace_is_an_intervention_queue_with_real_actions():
    html = (STATIC / "teacher.html").read_text(encoding="utf-8")
    for token in (
        "教师运营中心", "干预队列", "/api/v1/advisor/operations",
        "/api/teacher/dashboard", "/api/teacher/sessions/", "/api/tasks",
        "/feedback", "/note", "createReminder", "priorityClass",
    ):
        assert token in html
    assert "data-teacher-view" not in html
    assert "teacher-workspace.js" not in html


def test_global_i18n_and_admin_configuration_contracts():
    i18n = (STATIC / "i18n.js").read_text(encoding="utf-8")
    admin_html = (STATIC / "admin.html").read_text(encoding="utf-8")
    extension = (STATIC / "admin-extension.js").read_text(encoding="utf-8")
    for page in (
        "index.html", "login.html", "projects.html", "student.html",
        "teacher.html", "governance.html", "admin.html",
    ):
        html = (STATIC / page).read_text(encoding="utf-8")
        assert "/static/i18n.js" in html, page
    for token in ("careeros_locale", "globe-2", "MutationObserver", "careeros:localechange", "en-US"):
        assert token in i18n
    assert 'data-tab="templates"' in admin_html
    assert 'data-tab="access"' in admin_html
    for endpoint in (
        "/api/admin/templates/workflows", "/api/admin/templates/artifacts",
        "/api/admin/users", "/role", "/status",
    ):
        assert endpoint in extension
    assert "workspace-select" in extension


'''
    path.write_text(header + tail, encoding="utf-8")


def update_migration_contracts() -> None:
    phase = ROOT / "tests" / "test_phase1_projects.py"
    text = phase.read_text(encoding="utf-8")
    old = '''def test_generated_postgres_baseline_includes_project_security_triggers():
    baseline = (Path(__file__).parents[1] / "alembic" / "versions" / "0011_project_mvp_foundation.py").read_text(encoding="utf-8")
    assert "CREATE TRIGGER trg_project_template_versions_immutable" in baseline
    assert "CREATE TRIGGER trg_project_instances_tenant_guard" in baseline
    assert "CREATE TRIGGER trg_project_answers_tenant_guard" in baseline
    assert "student_user_id=NEW.owner_user_id" in baseline'''
    new = '''def test_project_migration_installs_immutable_and_tenant_guard_triggers():
    migration = (Path(__file__).parents[1] / "alembic" / "versions" / "0011_project_mvp_foundation.py").read_text(encoding="utf-8")
    assert "CREATE TRIGGER trg_project_template_versions_immutable" in migration
    assert 'for table in ("project_template_versions", "project_instances", "project_answers")' in migration
    assert 'f"CREATE TRIGGER {trigger} BEFORE INSERT OR UPDATE ON {table} "' in migration
    assert "student_user_id=NEW.owner_user_id" in migration'''
    if old not in text:
        raise RuntimeError("project trigger contract anchor missing")
    phase.write_text(text.replace(old, new, 1), encoding="utf-8")

    domain = ROOT / "tests" / "test_v15_domain_intelligence.py"
    replace(domain, 'assert migration_status(db)["current"] == 22', 'assert migration_status(db)["current"] == 23')

    hardening = ROOT / "tests" / "test_v15_release_hardening.py"
    replace(
        hardening,
        'assert version == "0010_immutable_runtime_tenant_hardening"',
        'assert version == "0012_project_tenant_rls"',
    )


def main() -> None:
    restore_test_dependency_lock()
    add_i18n_to_focused_workspaces()
    rewrite_ui_contract()
    update_migration_contracts()
    run("python", "-m", "compileall", "-q", "app", "scripts", "tests", "alembic")
    print("v1.5 integration regression contracts updated")


if __name__ == "__main__":
    main()
