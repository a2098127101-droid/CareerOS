from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

from app.embedding_gateway import EmbeddingConfig, EmbeddingGateway
from app.migrations import migration_status, run_migrations
from app.project_repository import ProjectRepository, ProjectVersionConflict
from app.repositories.container import RepositoryContainer


def build_repositories(tmp_path: Path):
    db_path = str(tmp_path / "projects.db")
    run_migrations(db_path)
    repos = RepositoryContainer.build_sqlite(
        db_path=db_path,
        app_secret_key="x" * 40,
        session_ttl_hours=24,
        embedding_gateway=EmbeddingGateway(EmbeddingConfig()),
    )
    return db_path, repos


def test_migration_17_is_additive_and_template_versions_are_db_immutable(tmp_path: Path):
    db_path, repos = build_repositories(tmp_path)
    repos.identity.ensure_tenant("school-a", "School A")
    template = repos.projects.ensure_default_template(tenant_id="school-a")
    assert migration_status(db_path)["current"] == 23
    with sqlite3.connect(db_path) as conn:
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'project_%'"
            )
        }
        assert {
            "project_templates",
            "project_template_versions",
            "project_instances",
            "project_answers",
        }.issubset(names)
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute(
                "UPDATE project_template_versions SET name='mutated' WHERE template_version_id=?",
                (template["template_version_id"],),
            )
        triggers = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'trg_project_%'"
            )
        }
        assert "trg_project_instances_tenant_guard_update" in triggers
        assert "trg_project_answers_owner_guard_update" in triggers


