from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from .workflow_templates import get_workflow_template


PROJECT_STATUSES = {
    "draft",
    "collecting",
    "ready_to_generate",
    "solution_generated",
    "reviewed",
    "revision_required",
    "completed",
}


class ProjectVersionConflict(ValueError):
    """The selected immutable template version is no longer current for new projects."""


DEFAULT_QUESTIONS = [
    {"question_id": "Q-001", "group_id": "basic", "question_text": "你的当前身份或学习阶段是什么？", "question_type": "single_select", "required": True, "options": ["大一", "大二", "大三", "大四", "研究生", "应届毕业", "其他"], "display_order": 1, "artifact_sections": ["个人现状"]},
    {"question_id": "Q-002", "group_id": "basic", "question_text": "你的专业或主要背景是什么？", "question_type": "short_text", "required": True, "display_order": 2, "artifact_sections": ["个人现状"]},
    {"question_id": "Q-003", "group_id": "basic", "question_text": "你希望发展的职业方向是什么？", "question_type": "short_text", "required": True, "display_order": 3, "artifact_sections": ["职业目标"]},
    {"question_id": "Q-004", "group_id": "basic", "question_text": "你是否已经确定具体目标岗位？", "question_type": "single_select", "required": True, "options": ["是", "否", "正在探索"], "display_order": 4, "artifact_sections": ["职业目标"]},
    {"question_id": "Q-005", "group_id": "experience", "question_text": "请填写 1—3 段与你目标方向相关的真实经历。", "question_type": "long_text", "required": True, "display_order": 5, "artifact_sections": ["个人能力与证据"]},
    {"question_id": "Q-006", "group_id": "experience", "question_text": "在这些经历中，你具体完成了什么工作？", "question_type": "long_text", "required": True, "display_order": 6, "artifact_sections": ["个人能力与证据"]},
    {"question_id": "Q-007", "group_id": "experience", "question_text": "这些经历产生了什么可以验证的结果？", "question_type": "long_text", "required": False, "display_order": 7, "artifact_sections": ["个人能力与证据"]},
    {"question_id": "Q-008", "group_id": "experience", "question_text": "你目前已经具备哪些能力或技能？", "question_type": "multi_select", "required": True, "display_order": 8, "artifact_sections": ["个人能力与证据"]},
    {"question_id": "Q-009", "group_id": "gap", "question_text": "你选择该职业方向的主要原因是什么？", "question_type": "long_text", "required": True, "display_order": 9, "artifact_sections": ["职业目标"]},
    {"question_id": "Q-010", "group_id": "gap", "question_text": "你认为该职业最重要的要求是什么？", "question_type": "long_text", "required": True, "display_order": 10, "artifact_sections": ["职业要求分析"]},
    {"question_id": "Q-011", "group_id": "gap", "question_text": "你目前最明显的能力差距是什么？", "question_type": "long_text", "required": True, "display_order": 11, "artifact_sections": ["差距分析"]},
    {"question_id": "Q-012", "group_id": "gap", "question_text": "你当前面临的主要困难是什么？", "question_type": "long_text", "required": True, "display_order": 12, "artifact_sections": ["差距分析"]},
    {"question_id": "Q-013", "group_id": "action", "question_text": "未来三个月你准备完成哪些行动？", "question_type": "long_text", "required": True, "display_order": 13, "artifact_sections": ["行动计划"]},
    {"question_id": "Q-014", "group_id": "action", "question_text": "未来一年你希望达到什么结果？", "question_type": "long_text", "required": True, "display_order": 14, "artifact_sections": ["行动计划"]},
    {"question_id": "Q-015", "group_id": "action", "question_text": "你希望 AI 重点帮助你解决什么问题？", "question_type": "long_text", "required": False, "display_order": 15, "artifact_sections": ["动态调整"]},
    {"question_id": "Q-016", "group_id": "materials", "question_text": "上传个人简历、岗位描述或项目材料。", "question_type": "file_upload", "required": False, "display_order": 16, "artifact_sections": ["Evidence 附件"]},
]

DEFAULT_RUBRIC = {
    "rubric_id": "RUB-CAREER-PLAN",
    "version": 1,
    "dimensions": [
        {"dimension_id": "goal_fit", "name": "项目目标与内容匹配度", "weight": 20},
        {"dimension_id": "evidence", "name": "个人事实与证据支撑", "weight": 25},
        {"dimension_id": "logic", "name": "分析逻辑与结构完整性", "weight": 20},
        {"dimension_id": "actionability", "name": "行动方案的可执行性", "weight": 20},
        {"dimension_id": "expression", "name": "表达质量与规范性", "weight": 15},
    ],
    "fatal_score_cap": 59,
}

