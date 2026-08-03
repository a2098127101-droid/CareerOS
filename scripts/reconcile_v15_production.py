from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN_REF = "origin/main"
LAUNCH_REF = "origin/codex/production-launch-hardening"


def git_show(ref: str, path: str) -> str:
    return subprocess.check_output(
        ["git", "show", f"{ref}:{path}"], cwd=ROOT, text=True, encoding="utf-8"
    )


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def copy(ref: str, path: str) -> None:
    write(path, git_show(ref, path))


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"required integration anchor missing in {path}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def regex_replace_once(path: str, pattern: str, replacement: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"required regex integration anchor missing in {path}: {pattern}")
    target.write_text(updated, encoding="utf-8")


def copy_project_and_launch_files() -> None:
    from_launch = (
        "app/project_models.py",
        "app/project_repository.py",
        "app/routers/projects.py",
        "app/static/projects.html",
        "app/static/student.html",
        "app/static/teacher.html",
        "app/static/governance.html",
        "app/static/production-workspaces.css",
        "scripts/build_production_release.py",
        "tests/test_production_launch_hardening.py",
        ".github/workflows/production-release-package.yml",
        "docs/PRODUCT_BENCHMARKS_2026.md",
        "deploy/README_PRODUCTION.md",
        "deploy/PRODUCTION_CHECKLIST.md",
    )
    for path in from_launch:
        copy(LAUNCH_REF, path)
    copy(MAIN_REF, "app/static/safe-navigation.js")
    copy(MAIN_REF, "tests/test_phase1_projects.py")


def patch_repository_container() -> None:
    path = "app/repositories/container.py"
    replace_once(
        path,
        "from ..domain_intelligence import DomainIntelligenceStore\n",
        "from ..domain_intelligence import DomainIntelligenceStore\nfrom ..project_repository import ProjectRepository\n",
    )
    replace_once(
        path,
        "    templates: TemplateRegistry\n    runtime_entities: object\n",
        "    templates: TemplateRegistry\n    projects: ProjectRepository\n    runtime_entities: object\n",
    )
    replace_once(
        path,
        "            templates=template_registry,\n            runtime_entities=UnifiedRuntimeStore(db_path),\n",
        "            templates=template_registry,\n            projects=ProjectRepository(engine),\n            runtime_entities=UnifiedRuntimeStore(db_path),\n",
    )
    replace_once(
        path,
        "            templates=template_registry,\n            runtime_entities=PostgresUnifiedRuntimeRepository(engine),\n",
        "            templates=template_registry,\n            projects=ProjectRepository(engine),\n            runtime_entities=PostgresUnifiedRuntimeRepository(engine),\n",
    )
    replace_once(
        path,
        '            "storage_registry": PostgresStorageRegistry(engine),\n            "runtime_entities": PostgresUnifiedRuntimeRepository(engine),\n',
        '            "storage_registry": PostgresStorageRegistry(engine),\n            "projects": ProjectRepository(engine),\n            "runtime_entities": PostgresUnifiedRuntimeRepository(engine),\n',
    )