def test_default_template_is_stable_with_single_connection_pool(tmp_path: Path):
    db_path = str(tmp_path / "single-pool.db")
    run_migrations(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO tenants(tenant_id,name,product_preset)
            VALUES('single-pool','Single Pool','career_development')"""
        )
        conn.commit()
    engine = create_engine(
        f"sqlite:///{Path(db_path).as_posix()}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=1,
        max_overflow=0,
        pool_timeout=0.25,
        future=True,
    )
    try:
        projects = ProjectRepository(engine)
        for _ in range(12):
            current = projects.ensure_default_template(tenant_id="single-pool")
            assert projects.list_templates(tenant_id="single-pool")[0]["current_version_id"] == current[
                "template_version_id"
            ]
            assert projects.get_template(
                current["template_id"], tenant_id="single-pool"
            )["template_version_id"] == current["template_version_id"]
    finally:
        engine.dispose()


def test_project_repository_enforces_tenant_owner_and_snapshot_binding(tmp_path: Path):
    _, repos = build_repositories(tmp_path)
    repos.identity.ensure_tenant("school-a", "School A")
    repos.identity.ensure_tenant("school-b", "School B")
    template_a = repos.projects.ensure_default_template(tenant_id="school-a")
    template_b = repos.projects.ensure_default_template(tenant_id="school-b")
    assert template_a["template_version_id"] != template_b["template_version_id"]

    session = repos.sessions.create(
        tenant_id="school-a", student_user_id="student-a", class_id="default", student_id="student-a"
    )
    workflow = repos.workflows.ensure(session, preset_id="career_development")
    assert workflow["template_id"] == template_a["workflow_template_id"] == "career_development_v1"
    wrong_tenant_session = repos.sessions.create(
        tenant_id="school-b", student_user_id="student-a", class_id="default", student_id="student-a"
    )
    wrong_owner_session = repos.sessions.create(
        tenant_id="school-a", student_user_id="student-b", class_id="default", student_id="student-b"
    )
    mismatched_workflow_session = repos.sessions.create(
        tenant_id="school-a", student_user_id="student-a", class_id="default", student_id="student-a"
    )
    repos.workflows.ensure(mismatched_workflow_session, preset_id="campus_career")
    with pytest.raises(ValueError, match="does not exist"):
        repos.projects.create_project(
            tenant_id="school-a",
            owner_user_id="student-a",
            template_version_id=template_a["template_version_id"],
            session_id="missing-session",
        )
    for invalid_session in (wrong_tenant_session, wrong_owner_session):
        with pytest.raises(ValueError, match="tenant or owner mismatch"):
            repos.projects.create_project(
                tenant_id="school-a",
                owner_user_id="student-a",
                template_version_id=template_a["template_version_id"],
                session_id=invalid_session.session_id,
            )
    with pytest.raises(ValueError, match="workflow does not match"):
        repos.projects.create_project(
            tenant_id="school-a",
            owner_user_id="student-a",
            template_version_id=template_a["template_version_id"],
            session_id=mismatched_workflow_session.session_id,
        )
    project = repos.projects.create_project(
        tenant_id="school-a",
        owner_user_id="student-a",
        template_version_id=template_a["template_version_id"],
        session_id=session.session_id,
        name="我的职业发展项目",
    )
    assert project["template_version_id"] == template_a["template_version_id"]
    assert project["template_version"] == 1
    assert len(project["progress"]["steps"]) == 5

    with pytest.raises(KeyError):
        repos.projects.get_project(project["project_id"], tenant_id="school-a", owner_user_id="student-b")
    with pytest.raises(KeyError):
        repos.projects.get_project(project["project_id"], tenant_id="school-b", owner_user_id="student-a")
    with pytest.raises(KeyError):
        repos.projects.get_template(template_a["template_id"], tenant_id="school-b")

    repos.projects.save_answer(
        project["project_id"],
        "Q-001",
        "大二",
        tenant_id="school-a",
        owner_user_id="student-a",
    )
    assert repos.projects.get_project(
        project["project_id"], tenant_id="school-a", owner_user_id="student-a"
    )["answers"] == {"Q-001": "大二"}
    with sqlite3.connect(repos.projects.engine.url.database) as conn:
        insert_sql = """INSERT INTO project_instances(
            project_id,tenant_id,owner_user_id,template_id,template_version_id,session_id,name
        ) VALUES(?,?,?,?,?,?,?)"""
        with pytest.raises(sqlite3.IntegrityError, match="tenant, owner or session mismatch"):
            conn.execute(
                insert_sql,
                (
                    "PRJ-DIRECT-BAD-SESSION",
                    "school-a",
                    "student-a",
                    template_a["template_id"],
                    template_a["template_version_id"],
                    wrong_tenant_session.session_id,
                    "bad",
                ),
            )
        with pytest.raises(sqlite3.IntegrityError, match="tenant, owner or session mismatch"):
            conn.execute(
                insert_sql,
                (
                    "PRJ-DIRECT-BAD-TEMPLATE",
                    "school-a",
                    "student-a",
                    template_b["template_id"],
                    template_b["template_version_id"],
                    session.session_id,
                    "bad",
                ),
            )
        with pytest.raises(sqlite3.IntegrityError, match="tenant, owner or session mismatch"):
            conn.execute(
                "UPDATE project_instances SET owner_user_id='student-b' WHERE project_id=?",
                (project["project_id"],),
            )
        with pytest.raises(sqlite3.IntegrityError, match="tenant or owner mismatch"):
            conn.execute(
                "UPDATE project_answers SET owner_user_id='student-b' WHERE project_id=?",
                (project["project_id"],),
            )


def test_alembic_fresh_database_reaches_project_head(tmp_path: Path):
    db_path = tmp_path / "alembic-projects.db"
    env = os.environ.copy()
    env["ALEMBIC_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=Path(__file__).parents[1],
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    with sqlite3.connect(db_path) as conn:
        revision = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        triggers = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'trg_project_%'"
            )
        }
    assert revision == "0012_project_tenant_rls"
    assert "trg_project_template_versions_immutable_update" in triggers
    assert "trg_project_instances_tenant_guard_update" in triggers
    assert "trg_project_answers_owner_guard_update" in triggers


def test_project_api_login_redirect_create_list_detail_and_isolation(tmp_path: Path):
    code = r'''
from fastapi.testclient import TestClient
from app.main import app, auth_store

student = TestClient(app)
assert student.get('/projects', follow_redirects=False).status_code == 302
login = student.post('/api/auth/login', json={'email':'student@demo.local','password':'CareerOS-Demo-123!','role':'student'})
assert login.status_code == 200, login.text
assert login.json()['redirect'] == '/projects'
assert student.get('/projects').status_code == 200
templates = student.get('/api/v1/project-templates')
assert templates.status_code == 200, templates.text
template = templates.json()['items'][0]
created = student.post('/api/v1/projects', json={'template_version_id':template['current_version_id'],'name':'Project A'})
assert created.status_code == 201, created.text
project = created.json()
assert project['owner_user_id']
assert student.get('/api/v1/projects').json()['items'][0]['project_id'] == project['project_id']
detail = student.get('/api/v1/projects/'+project['project_id'])
assert detail.status_code == 200 and detail.json()['template_version_id'] == template['current_version_id']
form = student.get('/api/v1/projects/'+project['project_id']+'/form')
assert len(form.json()['questions']) == 16
saved = student.put('/api/v1/projects/'+project['project_id']+'/answers',json={'answers':[{'question_id':'Q-001','answer':'大二'}]})
assert saved.status_code == 200 and saved.json()['answers']['Q-001'] == '大二'

second_user = auth_store.ensure_user(email='student2@test.local',password='CareerOS-Test-Second-123!',display_name='Student 2',tenant_id=project['tenant_id'],role='student')
other = TestClient(app)
assert other.post('/api/auth/login',json={'email':'student2@test.local','password':'CareerOS-Test-Second-123!','role':'student'}).status_code == 200
assert other.get('/api/v1/projects/'+project['project_id']).status_code == 404
assert other.get('/api/v1/projects').json()['items'] == []

teacher = TestClient(app)
assert teacher.post('/api/auth/login',json={'email':'teacher@demo.local','password':'CareerOS-Demo-123!','role':'teacher'}).status_code == 200
assert teacher.get('/api/v1/projects').status_code == 403
assert teacher.post('/api/v1/projects',json={'template_version_id':template['current_version_id']}).status_code == 403

for email,role in [('admin@demo.local','school_admin'),('super@demo.local','super_admin')]:
    admin = TestClient(app)
    assert admin.post('/api/auth/login',json={'email':email,'password':'CareerOS-Demo-123!','role':role}).status_code == 200
    assert admin.post('/api/v1/projects',json={'template_version_id':template['current_version_id']}).status_code == 403
print('PROJECT_API_OK')
'''
    env = os.environ.copy()
    env.update(
        {
            "APP_DB_PATH": str(tmp_path / "project-api.db"),
            "DEMO_MODE": "true",
            "AUTH_REQUIRED": "true",
            "AUTO_SEED_DEMO_USERS": "true",
            "APP_SECRET_KEY": "test-secret-123456789012345678901234567890",
            "APP_ENV": "development",
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).parents[1],
        env=env,
        text=True,
        capture_output=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "PROJECT_API_OK" in result.stdout


def test_default_local_demo_projects_are_usable_without_weakening_production_roles(tmp_path: Path):
    code = r'''
from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)
assert client.get('/projects').status_code == 200
templates=client.get('/api/v1/project-templates')
assert templates.status_code == 200,templates.text
template=templates.json()['items'][0]
created=client.post('/api/v1/projects',json={'template_version_id':template['current_version_id'],'name':'Demo Project'})
assert created.status_code == 201,created.text
project=created.json()
assert project['owner_user_id']=='demo-local'
assert project['template']['workflow_template_id']=='career_development_v1'
assert client.get('/api/v1/projects/'+project['project_id']).status_code == 200
print('DEFAULT_DEMO_PROJECT_OK')
'''
    env = os.environ.copy()
    env.update(
        {
            "APP_DB_PATH": str(tmp_path / "default-demo-project.db"),
            "DEMO_MODE": "true",
            "AUTH_REQUIRED": "false",
            "APP_SECRET_KEY": "test-secret-123456789012345678901234567890",
            "APP_ENV": "development",
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).parents[1],
        env=env,
        text=True,
        capture_output=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "DEFAULT_DEMO_PROJECT_OK" in result.stdout


def test_project_api_resolves_real_workflow_for_each_tenant_preset(tmp_path: Path):
    code = r'''
from fastapi.testclient import TestClient
from app.main import app,auth_store,workflow_store
expected={
 'career_development':'career_development_v1',
 'campus_career':'campus_career_v1',
 'career_service':'career_service_v1',
 'career_competition':'career_competition_v1',
 'enterprise_talent':'enterprise_talent_v1',
}
created_ids={}
for index,(preset,workflow_id) in enumerate(expected.items()):
    tenant='preset-'+preset
    auth_store.ensure_tenant(tenant,tenant,product_preset=preset)
    email=f'{preset}@test.local'
    password='CareerOS-Preset-Test-123!'
    auth_store.create_user(email=email,password=password,display_name=preset,tenant_id=tenant,role='student')
    client=TestClient(app)
    login=client.post('/api/auth/login',json={'email':email,'password':password,'tenant_id':tenant,'role':'student'})
    assert login.status_code==200,login.text
    templates=client.get('/api/v1/project-templates')
    assert templates.status_code==200,templates.text
    template=templates.json()['items'][0]
    detail=client.get('/api/v1/project-templates/'+template['template_id']).json()
    assert detail['workflow_template_id']==workflow_id,(preset,detail)
    created=client.post('/api/v1/projects',json={'template_version_id':template['current_version_id'],'name':preset})
    assert created.status_code==201,created.text
    project=created.json()
    assert project['template']['workflow_template_id']==workflow_id
    assert workflow_store.snapshot(project['session_id'],tenant_id=tenant)['template_id']==workflow_id
    created_ids[preset]=project['project_id']
assert len(set(created_ids.values()))==len(expected)
print('MULTI_PRESET_PROJECT_OK')
'''
    env = os.environ.copy()
    env.update(
        {
            "APP_DB_PATH": str(tmp_path / "multi-preset-project.db"),
            "DEMO_MODE": "true",
            "AUTH_REQUIRED": "true",
            "AUTO_SEED_DEMO_USERS": "false",
            "APP_SECRET_KEY": "test-secret-123456789012345678901234567890",
            "APP_ENV": "development",
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).parents[1],
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "MULTI_PRESET_PROJECT_OK" in result.stdout


def test_wrong_legacy_template_version_is_preserved_and_superseded(tmp_path: Path):
    db_path, repos = build_repositories(tmp_path)
    repos.identity.ensure_tenant("school-upgrade", "School Upgrade", product_preset="campus_career")
    template_id, wrong_version_id = repos.projects._default_ids("school-upgrade")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO project_templates(
            template_id,tenant_id,name,category,status,current_version_id,created_by
            ) VALUES(?,?,?,'职业发展规划','published',?,'legacy')""",
            (template_id, "school-upgrade", "个人职业发展规划", wrong_version_id),
        )
        conn.execute(
            """INSERT INTO project_template_versions(
            template_version_id,template_id,tenant_id,version,name,category,description,background,
            objective,applicable_users,estimated_time_minutes,output_type,questions_json,
            material_requirements_json,artifact_structure_json,rubric_json,workflow_template_id,
            artifact_template_id,status,published_at
            ) VALUES(?,?,?,1,?,?,'','','','',60,'career_report','[]','[]','[]','{}',
            'project_mvp_5step_v1','career_report_v1','published',CURRENT_TIMESTAMP)""",
            (
                wrong_version_id,
                template_id,
                "school-upgrade",
                "个人职业发展规划",
                "职业发展规划",
            ),
        )
        conn.commit()

    session = repos.sessions.create(
        tenant_id="school-upgrade",
        student_user_id="legacy-student",
        class_id="default",
        student_id="legacy-student",
    )
    repos.workflows.ensure(session, preset_id="campus_career")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO project_instances(
            project_id,tenant_id,owner_user_id,template_id,template_version_id,session_id,name
            ) VALUES('PRJ-LEGACY','school-upgrade','legacy-student',?,?,?,'Legacy Project')""",
            (template_id, wrong_version_id, session.session_id),
        )
        conn.commit()

    current = repos.projects.ensure_default_template(tenant_id="school-upgrade")
    assert current["version"] == 2
    assert current["workflow_template_id"] == "campus_career_v1"
    assert current["template_version_id"] != wrong_version_id
    with sqlite3.connect(db_path) as conn:
        legacy = conn.execute(
            """SELECT version,workflow_template_id FROM project_template_versions
            WHERE template_version_id=?""",
            (wrong_version_id,),
        ).fetchone()
        versions = conn.execute(
            """SELECT version,workflow_template_id FROM project_template_versions
            WHERE template_id=? ORDER BY version""",
            (template_id,),
        ).fetchall()
    assert legacy == (1, "project_mvp_5step_v1")
    assert versions == [(1, "project_mvp_5step_v1"), (2, "campus_career_v1")]
    historical = repos.projects.get_project(
        "PRJ-LEGACY", tenant_id="school-upgrade", owner_user_id="legacy-student"
    )
    assert historical["template_version_id"] == wrong_version_id
    assert historical["template"]["workflow_template_id"] == "project_mvp_5step_v1"
    with pytest.raises(ProjectVersionConflict, match="not current"):
        repos.projects.create_project(
            tenant_id="school-upgrade",
            owner_user_id="legacy-student",
            template_version_id=wrong_version_id,
            session_id=session.session_id,
            name="Must not use archived version",
        )


def test_project_api_rejects_old_version_but_keeps_historical_project_readable(tmp_path: Path):
    code = r'''
from fastapi.testclient import TestClient
from app.main import app,auth_store

tenant='version-upgrade-school'
email='version-upgrade@test.local'
password='CareerOS-Version-Test-123!'
auth_store.ensure_tenant(tenant,tenant,product_preset='career_development')
auth_store.create_user(email=email,password=password,display_name='Version User',tenant_id=tenant,role='student')
client=TestClient(app)
assert client.post('/api/auth/login',json={'email':email,'password':password,'tenant_id':tenant,'role':'student'}).status_code==200
old_template=client.get('/api/v1/project-templates').json()['items'][0]
old_version=old_template['current_version_id']
old_created=client.post('/api/v1/projects',json={'template_version_id':old_version,'name':'Historical V1'})
assert old_created.status_code==201,old_created.text
old_project_id=old_created.json()['project_id']

auth_store.ensure_tenant(tenant,tenant,product_preset='campus_career')
new_template=client.get('/api/v1/project-templates').json()['items'][0]
new_version=new_template['current_version_id']
assert new_version!=old_version
rejected=client.post('/api/v1/projects',json={'template_version_id':old_version,'name':'Archived ID'})
assert rejected.status_code==409,rejected.text
assert rejected.json()['detail']=='project template version is not current'
assert client.get('/api/v1/projects/'+old_project_id).status_code==200
created=client.post('/api/v1/projects',json={'template_version_id':new_version,'name':'Current V2'})
assert created.status_code==201,created.text
print('OLD_VERSION_CONFLICT_OK')
'''
    env = os.environ.copy()
    env.update(
        {
            "APP_DB_PATH": str(tmp_path / "old-version-api.db"),
            "DEMO_MODE": "true",
            "AUTH_REQUIRED": "true",
            "AUTO_SEED_DEMO_USERS": "false",
            "APP_SECRET_KEY": "test-secret-123456789012345678901234567890",
            "APP_ENV": "development",
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).parents[1],
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "OLD_VERSION_CONFLICT_OK" in result.stdout


def test_login_next_rejects_external_and_backslash_redirects():
    root = Path(__file__).parents[1]
    script = root / "app" / "static" / "safe-navigation.js"
    code = r"""
