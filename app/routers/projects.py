from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from ..auth_store import Principal
from ..domain.roles import canonical_role
from ..project_models import ProjectAnswersRequest, ProjectCreateRequest
from ..project_repository import PROJECT_STATUSES, ProjectRepository, ProjectVersionConflict


MILESTONE_TRANSITIONS = {
    "ready": ("ready_to_generate", "generate"),
    "generated": ("solution_generated", "review"),
    "reviewed": ("reviewed", "revise"),
    "revision_required": ("revision_required", "revise"),
    "completed": ("completed", "complete"),
}

ALLOWED_STATUS_TRANSITIONS = {
    "draft": {"collecting", "ready_to_generate"},
    "collecting": {"ready_to_generate"},
    "ready_to_generate": {"solution_generated"},
    "solution_generated": {"reviewed", "revision_required"},
    "reviewed": {"revision_required", "completed"},
    "revision_required": {"reviewed", "completed"},
    "completed": set(),
}


def _answer_is_empty(value: Any) -> bool:
    if value is None or value == [] or value == {}:
        return True
    return isinstance(value, str) and not value.strip()


def _missing_required(project: dict[str, Any]) -> list[dict[str, Any]]:
    answers = project.get("answers") or {}
    questions = project.get("template", {}).get("questions") or []
    return [
        question
        for question in questions
        if question.get("required") and _answer_is_empty(answers.get(str(question.get("question_id"))))
    ]