def patch_repository_contracts() -> None:
    core = ROOT / "app/repositories/interfaces/core.py"
    text = core.read_text(encoding="utf-8")
    if "class ProjectRepositoryProtocol" not in text:
        text += '''\n\n@runtime_checkable\nclass ProjectRepositoryProtocol(Protocol):\n    def ensure_default_template(self, *, tenant_id: str, created_by: str = ...) -> dict[str, Any]: ...\n    def list_templates(self, *, tenant_id: str, published_only: bool = ...) -> list[dict[str, Any]]: ...\n    def get_template(self, template_id: str, *, tenant_id: str) -> dict[str, Any]: ...\n    def get_template_version(self, template_version_id: str, *, tenant_id: str) -> dict[str, Any]: ...\n    def create_project(self, *, tenant_id: str, owner_user_id: str, template_version_id: str, session_id: str, name: str = ...) -> dict[str, Any]: ...\n    def list_projects(self, *, tenant_id: str, owner_user_id: str, status: str | None = ...) -> list[dict[str, Any]]: ...\n    def get_project(self, project_id: str, *, tenant_id: str, owner_user_id: str) -> dict[str, Any]: ...\n    def save_answer(self, project_id: str, question_id: str, answer: Any, *, tenant_id: str, owner_user_id: str) -> dict[str, Any]: ...\n    def list_answers(self, project_id: str, *, tenant_id: str, owner_user_id: str) -> dict[str, Any]: ...\n'''
        core.write_text(text, encoding="utf-8")

    init_path = ROOT / "app/repositories/interfaces/__init__.py"
    text = init_path.read_text(encoding="utf-8")
    if "ProjectRepositoryProtocol" not in text:
        text = text.replace("    ModelUsageRepository,\n", "    ModelUsageRepository,\n    ProjectRepositoryProtocol,\n")
        text = text.replace('"ModelUsageRepository", ', '"ModelUsageRepository", "ProjectRepositoryProtocol", ')
        init_path.write_text(text, encoding="utf-8")

    audit_path = ROOT / "scripts/audit_repository_contract.py"
    text = audit_path.read_text(encoding="utf-8")
    project_pair = '    ("app/repositories/interfaces/core.py", "ProjectRepositoryProtocol", "app/project_repository.py", "ProjectRepository"),\n'
    if project_pair not in text:
        text = text.replace(
            '    ("app/domain_intelligence.py", "DomainIntelligenceStore", "app/repositories/postgres/domain_intelligence.py", "PostgresDomainIntelligenceRepository"),\n',
            '    ("app/domain_intelligence.py", "DomainIntelligenceStore", "app/repositories/postgres/domain_intelligence.py", "PostgresDomainIntelligenceRepository"),\n' + project_pair,
        )
        audit_path.write_text(text, encoding="utf-8")

    parity_path = ROOT / "app/repositories/parity.py"
    text = parity_path.read_text(encoding="utf-8")
    if '        "projects",\n' not in text:
        text = text.replace('        "storage_registry",\n', '        "storage_registry",\n        "projects",\n')
        parity_path.write_text(text, encoding="utf-8")


def patch_sqlite_migrations() -> None:
    target = ROOT / "app/migrations.py"
    text = target.read_text(encoding="utf-8")
    if "_migration_23_project_mvp_foundation" not in text:
        source = git_show(MAIN_REF, "app/migrations.py")
        match = re.search(
            r"def _migration_17_project_mvp_foundation\(conn: sqlite3\.Connection\) -> None:\n.*?(?=\n\nMIGRATIONS:)",
            source,
            flags=re.DOTALL,
        )
        if not match:
            raise RuntimeError("project SQLite migration source not found")
        function = match.group(0).replace(
            "_migration_17_project_mvp_foundation", "_migration_23_project_mvp_foundation", 1
        )
        text = text.replace("\n\nMIGRATIONS: list[Migration] = [", "\n\n" + function + "\n\nMIGRATIONS: list[Migration] = [", 1)
        text = text.replace(
            '    (22, "tenant_index_hardening", _migration_22_tenant_index_hardening),\n',
            '    (22, "tenant_index_hardening", _migration_22_tenant_index_hardening),\n'
            '    (23, "project_mvp_foundation", _migration_23_project_mvp_foundation),\n',
            1,
        )
        target.write_text(text, encoding="utf-8")


