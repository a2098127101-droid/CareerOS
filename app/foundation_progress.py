from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .direction_discovery import discover_task_preferences
from .ability_aggregation import aggregate_professional_evidence
from .expression_service import ExpressionService
from .foundation_abilities import ABILITY_BY_ID, FOUNDATION_ABILITIES, FOUNDATION_TASKS, TASK_BY_ID, public_task
from .project_chain import build_first_mini_project, mini_project_markdown
from .unified_runtime_store import RuntimeVersionConflict


class FoundationError(RuntimeError):
    pass


class FoundationProgressService:
    ENTITY = "foundation_state"
    ENTITY_ID = "foundation"

    def __init__(self, *, repository: Any, evidence: Any, artifacts: Any):
        self.repository = repository
        self.evidence = evidence
        self.artifacts = artifacts

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _default_abilities() -> dict[str, dict[str, Any]]:
        return {
            item["id"]: {
                "id": item["id"],
                "name": item["name"],
                "plain": item["plain"],
                "attempts": 0,
                "guided": 0,
                "independent": 0,
                "transfer": 0,
                "combined": 0,
                "scoreTotal": 0.0,
                "level": "还没接触",
            }
            for item in FOUNDATION_ABILITIES
        }

    def _default_state(self, *, owner_user_id: str, session_id: str) -> dict[str, Any]:
        return {
            "id": self.ENTITY_ID,
            "ownerUserId": owner_user_id,
            "sessionId": session_id,
            "mode": "beginner",
            "startedAt": self._now(),
            "currentTaskIndex": 0,
            "completedTaskIds": [],
            "answers": {},
            "hintUsage": {},
            "taskResults": {},
            "abilities": self._default_abilities(),
            "miniProjects": [],
            "expression": {},
            "updatedAt": self._now(),
        }

    def get_state(self, *, tenant_id: str, owner_user_id: str, session_id: str, create: bool = True) -> dict[str, Any]:
        try:
            state = self.repository.get(
                tenant_id=tenant_id,
                entity_type=self.ENTITY,
                entity_id=self.ENTITY_ID,
                owner_user_id=owner_user_id,
            )
        except KeyError:
            if not create:
                raise
            state = self.repository.upsert(
                tenant_id=tenant_id,
                entity_type=self.ENTITY,
                entity_id=self.ENTITY_ID,
                owner_user_id=owner_user_id,
                updated_by=owner_user_id,
                payload=self._default_state(owner_user_id=owner_user_id, session_id=session_id),
            )
        changed = False
        if not state.get("sessionId") and session_id:
            state["sessionId"] = session_id
            changed = True
        if not isinstance(state.get("abilities"), dict):
            state["abilities"] = self._default_abilities()
            changed = True
        else:
            defaults = self._default_abilities()
            for aid, row in defaults.items():
                if aid not in state["abilities"]:
                    state["abilities"][aid] = row
                    changed = True
        if changed:
            state = self._save(state, tenant_id=tenant_id, owner_user_id=owner_user_id, updated_by=owner_user_id)
        return state

    def _save(self, state: dict[str, Any], *, tenant_id: str, owner_user_id: str, updated_by: str) -> dict[str, Any]:
        state = dict(state)
        state["updatedAt"] = self._now()
        expected = int(state.get("_version") or 0) or None
        return self.repository.upsert(
            tenant_id=tenant_id,
            entity_type=self.ENTITY,
            entity_id=self.ENTITY_ID,
            owner_user_id=owner_user_id,
            updated_by=updated_by,
            expected_version=expected,
            payload=state,
        )

    @staticmethod
    def _level(row: dict[str, Any]) -> str:
        if int(row.get("combined") or 0) > 0:
            return "能组合起来做"
        if int(row.get("transfer") or 0) > 0:
            return "换个场景也能做"
        if int(row.get("independent") or 0) > 0:
            return "能自己做"
        if int(row.get("guided") or 0) > 0:
            return "能跟着做"
        if int(row.get("attempts") or 0) > 0:
            return "接触过"
        return "还没接触"

    def _current_task(self, state: dict[str, Any]) -> dict[str, Any] | None:
        done = set(state.get("completedTaskIds") or [])
        for task in FOUNDATION_TASKS:
            if task["id"] not in done:
                return task
        return None

    def summary(self, *, tenant_id: str, owner_user_id: str, session_id: str) -> dict[str, Any]:
        state = self.get_state(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        current = self._current_task(state)
        completed = len(state.get("completedTaskIds") or [])
        abilities = list((state.get("abilities") or {}).values())
        later_signals = aggregate_professional_evidence(self.evidence.list_session(session_id, limit=500, tenant_id=tenant_id))
        for row in abilities:
            row["level"] = self._level(row)
            attempts = max(1, int(row.get("attempts") or 0))
            row["average"] = round(float(row.get("scoreTotal") or 0.0) / attempts, 3) if row.get("attempts") else 0.0
            sig = later_signals.get(row.get("id") or "") or {}
            row["laterPracticeCount"] = int(sig.get("count") or 0)
            row["laterVerifiedCount"] = int(sig.get("verifiedCount") or 0)
            row["laterSources"] = list(sig.get("sources") or [])[:8]
            row["repeatedAcrossTasks"] = int(sig.get("count") or 0) >= 2
        complete = current is None and completed >= len(FOUNDATION_TASKS)
        direction = discover_task_preferences(state.get("taskResults") or {})
        return {
            "ok": True,
            "mode": "foundation_complete" if complete else "beginner",
            "foundationComplete": complete,
            "professionalUnlocked": complete and bool(state.get("expression")),
            "completed": completed,
            "total": len(FOUNDATION_TASKS),
            "progress": round(completed / len(FOUNDATION_TASKS), 3),
            "currentTask": public_task(current) if current else None,
            "abilities": abilities,
            "miniProjects": list(state.get("miniProjects") or []),
            "expression": dict(state.get("expression") or {}),
            "direction": direction,
        }

    def get_task(self, task_id: str, *, tenant_id: str, owner_user_id: str, session_id: str) -> dict[str, Any]:
        if task_id not in TASK_BY_ID:
            raise KeyError(task_id)
        state = self.get_state(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        task = TASK_BY_ID[task_id]
        done = set(state.get("completedTaskIds") or [])
        current = self._current_task(state)
        unlocked = task_id in done or (current and current["id"] == task_id)
        if not unlocked:
            raise FoundationError("先把前面这一小步做完")
        return {
            "task": public_task(task),
            "answer": dict((state.get("answers") or {}).get(task_id) or {}),
            "result": dict((state.get("taskResults") or {}).get(task_id) or {}),
            "hintsUsed": int((state.get("hintUsage") or {}).get(task_id) or 0),
            "done": task_id in done,
        }

    def save_answer(self, task_id: str, answer: dict[str, Any], *, tenant_id: str, owner_user_id: str, session_id: str, updated_by: str) -> dict[str, Any]:
        state = self.get_state(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        current = self._current_task(state)
        done = set(state.get("completedTaskIds") or [])
        if task_id not in TASK_BY_ID:
            raise KeyError(task_id)
        if task_id not in done and (not current or current["id"] != task_id):
            raise FoundationError("先把前面这一小步做完")
        answers = dict(state.get("answers") or {})
        answers[task_id] = dict(answer or {})
        state["answers"] = answers
        return self._save(state, tenant_id=tenant_id, owner_user_id=owner_user_id, updated_by=updated_by)

    def hint(self, task_id: str, *, tenant_id: str, owner_user_id: str, session_id: str, updated_by: str) -> dict[str, Any]:
        if task_id not in TASK_BY_ID:
            raise KeyError(task_id)
        task = TASK_BY_ID[task_id]
        state = self.get_state(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        current = self._current_task(state)
        if not current or current["id"] != task_id:
            raise FoundationError("这一步现在不需要提示")
        used = int((state.get("hintUsage") or {}).get(task_id) or 0)
        budget = int(task.get("hintBudget") or 0)
        if used >= budget:
            return {"ok": True, "available": False, "used": used, "budget": budget, "message": "这一步先自己试一次。"}
        hints = task.get("hints") or []
        message = hints[min(used, len(hints) - 1)] if hints else "先只看眼前这一小步，不急着一次做完。"
        usage = dict(state.get("hintUsage") or {})
        usage[task_id] = used + 1
        state["hintUsage"] = usage
        self._save(state, tenant_id=tenant_id, owner_user_id=owner_user_id, updated_by=updated_by)
        return {"ok": True, "available": True, "used": used + 1, "budget": budget, "message": message}

    @staticmethod
    def _reason_ok(answer: dict[str, Any], key: str = "reason", minimum: int = 8) -> bool:
        return len(str(answer.get(key) or "").strip()) >= minimum

    def _validate(self, task: dict[str, Any], answer: dict[str, Any]) -> tuple[bool, float, list[str]]:
        kind = task["type"]
        data = task.get("data") or {}
        issues: list[str] = []
        score = 0.0
        if kind == "order":
            order = answer.get("order") or []
            expected = data.get("expectedTop") or []
            if len(order) != len(data.get("items") or []):
                issues.append("把 4 件事都排一下")
            top = set(order[:2])
            score = min(1.0, len(top & set(expected)) / max(1, len(expected))) * 0.7
            if not self._reason_ok(answer, minimum=12):
                issues.append("说一句你为什么这样排")
            else:
                score += 0.3
        elif kind == "select":
            selected = set(answer.get("selected") or [])
            expected = set(data.get("expected") or [])
            if len(selected) != int(data.get("pick") or 0):
                issues.append(f"只选 {data.get('pick')} 条")
            score = len(selected & expected) / max(1, len(expected))
            if score < 1:
                issues.append("再想一想，哪些信息会直接影响按时完成任务")
        elif kind == "categorize":
            mapping = answer.get("mapping") or {}
            items = data.get("items") or []
            correct = sum(1 for item in items if mapping.get(item["id"]) == item.get("expected"))
            score = correct / max(1, len(items))
            if score < 0.84:
                issues.append("还有几条消息放得不太合适，再看它是要马上处理、需要确认还是只是记录")
        elif kind == "spot_issues":
            selected = set(answer.get("selected") or [])
            expected = set(data.get("expected") or [])
            score = len(selected & expected) / max(1, len(expected))
            if score < 1:
                issues.append("还有明显的问题没找出来")
            if not self._reason_ok(answer, minimum=10):
                issues.append("简单说说为什么这会影响后面的工作")
            else:
                score = min(1.0, score * 0.8 + 0.2)
        elif kind == "handoff":
            fields = answer.get("fields") or {}
            complete = sum(1 for key in ("done", "left", "next") if len(str(fields.get(key) or "").strip()) >= 8)
            score = complete / 3
            if complete < 3:
                issues.append("把已经做到哪、还剩什么、下一步做什么都交代清楚")
        elif kind == "revise":
            revised = str(answer.get("revised") or "").strip()
            reason = str(answer.get("changeReason") or "").strip()
            if len(revised) < 45:
                issues.append("改完以后再具体一点，至少把数字、时间和下一步补清楚")
            if revised == str(data.get("original") or "").strip():
                issues.append("需要真的改出一个新版本")
            if len(reason) < 12:
                issues.append("说一句这次主要改了什么")
            score = min(1.0, len(revised) / 90) * 0.7 + min(1.0, len(reason) / 24) * 0.3
        elif kind == "transfer":
            choice = str(answer.get("choice") or "")
            if choice != str(data.get("expected") or ""):
                issues.append("再比较一下哪件事如果现在不处理，会马上影响更多人")
            if not self._reason_ok(answer, minimum=12):
                issues.append("把判断依据说清楚")
            score = (0.7 if choice == str(data.get("expected") or "") else 0.0) + (0.3 if self._reason_ok(answer, minimum=12) else 0.0)
        elif kind == "mini_project":
            facts = set(answer.get("keyFactIds") or [])
            expected = set(data.get("expectedKey") or [])
            decision = str(answer.get("decision") or "").strip()
            handoff = str(answer.get("handoff") or "").strip()
            overlap = len(facts & expected)
            score = min(1.0, overlap / 3) * 0.35
            if overlap < 2:
                issues.append("先抓到至少两个真正影响处理的重点")
            if len(decision) < 18:
                issues.append("说清楚你准备先处理什么、为什么")
            else:
                score += 0.3
            if len(handoff) < 55:
                issues.append("最后把处理结果整理成一段别人能直接接手的话")
            else:
                score += 0.35
        else:
            issues.append("这个基础任务暂时不能提交")
        ok = not issues and score >= 0.6
        return ok, round(min(1.0, score), 3), issues

    def _update_abilities(self, state: dict[str, Any], task: dict[str, Any], *, score: float, hints_used: int) -> None:
        abilities = dict(state.get("abilities") or self._default_abilities())
        scaffold = str(task.get("scaffold") or "guided")
        for aid in task.get("abilities") or []:
            row = dict(abilities.get(aid) or self._default_abilities().get(aid) or {"id": aid, "name": aid})
            row["attempts"] = int(row.get("attempts") or 0) + 1
            row["scoreTotal"] = round(float(row.get("scoreTotal") or 0.0) + float(score), 3)
            if scaffold in {"guided", "assisted", "revision"}:
                row["guided"] = int(row.get("guided") or 0) + 1
            if scaffold in {"independent", "transfer", "combined"} and hints_used == 0 and score >= 0.7:
                row["independent"] = int(row.get("independent") or 0) + 1
            if scaffold == "transfer" and score >= 0.7:
                row["transfer"] = int(row.get("transfer") or 0) + 1
            if scaffold == "combined" and score >= 0.7:
                row["combined"] = int(row.get("combined") or 0) + 1
            row["level"] = self._level(row)
            abilities[aid] = row
        state["abilities"] = abilities

    def complete_task(self, task_id: str, answer: dict[str, Any], *, tenant_id: str, owner_user_id: str, session_id: str, updated_by: str) -> dict[str, Any]:
        if task_id not in TASK_BY_ID:
            raise KeyError(task_id)
        task = TASK_BY_ID[task_id]
        state = self.get_state(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        done = list(state.get("completedTaskIds") or [])
        if task_id in done:
            return {"ok": True, "alreadyDone": True, "state": self.summary(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)}
        current = self._current_task(state)
        if not current or current["id"] != task_id:
            raise FoundationError("先把前面这一小步做完")
        ok, score, issues = self._validate(task, answer or {})
        if not ok:
            return {"ok": False, "issues": issues, "score": score, "task": public_task(task)}
        hints_used = int((state.get("hintUsage") or {}).get(task_id) or 0)
        answers = dict(state.get("answers") or {})
        answers[task_id] = dict(answer or {})
        state["answers"] = answers
        results = dict(state.get("taskResults") or {})
        result = {
            "taskId": task_id,
            "title": task["title"],
            "score": score,
            "hintsUsed": hints_used,
            "scaffold": task.get("scaffold"),
            "abilities": list(task.get("abilities") or []),
            "answer": dict(answer or {}),
            "completedAt": self._now(),
        }
        evidence = self.evidence.add_structured(
            session_id,
            title=f"基础实践 · {task['title']}",
            action=self._evidence_text(task, answer),
            proof=f"Foundation task {task_id}; score={score}; hints={hints_used}",
            capabilities=[ABILITY_BY_ID.get(aid, {"name": aid})["name"] for aid in task.get("abilities") or []],
            verified=False,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
        )
        result["evidenceId"] = evidence.get("evidence_id") if evidence else ""
        results[task_id] = result
        state["taskResults"] = results
        done.append(task_id)
        state["completedTaskIds"] = done
        state["currentTaskIndex"] = len(done)
        self._update_abilities(state, task, score=score, hints_used=hints_used)

        if task_id == "FND-08-mini-project":
            project = build_first_mini_project(results)
            fact_text = {x["id"]: x["text"] for x in task["data"].get("facts") or []}
            project["keyFacts"] = [fact_text.get(x, x) for x in (answer.get("keyFactIds") or [])]
            projects = list(state.get("miniProjects") or [])
            projects.append(project)
            state["miniProjects"] = projects
            art = self.artifacts.create_workspace_version(
                session_id=session_id,
                title=project["plainTitle"],
                kind="foundation_project",
                content=mini_project_markdown(project),
                evidence_ids=[x.get("evidenceId") for x in results.values() if x.get("evidenceId")],
                tenant_id=tenant_id,
                owner_user_id=owner_user_id,
                created_by=updated_by,
            )
            project["artifactId"] = art.get("artifact_id")
            state["miniProjects"][-1] = project
            state["mode"] = "foundation_complete"
        state = self._save(state, tenant_id=tenant_id, owner_user_id=owner_user_id, updated_by=updated_by)
        return {"ok": True, "score": score, "result": result, "state": self.summary(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)}

    @staticmethod
    def _evidence_text(task: dict[str, Any], answer: dict[str, Any]) -> str:
        kind = task["type"]
        if kind == "order":
            return "完成了 4 项事务排序，并说明了取舍理由。"
        if kind == "select":
            return f"从 6 条材料中选出 {len(answer.get('selected') or [])} 条关键信息。"
        if kind == "categorize":
            return f"把 {len(answer.get('mapping') or {})} 条消息按处理方式分组。"
        if kind == "spot_issues":
            return f"找出明显问题：{', '.join(answer.get('selected') or [])}。理由：{str(answer.get('reason') or '')[:160]}"
        if kind == "handoff":
            f = answer.get("fields") or {}
            return f"完成交接说明：已完成 {f.get('done','')}；还剩 {f.get('left','')}；下一步 {f.get('next','')}。"
        if kind == "revise":
            return f"根据反馈改出新版本，并说明修改点：{str(answer.get('changeReason') or '')[:180]}"
        if kind == "transfer":
            return f"在新场景中独立完成优先判断：{answer.get('choice','')}；理由：{str(answer.get('reason') or '')[:180]}"
        if kind == "mini_project":
            return f"把找重点、判断和交接组合成一次小项目：{str(answer.get('handoff') or '')[:220]}"
        return task.get("title") or "完成一次基础实践"

    def expression(self, reflection: str, *, tenant_id: str, owner_user_id: str, session_id: str, updated_by: str) -> dict[str, Any]:
        state = self.get_state(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        projects = list(state.get("miniProjects") or [])
        if not projects:
            raise FoundationError("先完成第一个小项目，再练怎么把它讲出来")
        output = ExpressionService.build(projects[-1], reflection=reflection)
        state["expression"] = output
        self._save(state, tenant_id=tenant_id, owner_user_id=owner_user_id, updated_by=updated_by)
        art = self.artifacts.create_workspace_version(
            session_id=session_id,
            title="第一次实践怎么讲",
            kind="practice_expression",
            content=f"# 自己复盘\n{output['selfReview']}\n\n# 简历里怎么写\n{output['resume']}\n\n# 面试时怎么讲\n{output['interview90s']}\n",
            evidence_ids=[],
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            created_by=updated_by,
        )
        return {"ok": True, "expression": output, "artifactId": art.get("artifact_id")}

    def teacher_growth(self, *, tenant_id: str, owner_user_id: str, session_id: str) -> dict[str, Any]:
        summary = self.summary(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        state = self.get_state(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        timeline = []
        for task in FOUNDATION_TASKS:
            row = (state.get("taskResults") or {}).get(task["id"])
            if not row:
                continue
            timeline.append({
                "taskId": task["id"], "title": task["title"], "score": row.get("score"), "hintsUsed": row.get("hintsUsed"),
                "scaffold": row.get("scaffold"), "completedAt": row.get("completedAt"),
                "plain": f"{task['title']} · 提示 {row.get('hintsUsed',0)} 次 · 完成度 {round(float(row.get('score') or 0)*100)}%",
            })
        return {"ok": True, "summary": summary, "timeline": timeline}