def _next_action(project: dict[str, Any] | None) -> dict[str, Any]:
    if not project:
        return {
            "action": "create_project",
            "title": "建立第一个职业项目",
            "description": "从职业方向、真实经历和目标岗位开始，形成可持续修改的项目档案。",
            "href": "/projects/new",
            "cta": "开始项目",
        }
    missing = _missing_required(project)
    project_id = project["project_id"]
    session_id = project.get("session_id", "")
    if missing:
        return {
            "action": "complete_project_profile",
            "title": f"补充 {len(missing)} 项关键信息",
            "description": "先完成职业方向、真实经历和能力证据，再进入成果生成。",
            "href": f"/projects/{project_id}#projectFormSection",
            "cta": "继续填写",
            "missing_question_ids": [str(item.get("question_id")) for item in missing],
        }
    status = str(project.get("status") or "collecting")
    workspace = f"/student?session_id={session_id}&project_id={project_id}"
    mapping = {
        "draft": ("complete_project_profile", "检查项目材料", "确认信息完整后进入成果工作台。", f"/projects/{project_id}", "检查材料"),
        "collecting": ("prepare_evidence", "整理项目证据", "上传简历、项目成果或岗位描述，避免无证据生成。", workspace, "整理证据"),
        "ready_to_generate": ("generate_artifact", "生成第一版成果", "基于项目材料生成职业方案或基础简历。", workspace, "生成成果"),
        "solution_generated": ("review_artifact", "评审当前成果", "检查岗位匹配、事实支撑和表达质量。", workspace, "开始评审"),
        "reviewed": ("revise_artifact", "根据评审完成修改", "处理高优先级问题，保留修改前后版本。", workspace, "继续修改"),
        "revision_required": ("revise_artifact", "完成必要修改", "当前版本仍存在关键缺口，完成修改后再提交。", workspace, "立即修改"),
        "completed": ("export_artifact", "导出并使用成果", "当前项目已完成，可导出简历或继续创建岗位定制版本。", workspace, "查看成果"),
    }
    action, title, description, href, cta = mapping.get(status, mapping["collecting"])
    return {"action": action, "title": title, "description": description, "href": href, "cta": cta}


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def calculate_usage_cost(rows: list[dict[str, Any]], capabilities: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate configured model cost without inventing prices for unknown models."""
    pricing = {
        (str(item.get("provider_id")), str(item.get("model"))): (
            float(item.get("input_cost_per_million") or 0),
            float(item.get("output_cost_per_million") or 0),
        )
        for item in capabilities
    }
    total = 0.0
    unpriced_calls = 0
    recent: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        key = (str(row.get("provider_id")), str(row.get("model")))
        rates = pricing.get(key)
        if rates is None or (rates[0] <= 0 and rates[1] <= 0):
            row["estimated_cost_usd"] = None
            unpriced_calls += 1
        else:
            input_cost = int(row.get("input_tokens") or 0) * rates[0] / 1_000_000
            output_cost = int(row.get("output_tokens") or 0) * rates[1] / 1_000_000
            row["estimated_cost_usd"] = round(input_cost + output_cost, 8)
            total += input_cost + output_cost
        row["success"] = bool(row.get("success"))
        recent.append(row)
    return {
        "estimated_cost_usd": round(total, 6),
        "priced_calls": len(rows) - unpriced_calls,
        "unpriced_calls": unpriced_calls,
        "recent": recent,
    }


def build_projects_router(
    *,
    current_principal,
    project_repository: ProjectRepository,
    create_project_session: Callable[[Principal], object],
    cleanup_project_session: Callable[[str, str], None],
    allow_anonymous_demo: bool = False,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["projects"])
    engine = project_repository.engine

    def participant_identity(principal: Principal) -> tuple[str, str]:
        if not principal.authenticated:
            if allow_anonymous_demo and principal.user_id == "demo-local":
                return principal.tenant_id, principal.user_id
            raise HTTPException(status_code=401, detail="authenticated participant required")
        role = canonical_role(principal.role)
        if role != "participant":
            raise HTTPException(status_code=403, detail="participant account required")
        owner = principal.user_id
        if not owner:
            raise HTTPException(status_code=401, detail="authenticated participant required")
        return principal.tenant_id, owner

    def target_tenant(principal: Principal, requested: str = "") -> str:
        if not principal.authenticated:
            raise HTTPException(status_code=401, detail="authentication required")
        role = canonical_role(principal.role)
        if role == "platform_admin" and requested:
            return requested
        return principal.tenant_id

    def require_operational_role(principal: Principal) -> str:
        role = canonical_role(principal.role)
        if role not in {"advisor", "organization_admin", "platform_admin"}:
            raise HTTPException(status_code=403, detail="advisor or organization administrator required")
        return role

    def require_governance_role(principal: Principal) -> str:
        role = canonical_role(principal.role)
        if role not in {"organization_admin", "platform_admin"}:
            raise HTTPException(status_code=403, detail="organization administrator required")
        return role

    def write_audit(
        principal: Principal,
        *,
        action: str,
        resource_type: str,
        resource_id: str,
        success: bool = True,
        details: dict[str, Any] | None = None,
    ) -> None:
        if not principal.authenticated:
            return
        with engine.begin() as conn:
            conn.execute(
                text(
                    """INSERT INTO security_audit_log(
                    tenant_id,user_id,action,resource_type,resource_id,success,details_json,ip_address
                    ) VALUES(:tenant,:user_id,:action,:resource_type,:resource_id,:success,:details,'')"""
                ),
                {
                    "tenant": principal.tenant_id,
                    "user_id": principal.user_id,
                    "action": action,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "success": 1 if success else 0,
                    "details": json.dumps(details or {}, ensure_ascii=False)[:8000],
                },
            )

    def set_project_status(
        project_id: str,
        *,
        tenant_id: str,
        owner_user_id: str,
        status: str,
        current_step: str,
    ) -> None:
        if status not in PROJECT_STATUSES:
            raise ValueError("invalid project status")
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    """UPDATE project_instances
                    SET status=:status,current_step=:current_step,updated_at=CURRENT_TIMESTAMP,
                        completed_at=CASE WHEN :status='completed' THEN CURRENT_TIMESTAMP ELSE completed_at END
                    WHERE project_id=:project_id AND tenant_id=:tenant AND owner_user_id=:owner"""
                ),
                {
                    "status": status,
                    "current_step": current_step,
                    "project_id": project_id,
                    "tenant": tenant_id,
                    "owner": owner_user_id,
                },
            )
            if result.rowcount == 0:
                raise KeyError(project_id)

    @router.get("/project-templates")
    def list_project_templates(principal: Principal = Depends(current_principal)):
        tenant_id, _ = participant_identity(principal)
        return {"items": project_repository.list_templates(tenant_id=tenant_id), "tenant_id": tenant_id}

    @router.get("/project-templates/{template_id}")
    def get_project_template(template_id: str, principal: Principal = Depends(current_principal)):
        tenant_id, _ = participant_identity(principal)
        try:
            template = project_repository.get_template(template_id, tenant_id=tenant_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="project template not found")
        if template.get("status") != "published":
            raise HTTPException(status_code=404, detail="project template not found")
        return template

    @router.get("/projects")
    def list_projects(
        status: str | None = Query(default=None),
        principal: Principal = Depends(current_principal),
    ):
        tenant_id, owner = participant_identity(principal)
        try:
            items = project_repository.list_projects(
                tenant_id=tenant_id, owner_user_id=owner, status=status
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return {"items": items, "tenant_id": tenant_id}

    @router.get("/me/next-action")
    def participant_next_action(principal: Principal = Depends(current_principal)):
        tenant_id, owner = participant_identity(principal)
        projects = project_repository.list_projects(tenant_id=tenant_id, owner_user_id=owner)
        project = None
        if projects:
            project = project_repository.get_project(
                projects[0]["project_id"], tenant_id=tenant_id, owner_user_id=owner
            )
        return {"next_action": _next_action(project), "project": project}

    @router.post("/projects", status_code=201)
    def create_project(
        req: ProjectCreateRequest,
        principal: Principal = Depends(current_principal),
    ):
        tenant_id, owner = participant_identity(principal)
        try:
            version = project_repository.get_template_version(
                req.template_version_id, tenant_id=tenant_id
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="published project template version not found")
        if version.get("status") != "published":
            raise HTTPException(status_code=409, detail="project template version is not published")
        try:
            current = project_repository.get_template(version["template_id"], tenant_id=tenant_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="project template not found")
        if current.get("current_version_id") != req.template_version_id:
            raise HTTPException(status_code=409, detail="project template version is not current")
        state = create_project_session(principal)
        try:
            if state.tenant_id != tenant_id or state.student_user_id != owner:
                raise HTTPException(status_code=403, detail="project session ownership mismatch")
            project = project_repository.create_project(
                tenant_id=tenant_id,
                owner_user_id=owner,
                template_version_id=req.template_version_id,
                session_id=state.session_id,
                name=req.name,
            )
            write_audit(
                principal,
                action="project_created",
                resource_type="project",
                resource_id=project["project_id"],
                details={"template_version_id": req.template_version_id},
            )
            return project
        except ProjectVersionConflict as exc:
            cleanup_project_session(state.session_id, tenant_id)
            raise HTTPException(status_code=409, detail=str(exc))
        except ValueError as exc:
            cleanup_project_session(state.session_id, tenant_id)
            raise HTTPException(status_code=409, detail=str(exc))
        except Exception:
            cleanup_project_session(state.session_id, tenant_id)
            raise

    @router.get("/projects/{project_id}")
    def get_project(project_id: str, principal: Principal = Depends(current_principal)):
        tenant_id, owner = participant_identity(principal)
        try:
            project = project_repository.get_project(
                project_id, tenant_id=tenant_id, owner_user_id=owner
            )
            project["next_action"] = _next_action(project)
            return project
        except KeyError:
            raise HTTPException(status_code=404, detail="project not found")

    @router.get("/projects/{project_id}/form")
    def get_project_form(project_id: str, principal: Principal = Depends(current_principal)):
        tenant_id, owner = participant_identity(principal)
        try:
            project = project_repository.get_project(
                project_id, tenant_id=tenant_id, owner_user_id=owner
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="project not found")
        return {
            "project_id": project_id,
            "questions": project["template"].get("questions", []),
            "answers": project.get("answers", {}),
            "missing_required": [str(item.get("question_id")) for item in _missing_required(project)],
        }

    @router.put("/projects/{project_id}/answers")
    def save_project_answers(
        project_id: str,
        req: ProjectAnswersRequest,
        principal: Principal = Depends(current_principal),
    ):
        tenant_id, owner = participant_identity(principal)
        try:
            project = project_repository.get_project(
                project_id, tenant_id=tenant_id, owner_user_id=owner
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="project not found")
        allowed = {str(q.get("question_id")) for q in project["template"].get("questions", [])}
        unknown = sorted({item.question_id for item in req.answers} - allowed)
        if unknown:
            raise HTTPException(status_code=422, detail={"unknown_question_ids": unknown})
        for item in req.answers:
            project_repository.save_answer(
                project_id,
                item.question_id,
                item.answer,
                tenant_id=tenant_id,
                owner_user_id=owner,
            )
        updated = project_repository.get_project(
            project_id, tenant_id=tenant_id, owner_user_id=owner
        )
        if not _missing_required(updated) and updated.get("status") in {"draft", "collecting"}:
            set_project_status(
                project_id,
                tenant_id=tenant_id,
                owner_user_id=owner,
                status="ready_to_generate",
                current_step="generate",
            )
            updated = project_repository.get_project(
                project_id, tenant_id=tenant_id, owner_user_id=owner
            )
        write_audit(
            principal,
            action="project_answers_saved",
            resource_type="project",
            resource_id=project_id,
            details={"question_count": len(req.answers), "status": updated.get("status")},
        )
        return {
            "project_id": project_id,
            "answers": updated.get("answers", {}),
            "status": updated.get("status"),
            "next_action": _next_action(updated),
        }

    @router.patch("/projects/{project_id}/milestone")
    def update_project_milestone(
        project_id: str,
        milestone: str = Query(pattern="^(ready|generated|reviewed|revision_required|completed)$"),
        principal: Principal = Depends(current_principal),
    ):
        tenant_id, owner = participant_identity(principal)
        try:
            project = project_repository.get_project(
                project_id, tenant_id=tenant_id, owner_user_id=owner
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="project not found")
        target_status, current_step = MILESTONE_TRANSITIONS[milestone]
        current_status = str(project.get("status") or "draft")
        if target_status == current_status:
            return {"project": project, "next_action": _next_action(project)}
        if target_status not in ALLOWED_STATUS_TRANSITIONS.get(current_status, set()):
            raise HTTPException(
                status_code=409,
                detail=f"invalid project transition: {current_status} -> {target_status}",
            )
        if target_status == "ready_to_generate" and _missing_required(project):
            raise HTTPException(status_code=409, detail="required project information is incomplete")
        set_project_status(
            project_id,
            tenant_id=tenant_id,
            owner_user_id=owner,
            status=target_status,
            current_step=current_step,
        )
        updated = project_repository.get_project(
            project_id, tenant_id=tenant_id, owner_user_id=owner
        )
        write_audit(
            principal,
            action="project_milestone_updated",
            resource_type="project",
            resource_id=project_id,
            details={"from": current_status, "to": target_status, "milestone": milestone},
        )
        return {"project": updated, "next_action": _next_action(updated)}

    @router.get("/advisor/operations")
    def advisor_operations(
        tenant_id: str = Query(default=""),
        principal: Principal = Depends(current_principal),
    ):
        role = require_operational_role(principal)
        target = target_tenant(principal, tenant_id)
        with engine.connect() as conn:
            rows = [
                dict(item)
                for item in conn.execute(
                    text(
                        """SELECT p.project_id,p.tenant_id,p.owner_user_id,p.session_id,p.name,
                        p.status,p.current_step,p.updated_at,s.class_id,u.display_name,v.questions_json
                        FROM project_instances p
                        JOIN sessions s ON s.session_id=p.session_id AND s.tenant_id=p.tenant_id
                        LEFT JOIN users u ON u.user_id=p.owner_user_id
                        JOIN project_template_versions v
                          ON v.template_version_id=p.template_version_id AND v.tenant_id=p.tenant_id
                        WHERE p.tenant_id=:tenant
                        ORDER BY p.updated_at DESC"""
                    ),
                    {"tenant": target},
                ).mappings().all()
            ]
            answer_rows = [
                dict(item)
                for item in conn.execute(
                    text(
                        """SELECT project_id,question_id,answer_json FROM project_answers
                        WHERE tenant_id=:tenant"""
                    ),
                    {"tenant": target},
                ).mappings().all()
            ]
            allowed_classes: set[str] | None = None
            if role == "advisor":
                allowed_classes = {
                    str(item["class_id"])
                    for item in conn.execute(
                        text(
                            """SELECT class_id FROM class_memberships
                            WHERE tenant_id=:tenant AND user_id=:user_id AND role='teacher'"""
                        ),
                        {"tenant": target, "user_id": principal.user_id},
                    ).mappings().all()
                }
        if allowed_classes is not None:
            rows = [row for row in rows if str(row.get("class_id") or "") in allowed_classes]
        answers: dict[str, dict[str, Any]] = {}
        for item in answer_rows:
            try:
                value = json.loads(item.get("answer_json") or "null")
            except (TypeError, json.JSONDecodeError):
                value = item.get("answer_json")
            answers.setdefault(str(item["project_id"]), {})[str(item["question_id"])] = value
        now = datetime.now(timezone.utc)
        queue: list[dict[str, Any]] = []
        counts = {status: 0 for status in PROJECT_STATUSES}
        student_ids: set[str] = set()
        for row in rows:
            project_id = str(row["project_id"])
            student_ids.add(str(row.get("owner_user_id") or ""))
            status = str(row.get("status") or "draft")
            counts[status] = counts.get(status, 0) + 1
            try:
                questions = json.loads(row.get("questions_json") or "[]")
            except (TypeError, json.JSONDecodeError):
                questions = []
            project_answers = answers.get(project_id, {})
            missing = [
                str(question.get("question_id"))
                for question in questions
                if question.get("required")
                and _answer_is_empty(project_answers.get(str(question.get("question_id"))))
            ]
            updated_at = _parse_datetime(row.get("updated_at"))
            stale_days = (now - updated_at).days if updated_at else 999
            reasons: list[str] = []
            priority = 0
            if status == "revision_required":
                reasons.append("成果需要修改")
                priority = max(priority, 100)
            if status == "solution_generated":
                reasons.append("成果等待评审")
                priority = max(priority, 90)
            if status == "ready_to_generate":
                reasons.append("资料完整，等待生成")
                priority = max(priority, 70)
            if missing:
                reasons.append(f"缺少 {len(missing)} 项关键信息")
                priority = max(priority, 60)
            if status == "draft":
                reasons.append("项目尚未启动")
                priority = max(priority, 50)
            if stale_days >= 7 and status != "completed":
                reasons.append(f"连续 {stale_days} 天未更新")
                priority = max(priority, 80)
            if reasons:
                queue.append(
                    {
                        "project_id": project_id,
                        "session_id": row.get("session_id"),
                        "student_user_id": row.get("owner_user_id"),
                        "student_name": row.get("display_name") or "未命名学生",
                        "project_name": row.get("name"),
                        "status": status,
                        "class_id": row.get("class_id"),
                        "reasons": reasons,
                        "priority": priority,
                        "missing_question_ids": missing,
                        "stale_days": stale_days,
                        "updated_at": row.get("updated_at"),
                    }
                )
        queue.sort(key=lambda item: (-int(item["priority"]), -int(item["stale_days"]), str(item["student_name"])))
        metrics = {
            "active_students": len(student_ids),
            "total_projects": len(rows),
            "needs_attention": len(queue),
            "ready_to_generate": counts.get("ready_to_generate", 0),
            "awaiting_review": counts.get("solution_generated", 0),
            "revision_required": counts.get("revision_required", 0),
            "completed": counts.get("completed", 0),
            "stalled": sum(1 for item in queue if item["stale_days"] >= 7),
        }
        return {"tenant_id": target, "metrics": metrics, "status_counts": counts, "queue": queue}

    @router.get("/governance/ai-usage")
    def ai_usage_governance(
        tenant_id: str = Query(default=""),
        limit: int = Query(default=100, ge=1, le=1000),
        principal: Principal = Depends(current_principal),
    ):
        require_governance_role(principal)
        target = target_tenant(principal, tenant_id)
        with engine.connect() as conn:
            usage_rows = [
                dict(item)
                for item in conn.execute(
                    text(
                        """SELECT * FROM llm_usage WHERE tenant_id=:tenant
                        ORDER BY id DESC LIMIT :limit"""
                    ),
                    {"tenant": target, "limit": limit},
                ).mappings().all()
            ]
            capabilities = [
                dict(item)
                for item in conn.execute(
                    text(
                        """SELECT provider_id,model,input_cost_per_million,output_cost_per_million
                        FROM llm_model_capabilities"""
                    )
                ).mappings().all()
            ]
        cost = calculate_usage_cost(usage_rows, capabilities)
        total_tokens = sum(int(item.get("total_tokens") or 0) for item in usage_rows)
        errors = sum(1 for item in usage_rows if not bool(item.get("success")))
        by_task: dict[str, dict[str, Any]] = {}
        for item in cost["recent"]:
            task = str(item.get("task") or "unknown")
            bucket = by_task.setdefault(task, {"calls": 0, "tokens": 0, "estimated_cost_usd": 0.0})
            bucket["calls"] += 1
            bucket["tokens"] += int(item.get("total_tokens") or 0)
            if item.get("estimated_cost_usd") is not None:
                bucket["estimated_cost_usd"] += float(item["estimated_cost_usd"])
        for bucket in by_task.values():
            bucket["estimated_cost_usd"] = round(bucket["estimated_cost_usd"], 6)
        write_audit(
            principal,
            action="ai_usage_viewed",
            resource_type="tenant",
            resource_id=target,
            details={"limit": limit},
        )
        return {
            "tenant_id": target,
            "currency": "USD",
            "pricing_source": "configured_model_capabilities",
            "summary": {
                "calls": len(usage_rows),
                "tokens": total_tokens,
                "errors": errors,
                "error_rate": round(errors / len(usage_rows), 4) if usage_rows else 0,
                "estimated_cost_usd": cost["estimated_cost_usd"],
                "priced_calls": cost["priced_calls"],
                "unpriced_calls": cost["unpriced_calls"],
            },
            "by_task": by_task,
            "recent": cost["recent"],
        }

    @router.get("/governance/audit-events")
    def audit_events(
        tenant_id: str = Query(default=""),
        limit: int = Query(default=100, ge=1, le=1000),
        principal: Principal = Depends(current_principal),
    ):
        require_governance_role(principal)
        target = target_tenant(principal, tenant_id)
        with engine.connect() as conn:
            rows = [
                dict(item)
                for item in conn.execute(
                    text(
                        """SELECT * FROM security_audit_log WHERE tenant_id=:tenant
                        ORDER BY created_at DESC LIMIT :limit"""
                    ),
                    {"tenant": target, "limit": limit},
                ).mappings().all()
            ]
        for row in rows:
            try:
                row["details"] = json.loads(row.pop("details_json", "{}") or "{}")
            except (TypeError, json.JSONDecodeError):
                row["details"] = {}
            row["success"] = bool(row.get("success"))
        return {"tenant_id": target, "events": rows, "count": len(rows)}

    return router