DEFAULT_TEMPLATE = {
    "name": "个人职业发展规划",
    "category": "职业发展规划",
    "description": "根据个人经历、能力和职业目标，形成一份结构完整、证据充分、可执行的职业发展方案。",
    "background": "职业发展不是抽象愿望，而是个人证据、岗位要求、能力差距和行动安排之间的持续匹配。",
    "objective": "明确目标方向，识别能力差距，形成未来三个月和一年的行动计划。",
    "applicable_users": "高校学生、应届毕业生、职业探索阶段青年",
    "estimated_time_minutes": 60,
    "output_type": "career_report",
    "questions": DEFAULT_QUESTIONS,
    "material_requirements": ["个人简历", "目标岗位描述", "实习或项目材料", "获奖证明", "原有规划方案"],
    "artifact_structure": ["个人现状", "职业目标", "职业要求分析", "个人能力与证据", "差距分析", "行动计划", "动态调整"],
    "rubric": DEFAULT_RUBRIC,
    "artifact_template_id": "career_report_v1",
}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _serializable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


class ProjectRepository:
    """Project aggregate repository with mandatory tenant and owner predicates.

    The repository composes existing Session/Artifact/Evidence/Workflow capabilities by identifier;
    it does not recreate those stores or mutate their schemas.
    """

    def __init__(self, engine: Engine):
        self.engine = engine

    @staticmethod
    def _default_ids(tenant_id: str) -> tuple[str, str]:
        suffix = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()[:12].upper()
        return f"PT-CAREER-{suffix}", f"PTV-CAREER-{suffix}-1"

    def _tenant_workflow_template_id(self, tenant_id: str) -> str:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT product_preset FROM tenants WHERE tenant_id=:tenant_id"),
                {"tenant_id": tenant_id},
            ).mappings().first()
        if not row:
            raise KeyError(tenant_id)
        return get_workflow_template(row["product_preset"]).template_id

    def ensure_default_template(self, *, tenant_id: str, created_by: str = "system") -> dict[str, Any]:
        template_id, first_version_id = self._default_ids(tenant_id)
        workflow_template_id = self._tenant_workflow_template_id(tenant_id)
        try:
            with self.engine.begin() as conn:
                template = conn.execute(
                    text(
                        """SELECT template_id,current_version_id FROM project_templates
                        WHERE template_id=:template_id AND tenant_id=:tenant_id"""
                    ),
                    {"template_id": template_id, "tenant_id": tenant_id},
                ).mappings().first()
                current = None
                if template and template["current_version_id"]:
                    current = conn.execute(
                        text(
                            """SELECT template_version_id,workflow_template_id FROM project_template_versions
                            WHERE template_version_id=:version_id AND template_id=:template_id
                              AND tenant_id=:tenant_id"""
                        ),
                        {
                            "version_id": template["current_version_id"],
                            "template_id": template_id,
                            "tenant_id": tenant_id,
                        },
                    ).mappings().first()
                if current and current["workflow_template_id"] == workflow_template_id:
                    return self._get_template_with_connection(
                        conn, template_id=template_id, tenant_id=tenant_id
                    )

                next_version = int(
                    conn.execute(
                        text(
                            """SELECT COALESCE(MAX(version),0)+1 FROM project_template_versions
                            WHERE template_id=:template_id AND tenant_id=:tenant_id"""
                        ),
                        {"template_id": template_id, "tenant_id": tenant_id},
                    ).scalar_one()
                )
                version_id = first_version_id if next_version == 1 else f"{first_version_id.rsplit('-', 1)[0]}-{next_version}"
                if not template:
                    conn.execute(
                        text(
                            """INSERT INTO project_templates(
                            template_id,tenant_id,name,category,status,current_version_id,created_by,created_at,updated_at
                            ) VALUES(:template_id,:tenant_id,:name,:category,'published',NULL,:created_by,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"""
                        ),
                        {
                            "template_id": template_id,
                            "tenant_id": tenant_id,
                            "name": DEFAULT_TEMPLATE["name"],
                            "category": DEFAULT_TEMPLATE["category"],
                            "created_by": created_by,
                        },
                    )
                conn.execute(
                    text(
                        """INSERT INTO project_template_versions(
                        template_version_id,template_id,tenant_id,version,name,category,description,background,
                        objective,applicable_users,estimated_time_minutes,output_type,questions_json,
                        material_requirements_json,artifact_structure_json,rubric_json,workflow_template_id,
                        artifact_template_id,status,published_at,created_at
                        ) VALUES(:version_id,:template_id,:tenant_id,:version,:name,:category,:description,:background,
                        :objective,:applicable_users,:estimated_time,:output_type,:questions,:materials,:structure,
                        :rubric,:workflow_template,:artifact_template,'published',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"""
                    ),
                    {
                        "version_id": version_id,
                        "template_id": template_id,
                        "tenant_id": tenant_id,
                        "version": next_version,
                        "name": DEFAULT_TEMPLATE["name"],
                        "category": DEFAULT_TEMPLATE["category"],
                        "description": DEFAULT_TEMPLATE["description"],
                        "background": DEFAULT_TEMPLATE["background"],
                        "objective": DEFAULT_TEMPLATE["objective"],
                        "applicable_users": DEFAULT_TEMPLATE["applicable_users"],
                        "estimated_time": DEFAULT_TEMPLATE["estimated_time_minutes"],
                        "output_type": DEFAULT_TEMPLATE["output_type"],
                        "questions": _json(DEFAULT_TEMPLATE["questions"]),
                        "materials": _json(DEFAULT_TEMPLATE["material_requirements"]),
                        "structure": _json(DEFAULT_TEMPLATE["artifact_structure"]),
                        "rubric": _json(DEFAULT_TEMPLATE["rubric"]),
                        "workflow_template": workflow_template_id,
                        "artifact_template": DEFAULT_TEMPLATE["artifact_template_id"],
                    },
                )
                conn.execute(
                    text(
                        """UPDATE project_templates
                        SET current_version_id=:version_id,status='published',updated_at=CURRENT_TIMESTAMP
                        WHERE template_id=:template_id AND tenant_id=:tenant_id"""
                    ),
                    {
                        "version_id": version_id,
                        "template_id": template_id,
                        "tenant_id": tenant_id,
                    },
                )
        except IntegrityError:
            # A concurrent creator may have published the same deterministic next version.
            pass
        result = self.get_template(template_id, tenant_id=tenant_id)
        if result.get("workflow_template_id") != workflow_template_id:
            # A concurrent preset change must not silently return a mismatched version.
            return self.ensure_default_template(tenant_id=tenant_id, created_by=created_by)
        return result

    def list_templates(self, *, tenant_id: str, published_only: bool = True) -> list[dict[str, Any]]:
        self.ensure_default_template(tenant_id=tenant_id)
        sql = """SELECT t.*,v.version AS current_version,v.description,v.objective,
                 v.estimated_time_minutes,v.output_type
                 FROM project_templates t
                 JOIN project_template_versions v
                   ON v.template_version_id=t.current_version_id AND v.tenant_id=t.tenant_id
                 WHERE t.tenant_id=:tenant"""
        if published_only:
            sql += " AND t.status='published' AND v.status='published'"
        sql += " ORDER BY t.updated_at DESC,t.name"
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"tenant": tenant_id}).mappings().all()
        return [self._clean_row(dict(row)) for row in rows]

    def get_template(self, template_id: str, *, tenant_id: str) -> dict[str, Any]:
        with self.engine.connect() as conn:
            return self._get_template_with_connection(
                conn, template_id=template_id, tenant_id=tenant_id
            )

    def _get_template_with_connection(
        self, conn, *, template_id: str, tenant_id: str
    ) -> dict[str, Any]:
        row = conn.execute(
            text(
                """SELECT t.*,v.template_version_id,v.version,v.description,v.background,v.objective,
                v.applicable_users,v.estimated_time_minutes,v.output_type,v.questions_json,
                v.material_requirements_json,v.artifact_structure_json,v.rubric_json,
                v.workflow_template_id,v.artifact_template_id,v.published_at
                FROM project_templates t
                JOIN project_template_versions v
                  ON v.template_version_id=t.current_version_id AND v.tenant_id=t.tenant_id
                WHERE t.template_id=:template_id AND t.tenant_id=:tenant"""
            ),
            {"template_id": template_id, "tenant": tenant_id},
        ).mappings().first()
        if not row:
            raise KeyError(template_id)
        return self._decode_template(dict(row))

    def get_template_version(self, template_version_id: str, *, tenant_id: str) -> dict[str, Any]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """SELECT * FROM project_template_versions
                    WHERE template_version_id=:version_id AND tenant_id=:tenant"""
                ),
                {"version_id": template_version_id, "tenant": tenant_id},
            ).mappings().first()
        if not row:
            raise KeyError(template_version_id)
        return self._decode_template(dict(row))

    def create_project(
        self,
        *,
        tenant_id: str,
        owner_user_id: str,
        template_version_id: str,
        session_id: str,
        name: str = "",
    ) -> dict[str, Any]:
        if not tenant_id or not owner_user_id or not session_id:
            raise ValueError("tenant, owner and session are required")
        with self.engine.connect() as conn:
            session = conn.execute(
                text(
                    """SELECT s.tenant_id,s.student_user_id,w.template_id AS workflow_template_id
                    FROM sessions s
                    LEFT JOIN workflow_instances w
                      ON w.session_id=s.session_id AND w.tenant_id=s.tenant_id
                    WHERE s.session_id=:session_id"""
                ),
                {"session_id": session_id},
            ).mappings().first()
        if not session:
            raise ValueError("project session does not exist")
        if session["tenant_id"] != tenant_id or session["student_user_id"] != owner_user_id:
            raise ValueError("project session tenant or owner mismatch")
        version = self.get_template_version(template_version_id, tenant_id=tenant_id)
        if version.get("status") != "published":
            raise ValueError("project template version is not published")
        with self.engine.connect() as conn:
            current_version_id = conn.execute(
                text(
                    """SELECT current_version_id FROM project_templates
                    WHERE template_id=:template_id AND tenant_id=:tenant_id"""
                ),
                {"template_id": version["template_id"], "tenant_id": tenant_id},
            ).scalar_one_or_none()
        if current_version_id != template_version_id:
            raise ProjectVersionConflict("project template version is not current")
        if session["workflow_template_id"] != version.get("workflow_template_id"):
            raise ValueError("project session workflow does not match template")
        project_id = f"PRJ-{uuid4().hex[:16].upper()}"
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """INSERT INTO project_instances(
                    project_id,tenant_id,owner_user_id,template_id,template_version_id,session_id,name,
                    status,current_step,created_at,updated_at
                    ) VALUES(:project_id,:tenant,:owner,:template_id,:version_id,:session_id,:name,
                    'draft','overview',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"""
                ),
                {
                    "project_id": project_id,
                    "tenant": tenant_id,
                    "owner": owner_user_id,
                    "template_id": version["template_id"],
                    "version_id": template_version_id,
                    "session_id": session_id,
                    "name": (name or version["name"]).strip(),
                },
            )
        return self.get_project(project_id, tenant_id=tenant_id, owner_user_id=owner_user_id)

    def list_projects(
        self, *, tenant_id: str, owner_user_id: str, status: str | None = None
    ) -> list[dict[str, Any]]:
        if status and status not in PROJECT_STATUSES:
            raise ValueError("invalid project status")
        sql = """SELECT p.*,v.name AS template_name,v.category,v.version AS template_version,
                 v.estimated_time_minutes,v.output_type
                 FROM project_instances p
                 JOIN project_template_versions v
                   ON v.template_version_id=p.template_version_id AND v.tenant_id=p.tenant_id
                 WHERE p.tenant_id=:tenant AND p.owner_user_id=:owner"""
        params: dict[str, Any] = {"tenant": tenant_id, "owner": owner_user_id}
        if status:
            sql += " AND p.status=:status"
            params["status"] = status
        sql += " ORDER BY p.updated_at DESC,p.project_id"
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return [self._project_summary(dict(row)) for row in rows]

    def get_project(self, project_id: str, *, tenant_id: str, owner_user_id: str) -> dict[str, Any]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """SELECT p.*,v.version AS template_version
                    FROM project_instances p
                    JOIN project_template_versions v
                      ON v.template_version_id=p.template_version_id AND v.tenant_id=p.tenant_id
                    WHERE p.project_id=:project_id AND p.tenant_id=:tenant AND p.owner_user_id=:owner"""
                ),
                {"project_id": project_id, "tenant": tenant_id, "owner": owner_user_id},
            ).mappings().first()
        if not row:
            raise KeyError(project_id)
        project = self._project_summary(dict(row))
        project["template"] = self.get_template_version(project["template_version_id"], tenant_id=tenant_id)
        project["answers"] = self.list_answers(project_id, tenant_id=tenant_id, owner_user_id=owner_user_id)
        return project

    def save_answer(
        self,
        project_id: str,
        question_id: str,
        answer: Any,
        *,
        tenant_id: str,
        owner_user_id: str,
    ) -> dict[str, Any]:
        self.get_project(project_id, tenant_id=tenant_id, owner_user_id=owner_user_id)
        params = {
            "project_id": project_id,
            "tenant": tenant_id,
            "owner": owner_user_id,
            "question_id": question_id,
            "answer": _json(answer),
        }
        with self.engine.begin() as conn:
            existing = conn.execute(
                text(
                    """SELECT 1 FROM project_answers
                    WHERE project_id=:project_id AND tenant_id=:tenant
                      AND owner_user_id=:owner AND question_id=:question_id"""
                ),
                params,
            ).first()
            if existing:
                conn.execute(
                    text(
                        """UPDATE project_answers SET answer_json=:answer,updated_at=CURRENT_TIMESTAMP
                        WHERE project_id=:project_id AND tenant_id=:tenant
                          AND owner_user_id=:owner AND question_id=:question_id"""
                    ),
                    params,
                )
            else:
                conn.execute(
                    text(
                        """INSERT INTO project_answers(
                        project_id,tenant_id,owner_user_id,question_id,answer_json,created_at,updated_at
                        ) VALUES(:project_id,:tenant,:owner,:question_id,:answer,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"""
                    ),
                    params,
                )
            conn.execute(
                text(
                    """UPDATE project_instances
                    SET status=CASE WHEN status='draft' THEN 'collecting' ELSE status END,
                        current_step=CASE WHEN current_step='overview' THEN 'form' ELSE current_step END,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE project_id=:project_id AND tenant_id=:tenant AND owner_user_id=:owner"""
                ),
                params,
            )
        return {"question_id": question_id, "answer": answer}

    def list_answers(self, project_id: str, *, tenant_id: str, owner_user_id: str) -> dict[str, Any]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """SELECT question_id,answer_json FROM project_answers
                    WHERE project_id=:project_id AND tenant_id=:tenant AND owner_user_id=:owner
                    ORDER BY question_id"""
                ),
                {"project_id": project_id, "tenant": tenant_id, "owner": owner_user_id},
            ).mappings().all()
        answers: dict[str, Any] = {}
        for row in rows:
            try:
                answers[row["question_id"]] = json.loads(row["answer_json"])
            except Exception:
                answers[row["question_id"]] = row["answer_json"]
        return answers

    @staticmethod
    def _clean_row(row: dict[str, Any]) -> dict[str, Any]:
        return {key: _serializable(value) for key, value in row.items()}

    @classmethod
    def _decode_template(cls, row: dict[str, Any]) -> dict[str, Any]:
        for source, target, fallback in (
            ("questions_json", "questions", []),
            ("material_requirements_json", "material_requirements", []),
            ("artifact_structure_json", "artifact_structure", []),
            ("rubric_json", "rubric", {}),
        ):
            if source in row:
                try:
                    row[target] = json.loads(row.pop(source) or _json(fallback))
                except Exception:
                    row[target] = fallback
        return cls._clean_row(row)

    @classmethod
    def _project_summary(cls, row: dict[str, Any]) -> dict[str, Any]:
        status = str(row.get("status") or "draft")
        active_index = {
            "draft": 0,
            "collecting": 1,
            "ready_to_generate": 2,
            "solution_generated": 3,
            "reviewed": 3,
            "revision_required": 3,
            "completed": 4,
        }.get(status, 0)
        labels = ["了解项目", "填写信息", "生成方案", "评分与修改", "完成项目"]
        row["progress"] = {
            "current": active_index + 1,
            "total": 5,
            "percent": 100 if status == "completed" else active_index * 25,
            "steps": [
                {
                    "id": idx + 1,
                    "label": label,
                    "status": "completed" if idx < active_index or status == "completed" else ("current" if idx == active_index else "locked"),
                }
                for idx, label in enumerate(labels)
            ],
        }
        return cls._clean_row(row)