def merge_project_manifest() -> None:
    target = ROOT / "app/schema_manifest.json"
    manifest = json.loads(target.read_text(encoding="utf-8"))
    main_manifest = json.loads(git_show(MAIN_REF, "app/schema_manifest.json"))
    for table in (
        "project_templates",
        "project_template_versions",
        "project_instances",
        "project_answers",
    ):
        manifest["tables"][table] = main_manifest["tables"][table]
    manifest["version"] = "1.5-production-integration"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def patch_main() -> None:
    path = "app/main.py"
    replace_once(
        path,
        "from .routers.model_admin import build_model_admin_router\n",
        "from .routers.model_admin import build_model_admin_router\nfrom .routers.projects import build_projects_router\n",
    )
    replace_once(
        path,
        "template_registry = repositories.templates\nunified_runtime_store = repositories.runtime_entities\n",
        "template_registry = repositories.templates\nproject_repository = repositories.projects\nunified_runtime_store = repositories.runtime_entities\n",
    )
    replace_once(path, '"participant": "/participant"', '"participant": "/projects"')

    session_replacement = '''def _create_session_for_principal(principal: Principal) -> SessionState:\n    if principal.authenticated and canonical_role(principal.role) not in {"participant", "platform_admin"}:\n        raise HTTPException(status_code=403, detail="student account required to create a student session")\n    tenant_id = principal.tenant_id if principal.authenticated else settings.bootstrap_tenant_id\n    owner_user_id = (\n        principal.user_id\n        if (principal.authenticated and canonical_role(principal.role) == "participant")\n        or (not principal.authenticated and settings.demo_mode and principal.user_id == "demo-local")\n        else ""\n    )\n    class_id = "default"\n    if owner_user_id:\n        class_ids = sorted(auth_store.user_class_ids(owner_user_id, tenant_id, role="student"))\n        if class_ids:\n            class_id = class_ids[0]\n    state = store.create(tenant_id=tenant_id, student_user_id=owner_user_id, class_id=class_id, student_id=owner_user_id or "")\n    state.messages.append(ChatMessage(\n        role="assistant",\n        content="你好，我是 CareerOS AI Coach。你可以从目标方向、已有经历、技能、作品或当前困惑开始；信息不完整也没关系，我会先建立可验证画像，再逐步推进定位、能力差距、行动计划与成果物。",\n        action="welcome",\n    ))\n    store.save(state)\n    workflow_store.ensure(state, preset_id=_workflow_preset_id(state.tenant_id))\n    commercial_store.track(tenant_id=tenant_id, user_id=owner_user_id, session_id=state.session_id, event_name="session_created")\n    return state\n\n\n@app.post("/api/sessions", response_model=SessionState)\ndef create_session(principal: Principal = Depends(current_principal)):\n    return _create_session_for_principal(principal)\n\n\ndef _cleanup_project_session(session_id: str, tenant_id: str) -> None:\n    try:\n        workflow_store.delete_session(session_id, tenant_id=tenant_id)\n    finally:\n        store.delete_session(session_id, tenant_id=tenant_id)\n'''
    regex_replace_once(
        path,
        r'@app\.post\("/api/sessions", response_model=SessionState\)\ndef create_session\(principal: Principal = Depends\(current_principal\)\):\n.*?(?=\n\ndef get_state)',
        session_replacement,
    )

    replace_once(
        path,
        '''app.include_router(build_template_admin_router(\n    template_registry=template_registry,\n    admin_dependency=require_roles("school_admin"),\n))\n\n''',
        '''app.include_router(build_template_admin_router(\n    template_registry=template_registry,\n    admin_dependency=require_roles("school_admin"),\n))\n\napp.include_router(build_projects_router(\n    current_principal=current_principal,\n    project_repository=project_repository,\n    create_project_session=_create_session_for_principal,\n    cleanup_project_session=_cleanup_project_session,\n    allow_anonymous_demo=settings.demo_mode and not settings.auth_required,\n))\n\n''',
    )

    replace_once(
        path,
        '''@app.get("/participant")\n@app.get("/student")\ndef student_page(request: Request):\n''',
        '''@app.get("/projects")\n@app.get("/projects/new")\ndef projects_page(request: Request):\n    denied = _page_guard(request, {"student"})\n    return denied or FileResponse(STATIC_DIR / "projects.html")\n\n\n@app.get("/projects/{project_id}")\ndef project_detail_page(project_id: str, request: Request):\n    denied = _page_guard(request, {"student"})\n    return denied or FileResponse(STATIC_DIR / "projects.html")\n\n\n@app.get("/participant")\n@app.get("/student")\ndef student_page(request: Request):\n''',
    )


def patch_project_repository_quality() -> None:
    path = ROOT / "app/routers/projects.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'def _answer_is_empty(value: Any) -> bool:\n    return value is None or value == "" or value == [] or value == {}\n',
        'def _answer_is_empty(value: Any) -> bool:\n    if value is None or value == [] or value == {}:\n        return True\n    return isinstance(value, str) and not value.strip()\n',
    )
    text = text.replace(
        '        rates = pricing.get(key)\n        if rates is None:\n',
        '        rates = pricing.get(key)\n        if rates is None or (rates[0] <= 0 and rates[1] <= 0):\n',
    )
    path.write_text(text, encoding="utf-8")