const nav=require(process.argv[1]);
const origin='https://careeros.example';
const accepted=['/projects','/projects/new?from=login#start'];
const rejected=['//evil.example/path','/\\evil.example/path','/%5Cevil.example/path','/%2F%2Fevil.example/path','https://evil.example/path','javascript:alert(1)'];
for(const value of accepted){if(!nav.safeSameOriginPath(value,origin))throw new Error('rejected safe path '+value)}
for(const value of rejected){if(nav.safeSameOriginPath(value,origin))throw new Error('accepted unsafe path '+value)}
"""
    result = subprocess.run(
        ["node", "-e", code, str(script)],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_project_detail_uses_real_form_and_does_not_bypass_to_legacy_coach():
    html = (Path(__file__).parents[1] / "app" / "static" / "projects.html").read_text(encoding="utf-8")
    assert "继续填写" in html
    assert "saveProject" in html
    assert "/answers',{method:'PUT'" in html
    assert "进入 Project Copilot" not in html
    assert "/student?project_id=" not in html


def test_project_migration_installs_immutable_and_tenant_guard_triggers():
    migration = (Path(__file__).parents[1] / "alembic" / "versions" / "0011_project_mvp_foundation.py").read_text(encoding="utf-8")
    assert "CREATE TRIGGER trg_project_template_versions_immutable" in migration
    assert 'for table in ("project_template_versions", "project_instances", "project_answers")' in migration
    assert 'f"CREATE TRIGGER {trigger} BEFORE INSERT OR UPDATE ON {table} "' in migration
    assert "student_user_id=NEW.owner_user_id" in migration
