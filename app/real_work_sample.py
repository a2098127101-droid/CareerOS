from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from .foundation_abilities import ABILITY_BY_ID
from .unified_runtime_store import RuntimeVersionConflict


WORK_SAMPLE_ID = "RWS-001-support-triage"
WORK_SAMPLE_VERSION = "1.0"
CORE_CAPABILITIES = [
    "understand_task",
    "extract_info",
    "organize_info",
    "judge",
    "spot_problem",
    "explain_reason",
    "deliver_clear",
]
REVISION_CAPABILITIES = CORE_CAPABILITIES + ["revise_feedback"]
TRANSFER_CAPABILITIES = CORE_CAPABILITIES + ["transfer"]


class RealWorkSampleError(RuntimeError):
    pass


WORK_SAMPLE = {
    "id": WORK_SAMPLE_ID,
    "version": WORK_SAMPLE_VERSION,
    "title": "高峰时段支持工单交接",
    "roleContext": "你临时加入支持运营值班。现在是周三 10:05，主管 10:30 要接手。你不直接替客户解决问题，只负责把眼前材料整理成一份可以继续处理的交接。",
    "deliverable": "一份高峰时段交接：哪些事项先处理、为什么、已知风险、下一步由谁做什么。",
    "constraints": [
        "10:30 前交给主管",
        "不能把不确定信息写成已确认事实",
        "优先级必须能从现有材料中找到依据",
        "第一版会收到主管反馈，随后要改出 V2",
    ],
    "materials": {
        "messages": [
            {"id": "M-201", "time": "09:42", "from": "客户A", "text": "我已经付款，但订单一直显示未支付。上午已经问过一次，今天要安排发货。"},
            {"id": "M-202", "time": "09:50", "from": "客户B", "text": "发票抬头想改一下，今天下班前能处理就可以。"},
            {"id": "M-203", "time": "09:56", "from": "活动负责人", "text": "报名链接打不开，40名同学今天12:00前必须完成报名。群里已经有多人反馈。"},
            {"id": "M-204", "time": "10:01", "from": "同事", "text": "帮助中心有一个错别字，方便的时候改一下。"},
        ],
        "tickets": [
            {"id": "T-201", "subject": "支付后订单状态未更新", "deadline": "今天发货前", "impact": "1名客户，已连续追问", "status": "待核对支付记录"},
            {"id": "T-202", "subject": "修改发票抬头", "deadline": "今天下班前", "impact": "1名客户", "status": "信息已齐"},
            {"id": "T-203", "subject": "活动报名链接不可用", "deadline": "12:00", "impact": "40名报名者", "status": "多人复现"},
            {"id": "T-204", "subject": "帮助中心文字修正", "deadline": "无明确截止", "impact": "不影响当前操作", "status": "待编辑"},
        ],
        "customerSignals": [
            {"id": "S-201", "type": "payment", "text": "客户A上传了支付成功截图，但系统订单状态仍为待支付。截图只能证明支付动作，不能单独证明平台已完成入账核对。"},
            {"id": "S-203", "type": "incident", "text": "报名链接在不同手机上均无法打开，负责人确认12:00后不再接收报名。"},
        ],
    },
    "transfer": {
        "title": "换一组材料，再做一次交接",
        "roleContext": "第二天 10:20，你接到另一组运营材料。11:00 前需要把最需要先处理的事项交给下一位同事，这次没有主管反馈提示。",
        "materials": [
            {"id": "X-301", "subject": "批量订单队列停止推进", "deadline": "10:45前恢复或升级", "impact": "23笔订单无法进入下一环节", "detail": "系统监控已连续10分钟无新任务出队。"},
            {"id": "X-302", "subject": "客户想修改收货地址", "deadline": "11:30前仓库出库", "impact": "1名客户", "detail": "地址信息完整，尚未出库。"},
            {"id": "X-303", "subject": "周报数字格式不统一", "deadline": "周五16:00", "impact": "内部报告", "detail": "内容本身已齐。"},
            {"id": "X-304", "subject": "优惠券规则咨询", "deadline": "无明确截止", "impact": "1名客户", "detail": "知识库已有说明。"},
        ],
    },
}