def patch_tests_and_ci() -> None:
    phase = ROOT / "tests/test_phase1_projects.py"
    text = phase.read_text(encoding="utf-8")
    text = text.replace('migration_status(db_path)["current"] == 17', 'migration_status(db_path)["current"] == 23')
    text = text.replace('revision == "0008_project_mvp_foundation"', 'revision == "0012_project_tenant_rls"')
    text = text.replace(
        '(Path(__file__).parents[1] / "deploy" / "postgresql_baseline.sql").read_text(encoding="utf-8")',
        '(Path(__file__).parents[1] / "alembic" / "versions" / "0011_project_mvp_foundation.py").read_text(encoding="utf-8")',
    )
    phase.write_text(text, encoding="utf-8")

    data_test = ROOT / "tests/test_v10_alpha_data_foundation.py"
    if data_test.exists():
        text = data_test.read_text(encoding="utf-8")
        text = re.sub(r'assert version == "[^"]+"', 'assert version == "0012_project_tenant_rls"', text, count=1)
        data_test.write_text(text, encoding="utf-8")

    contract_test = ROOT / "tests/test_v10_alpha2_repository_contract.py"
    if contract_test.exists():
        text = contract_test.read_text(encoding="utf-8")
        text = re.sub(r'assert report\["pairs"\] == \d+', 'assert report["pairs"] == 15', text)
        if "ProjectRepositoryProtocol" not in text:
            text = text.replace(
                '    assert all(not item["missing"] for item in report["items"])',
                '    project = next(item for item in report["items"] if item["legacy"] == "ProjectRepositoryProtocol")\n'
                '    assert project["missing"] == []\n'
                '    assert all(not item["missing"] for item in report["items"])',
            )
        contract_test.write_text(text, encoding="utf-8")

    parity_test = ROOT / "tests/test_v10_alpha2_repository_parity.py"
    if parity_test.exists():
        text = parity_test.read_text(encoding="utf-8")
        if 'assert "projects" in CORE_PARITY.complete' not in text:
            text = text.replace(
                '    assert "knowledge" in CORE_PARITY.complete\n',
                '    assert "knowledge" in CORE_PARITY.complete\n    assert "projects" in CORE_PARITY.complete\n',
            )
        parity_test.write_text(text, encoding="utf-8")

    ci = ROOT / ".github/workflows/ci.yml"
    text = ci.read_text(encoding="utf-8")
    marker = "      - run: python -m compileall -q app scripts tests alembic\n"
    addition = marker + '''      - name: Validate deployment shell scripts\n        run: bash -n deploy/postgres/init-app-role.sh deploy/scripts/*.sh\n      - name: Validate production compose model\n        run: |\n          cp deploy/.env.production.example deploy/.env.production\n          docker compose --env-file deploy/.env.production -f deploy/docker-compose.production.yml config --quiet\n          rm -f deploy/.env.production\n'''
    if "Validate production compose model" not in text:
        if marker not in text:
            raise RuntimeError("CI compile anchor missing")
        text = text.replace(marker, addition, 1)
    ci.write_text(text, encoding="utf-8")


def patch_release_manifest_requirements() -> None:
    path = ROOT / "scripts/build_production_release.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        '"deploy/docker-compose.production.yml",\n',
        '"deploy/docker-compose.production.yml",\n    "alembic/versions/0012_project_tenant_rls.py",\n',
    )
    path.write_text(text, encoding="utf-8")


def main() -> None:
    copy_project_and_launch_files()
    patch_repository_container()
    patch_repository_contracts()
    patch_sqlite_migrations()
    merge_project_manifest()
    patch_main()
    patch_project_repository_quality()
    patch_tests_and_ci()
    patch_release_manifest_requirements()
    subprocess.run(["python", "-m", "compileall", "-q", "app", "scripts", "tests", "alembic"], cwd=ROOT, check=True)
    print("v1.5 production integration reconciliation completed")


if __name__ == "__main__":
    main()