_EXPECTED_MAIN = {"T-201", "T-203"}
_EXPECTED_TRANSFER = {"X-301", "X-302"}


class RealWorkSampleService:
    ENTITY_TYPE = "real_work_sample_state"

    def __init__(
        self,
        *,
        repository: Any,
        foundation: Any,
        evidence: Any,
        artifacts: Any,
        observation_sink: Callable[..., Any] | None = None,
    ):
        self.repository = repository
        self.foundation = foundation
        self.evidence = evidence
        self.artifacts = artifacts
        self.observation_sink = observation_sink

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _capability_names(ids: list[str]) -> list[str]:
        return [str((ABILITY_BY_ID.get(capability_id) or {}).get("name") or capability_id) for capability_id in ids]

    def _emit(self, **event: Any) -> None:
        if self.observation_sink is None:
            return
        try:
            self.observation_sink(**event)
        except Exception:
            return

    def _default(self, *, owner_user_id: str, session_id: str) -> dict[str, Any]:
        return {
            "id": WORK_SAMPLE_ID,
            "version": WORK_SAMPLE_VERSION,
            "ownerUserId": owner_user_id,
            "sessionId": session_id,
            "status": "ready",
            "startedAt": "",
            "v1": {},
            "supervisorFeedback": [],
            "v2": {},
            "transfer": {},
            "artifactId": "",
            "evidenceIds": [],
            "updatedAt": self._now(),
        }

    def _load(self, *, tenant_id: str, owner_user_id: str, session_id: str, create: bool = False) -> dict[str, Any] | None:
        try:
            return self.repository.get(
                tenant_id=tenant_id,
                entity_type=self.ENTITY_TYPE,
                entity_id=WORK_SAMPLE_ID,
                owner_user_id=owner_user_id,
            )
        except KeyError:
            if not create:
                return None
            return self.repository.upsert(
                tenant_id=tenant_id,
                entity_type=self.ENTITY_TYPE,
                entity_id=WORK_SAMPLE_ID,
                owner_user_id=owner_user_id,
                updated_by=owner_user_id,
                payload=self._default(owner_user_id=owner_user_id, session_id=session_id),
            )

    def _save(self, state: dict[str, Any], *, tenant_id: str, owner_user_id: str, updated_by: str) -> dict[str, Any]:
        clean = {k: v for k, v in dict(state).items() if not k.startswith("_") and k != "entity_type"}
        clean["updatedAt"] = self._now()
        expected = int(state.get("_version") or 0) or None
        return self.repository.upsert(
            tenant_id=tenant_id,
            entity_type=self.ENTITY_TYPE,
            entity_id=WORK_SAMPLE_ID,
            owner_user_id=owner_user_id,
            updated_by=updated_by,
            expected_version=expected,
            payload=clean,
        )

    def _foundation_ready(self, *, tenant_id: str, owner_user_id: str, session_id: str) -> bool:
        summary = self.foundation.summary(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        return bool(summary.get("foundationComplete"))

    def public_state(self, *, tenant_id: str, owner_user_id: str, session_id: str) -> dict[str, Any]:
        unlocked = self._foundation_ready(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        state = self._load(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id, create=False)
        value = state or self._default(owner_user_id=owner_user_id, session_id=session_id)
        return {
            "id": WORK_SAMPLE_ID,
            "version": WORK_SAMPLE_VERSION,
            "unlocked": unlocked,
            "status": str(value.get("status") or "ready") if unlocked else "locked",
            "definition": WORK_SAMPLE,
            "v1": dict(value.get("v1") or {}),
            "supervisorFeedback": list(value.get("supervisorFeedback") or []),
            "v2": dict(value.get("v2") or {}),
            "transferSubmission": dict(value.get("transfer") or {}),
            "artifactId": str(value.get("artifactId") or ""),
            "evidenceIds": list(value.get("evidenceIds") or []),
            "unlockReason": "完成 Foundation 八个基础实践后开放" if not unlocked else "",
            "authority": "server",
        }

    def start(self, *, tenant_id: str, owner_user_id: str, session_id: str, updated_by: str) -> dict[str, Any]:
        if not self._foundation_ready(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id):
            raise RealWorkSampleError("先完成 Foundation 八个基础实践，再进入真实工作样本")
        state = self._load(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id, create=True)
        assert state is not None
        if not state.get("startedAt"):
            state["startedAt"] = self._now()
            state["status"] = "working_v1"
            state = self._save(state, tenant_id=tenant_id, owner_user_id=owner_user_id, updated_by=updated_by)
            self._emit(
                event_type="work_sample_started",
                source="real_work_sample",
                tenant_id=tenant_id,
                owner_user_id=owner_user_id,
                session_id=session_id,
                actor_user_id=updated_by,
                task_id=f"{WORK_SAMPLE_ID}:main",
                outcome="neutral",
                payload={"capabilityIds": CORE_CAPABILITIES},
            )
        return self.public_state(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)

    @staticmethod
    def _submission(priority_ticket_ids: list[str], handoff: str, work_notes: str) -> dict[str, Any]:
        return {
            "priorityTicketIds": [str(x) for x in priority_ticket_ids][:6],
            "handoff": str(handoff or "").strip()[:8000],
            "workNotes": str(work_notes or "").strip()[:8000],
        }

    @staticmethod
    def _basic_issues(submission: dict[str, Any]) -> list[str]:
        issues: list[str] = []
        if len(submission.get("priorityTicketIds") or []) < 2:
            issues.append("至少明确两个需要优先处理的事项")
        if len(str(submission.get("handoff") or "")) < 70:
            issues.append("交接还太短，需要让下一位知道优先事项、依据和下一步")
        if len(str(submission.get("workNotes") or "")) < 30:
            issues.append("保留一点工作过程：你主要按什么标准判断优先级")
        return issues

    @staticmethod
    def _supervisor_feedback(submission: dict[str, Any]) -> list[str]:
        selected = set(submission.get("priorityTicketIds") or [])
        handoff = str(submission.get("handoff") or "")
        feedback: list[str] = []
        if len(selected & _EXPECTED_MAIN) < 2:
            feedback.append("再核对一次影响范围和最近截止时间：现在的排序还没有把最容易造成即时阻塞的事项都放到前面。")
        if not any(token in handoff for token in ("12:00", "12点", "中午")):
            feedback.append("交接里缺少一个会直接改变优先级的明确截止时间。")
        if not any(token in handoff for token in ("40", "多人", "报名者")):
            feedback.append("补清楚受影响对象或范围，否则下一位很难理解为什么要先处理。")
        if not any(token in handoff for token in ("下一步", "先", "核对", "升级", "联系", "处理")):
            feedback.append("最后需要落到具体下一步，不要只停在问题描述。")
        if not feedback:
            feedback.append("第一版的重点基本抓住了。现在不要只是润色措辞，改成更适合交接的结构：当前风险、处理顺序、依据、下一步。")
        return feedback[:4]

    def submit_v1(
        self,
        *,
        priority_ticket_ids: list[str],
        handoff: str,
        work_notes: str,
        tenant_id: str,
        owner_user_id: str,
        session_id: str,
        updated_by: str,
    ) -> dict[str, Any]:
        state = self._load(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id, create=True)
        assert state is not None
        if not self._foundation_ready(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id):
            raise RealWorkSampleError("真实工作样本尚未开放")
        submission = self._submission(priority_ticket_ids, handoff, work_notes)
        issues = self._basic_issues(submission)
        if issues:
            return {"ok": False, "issues": issues, "state": self.public_state(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)}

        feedback = self._supervisor_feedback(submission)
        evidence = self.evidence.add_structured(
            session_id,
            title="工作样本 · 高峰工单交接 V1",
            action=submission["handoff"],
            proof="真实工作样本第一版；保留优先级选择与工作过程，不代表能力已核验。",
            capabilities=self._capability_names(CORE_CAPABILITIES),
            verified=False,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
        )
        artifact = self.artifacts.create_workspace_version(
            session_id=session_id,
            title="高峰时段支持工单交接",
            kind="real_work_sample",
            content=self._markdown("V1", submission, feedback),
            evidence_ids=[evidence.get("evidence_id")],
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            created_by=updated_by,
        )
        state["v1"] = {**submission, "submittedAt": self._now(), "evidenceId": evidence.get("evidence_id")}
        state["supervisorFeedback"] = feedback
        state["artifactId"] = artifact.get("artifact_id") or ""
        state["evidenceIds"] = list(dict.fromkeys(list(state.get("evidenceIds") or []) + [evidence.get("evidence_id")]))
        state["status"] = "revision_required"
        self._save(state, tenant_id=tenant_id, owner_user_id=owner_user_id, updated_by=updated_by)
        self._emit(
            event_type="work_sample_v1_submitted",
            source="real_work_sample",
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            actor_user_id=updated_by,
            task_id=f"{WORK_SAMPLE_ID}:main",
            evidence_id=str(evidence.get("evidence_id") or ""),
            outcome="neutral",
            payload={"capabilityIds": CORE_CAPABILITIES, "independent": True, "feedbackCount": len(feedback)},
        )
        return {"ok": True, "feedback": feedback, "state": self.public_state(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)}

    def submit_v2(
        self,
        *,
        priority_ticket_ids: list[str],
        handoff: str,
        work_notes: str,
        tenant_id: str,
        owner_user_id: str,
        session_id: str,
        updated_by: str,
    ) -> dict[str, Any]:
        state = self._load(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id, create=False)
        if not state or not state.get("v1"):
            raise RealWorkSampleError("先提交 V1 并读取主管反馈")
        submission = self._submission(priority_ticket_ids, handoff, work_notes)
        issues = self._basic_issues(submission)
        if submission.get("handoff") == (state.get("v1") or {}).get("handoff"):
            issues.append("V2 需要发生实质修改，不能原样再次提交")
        selected = set(submission.get("priorityTicketIds") or [])
        if len(selected & _EXPECTED_MAIN) < 2:
            issues.append("再比较影响范围、最近截止时间和不处理的直接后果")
        text = submission.get("handoff") or ""
        if not any(token in text for token in ("12:00", "12点", "中午")):
            issues.append("把会改变处理顺序的明确截止时间写进交接")
        if not any(token in text for token in ("40", "多人", "报名者")):
            issues.append("把受影响范围交代清楚")
        if issues:
            return {"ok": False, "issues": list(dict.fromkeys(issues)), "state": self.public_state(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)}

        evidence = self.evidence.add_structured(
            session_id,
            title="工作样本 · 高峰工单交接 V2",
            action=submission["handoff"],
            proof="根据主管反馈完成实质修订；仍需迁移表现与规范核验才能进入 Verified Evidence。",
            capabilities=self._capability_names(REVISION_CAPABILITIES),
            verified=False,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
        )
        artifact = self.artifacts.create_workspace_version(
            session_id=session_id,
            title="高峰时段支持工单交接",
            kind="real_work_sample",
            content=self._markdown("V2", submission, list(state.get("supervisorFeedback") or [])),
            evidence_ids=list(dict.fromkeys(list(state.get("evidenceIds") or []) + [evidence.get("evidence_id")])),
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            created_by=updated_by,
            artifact_id=str(state.get("artifactId") or "") or None,
        )
        state["v2"] = {**submission, "submittedAt": self._now(), "evidenceId": evidence.get("evidence_id")}
        state["artifactId"] = artifact.get("artifact_id") or state.get("artifactId") or ""
        state["evidenceIds"] = list(dict.fromkeys(list(state.get("evidenceIds") or []) + [evidence.get("evidence_id")]))
        state["status"] = "transfer_ready"
        self._save(state, tenant_id=tenant_id, owner_user_id=owner_user_id, updated_by=updated_by)
        self._emit(
            event_type="work_sample_v2_submitted",
            source="real_work_sample",
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            actor_user_id=updated_by,
            task_id=f"{WORK_SAMPLE_ID}:main",
            evidence_id=str(evidence.get("evidence_id") or ""),
            outcome="success",
            payload={"capabilityIds": REVISION_CAPABILITIES, "independent": True, "revision": True},
        )
        return {"ok": True, "state": self.public_state(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)}

    def submit_transfer(
        self,
        *,
        priority_ticket_ids: list[str],
        handoff: str,
        work_notes: str,
        tenant_id: str,
        owner_user_id: str,
        session_id: str,
        updated_by: str,
    ) -> dict[str, Any]:
        state = self._load(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id, create=False)
        if not state or not state.get("v2"):
            raise RealWorkSampleError("先完成根据反馈修改后的 V2")
        submission = self._submission(priority_ticket_ids, handoff, work_notes)
        issues = self._basic_issues(submission)
        selected = set(submission.get("priorityTicketIds") or [])
        if len(selected & _EXPECTED_TRANSFER) < 2:
            issues.append("新材料里还有一个更接近截止且影响范围更大的事项没有进入优先交接")
        text = submission.get("handoff") or ""
        if not any(token in text for token in ("10:45", "10点45", "23")):
            issues.append("用新材料里的时间或影响范围说明你的排序依据")
        if issues:
            self._emit(
                event_type="transfer_failed",
                source="real_work_sample",
                tenant_id=tenant_id,
                owner_user_id=owner_user_id,
                session_id=session_id,
                actor_user_id=updated_by,
                task_id=f"{WORK_SAMPLE_ID}:transfer",
                outcome="failure",
                payload={"capabilityIds": TRANSFER_CAPABILITIES, "issues": list(dict.fromkeys(issues)), "independent": True},
            )
            return {"ok": False, "issues": list(dict.fromkeys(issues)), "state": self.public_state(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)}

        evidence = self.evidence.add_structured(
            session_id,
            title="工作样本 · 换材料独立交接",
            action=submission["handoff"],
            proof="在新的运营材料中无主管提示完成同类优先级判断与交接。",
            capabilities=self._capability_names(TRANSFER_CAPABILITIES),
            verified=False,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
        )
        self.artifacts.create_workspace_version(
            session_id=session_id,
            title="换材料独立交接",
            kind="real_work_sample_transfer",
            content=self._markdown("Transfer", submission, []),
            evidence_ids=[evidence.get("evidence_id")],
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            created_by=updated_by,
        )
        state["transfer"] = {**submission, "submittedAt": self._now(), "evidenceId": evidence.get("evidence_id")}
        state["evidenceIds"] = list(dict.fromkeys(list(state.get("evidenceIds") or []) + [evidence.get("evidence_id")]))
        state["status"] = "completed"
        self._save(state, tenant_id=tenant_id, owner_user_id=owner_user_id, updated_by=updated_by)
        self._emit(
            event_type="work_sample_transfer_completed",
            source="real_work_sample",
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            actor_user_id=updated_by,
            task_id=f"{WORK_SAMPLE_ID}:transfer",
            evidence_id=str(evidence.get("evidence_id") or ""),
            outcome="success",
            payload={"capabilityIds": TRANSFER_CAPABILITIES, "independent": True, "transfer": True},
        )
        return {"ok": True, "state": self.public_state(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)}

    @staticmethod
    def _markdown(label: str, submission: dict[str, Any], feedback: list[str]) -> str:
        selected = "、".join(submission.get("priorityTicketIds") or [])
        lines = [
            f"# {label}",
            "",
            f"优先事项：{selected}",
            "",
            "## 交接",
            str(submission.get("handoff") or ""),
            "",
            "## 工作过程",
            str(submission.get("workNotes") or ""),
        ]
        if feedback:
            lines.extend(["", "## 主管反馈", *[f"- {item}" for item in feedback]])
        return "\n".join(lines)
