from __future__ import annotations

import re
from copy import deepcopy

from .config import Settings
from .evidence_lock import audit_evidence
from .knowledge import KnowledgeStore
from .job_store import JobStore
from .llm_gateway import LLMGateway, LLMGatewayError
from .commercial_store import CommercialStore
from .model_store import ModelConfigStore
from .models import (
    EvidenceAudit,
    KnowledgeRef,
    ProfilePatch,
    ReviewDimension,
    ReviewReport,
    SessionState,
    StudentProfile,
)
from .prompts import COACH_PROMPT, CRITIC_PROMPT, PROFILE_PROMPT, REVIEWER_PROMPT, REVISION_PROMPT, WRITER_PROMPT
from .domain.profile import ParticipantProfile


class CareerAgentService:
    """Business agents decoupled from any single model vendor.

    Each task resolves through llm_routes. Missing routes safely fall back to deterministic demo logic.
    """

    def __init__(self, settings: Settings, model_store: ModelConfigStore, knowledge_store: KnowledgeStore, job_store: JobStore | None = None, commercial_store: CommercialStore | None = None):
        self.settings = settings
        self.model_store = model_store
        self.knowledge_store = knowledge_store
        self.job_store = job_store
        self.commercial_store = commercial_store
        self.gateway = LLMGateway(
            model_store,
            commercial_store=commercial_store,
            retry_attempts=settings.llm_retry_attempts,
            retry_backoff_seconds=settings.llm_retry_backoff_seconds,
            circuit_failure_threshold=settings.llm_circuit_failure_threshold,
            circuit_cooldown_seconds=settings.llm_circuit_cooldown_seconds,
            pii_redaction_enabled=settings.pii_redaction_enabled,
        )

    @property
    def enabled(self) -> bool:
        return (not self.settings.demo_mode) and self.gateway.enabled

    def is_task_enabled(self, task: str) -> bool:
        if self.settings.demo_mode:
            return False
        route = self.model_store.get_route(task)
        if not route:
            return False
        if route.provider_id == "auto" or route.model == "auto":
            return bool(self.gateway.recommend_models_for_task(task))
        provider = self.model_store.get_provider(route.provider_id)
        return bool(provider and provider.enabled and provider.api_key)

    def task_status(self) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for task in ["profile", "coach", "writer", "reviewer", "critic", "revision"]:
            route = self.model_store.get_route(task)
            provider = self.model_store.get_provider(route.provider_id) if route and route.provider_id != "auto" else None
            auto_candidates = self.gateway.recommend_models_for_task(task) if route and (route.provider_id == "auto" or route.model == "auto") else []
            enabled = bool((not self.settings.demo_mode) and route and ((provider and provider.enabled and provider.api_key) or auto_candidates))
            result[task] = {
                "enabled": enabled,
                "provider_id": route.provider_id if route else None,
                "provider_name": (provider.name if provider else ("Auto capability routing" if auto_candidates else None)),
                "model": route.model if route else None,
                "auto_candidates": [{"provider_id": c.get("provider_id"), "model": c.get("model"), "score": c.get("score")} for c in auto_candidates[:3]],
                "fallback_provider_id": route.fallback_provider_id if route else None,
                "fallback_model": route.fallback_model if route else None,
            }
        return result

    def retrieve_context(self, query: str, state: SessionState | None = None) -> tuple[str, list[KnowledgeRef]]:
        scope = state.tenant_id if state else "global"
        return self.knowledge_store.build_context(
            query,
            scope=scope,
            top_k=self.settings.rag_top_k,
            max_chars=self.settings.rag_max_chars,
            tenant_id=(state.tenant_id if state else "global"),
        )

    def retrieve_job_context(self, state: SessionState, limit: int = 5) -> str:
        if not self.job_store or not state.profile.target_job.strip():
            return ""
        rows = self.job_store.search(
            query=state.profile.target_job,
            city=(state.profile.target_cities[0] if state.profile.target_cities else ""),
            industry=state.profile.target_industry,
            limit=limit,
            tenant_id=state.tenant_id,
        )
        if not rows:
            return ""
        blocks = []
        for r in rows:
            salary = ""
            if r.get("salary_min") is not None or r.get("salary_max") is not None:
                salary = f"薪资={r.get('salary_min') or '-'}~{r.get('salary_max') or '-'}"
            blocks.append(
                f"[{r['job_id']}] {r['title']}｜{r['company']}｜{r['city']}｜{r['industry']} {salary}\n"
                f"技能：{'、'.join(r.get('skills') or [])}\n{(r.get('description') or '')[:1200]}"
            )
        return "\n\n".join(blocks)

    async def extract_profile(self, text: str, current: StudentProfile, *, tenant_id: str = "global") -> StudentProfile:
        if not self.is_task_enabled("profile"):
            return self._demo_profile_extract(text, current)
        prompt = (
            "当前画像：\n" + current.model_dump_json(indent=2)
            + "\n\n用户新增信息：\n" + text
            + "\n\n允许输出字段与类型：\n" + ProfilePatch.model_json_schema().__str__()
        )
        try:
            patch, _ = await self.gateway.complete_json("profile", PROFILE_PROMPT, prompt, ProfilePatch, tenant_id=tenant_id)
        except Exception:
            # A profile extraction failure must not block the user's session or invent data.
            return self._demo_profile_extract(text, current)
        data = current.model_dump()
        for key, value in patch.model_dump(exclude_none=True).items():
            if value != "" and value != []:
                data[key] = value
        evidence = data.get("evidence_text", "")
        data["evidence_text"] = (evidence + "\n" + text).strip()
        return StudentProfile.model_validate(data)

    @property
    def _is_competition_mode(self) -> bool:
        return (self.settings.product_preset or "career_development") == "career_competition"

    def _knowledge_query(self, state: SessionState, document_type: str = "", *, purpose: str = "") -> str:
        target = f"{state.profile.target_job} {state.profile.target_industry}".strip()
        if self._is_competition_mode:
            return f"{state.track} {document_type} {purpose or '评分标准 作品规范'} {target}".strip()
        return f"{document_type} {purpose or '评价标准 成果规范'} {target}".strip()

    async def generate_draft(self, state: SessionState, document_type: str, extra: str = "", student_evidence: str = "", teacher_guidance: str = "") -> tuple[str, EvidenceAudit]:
        if not self.is_task_enabled("writer"):
            draft = self._demo_draft(state, document_type)
            return draft, audit_evidence(draft, state.profile.evidence_text)
        query = self._knowledge_query(state, document_type)
        context, _ = self.retrieve_context(query, state)
        job_context = self.retrieve_job_context(state)
        context_label = "赛事/业务规则" if self._is_competition_mode else "业务规则与成果规范"
        track_context = f"赛道：{state.track}\n" if self._is_competition_mode else ""
        prompt = f"""
{track_context}成果类型：{document_type}
参与者画像：
{state.profile.model_dump_json(indent=2)}

已确认事实材料：
{student_evidence or state.profile.evidence_text or '无；不得编造，必须使用待补充占位符。'}

知识库检索材料（{context_label}；仅在相关且来源可靠时使用；不得把知识库中的他人经历当成该参与者事实）：
{context or '未检索到相关知识。'}

结构化岗位数据（如有，属于岗位事实，不属于学生个人经历）：
{job_context or '未命中结构化岗位数据。'}

Advisor / 人工指导意见：
{teacher_guidance or '无'}

额外要求：
{extra or '无'}

请生成可直接继续编辑的完整初稿。涉及外部规则、岗位或机会信息时，优先依据知识库；存在冲突时明确标注需人工核验。
"""
        result = await self.gateway.complete("writer", WRITER_PROMPT, prompt, tenant_id=state.tenant_id)
        draft = result.text.strip()
        return draft, audit_evidence(draft, state.profile.evidence_text)

    async def review(self, state: SessionState, draft: str, student_evidence: str = "") -> ReviewReport:
        if not self.is_task_enabled("reviewer"):
            return self._demo_review(draft, state)
        query = self._knowledge_query(state, state.document_type or "", purpose="评审标准 评价规则 成果要求")
        context, _ = self.retrieve_context(query, state)
        review_context_label = "赛事规则/评分材料" if self._is_competition_mode else "业务规则/评价标准"
        track_context = f"赛道：{state.track}\n" if self._is_competition_mode else ""
        prompt = f"""
{track_context}参与者画像：{state.profile.model_dump_json(indent=2)}
已确认事实材料：{student_evidence or state.profile.evidence_text}

知识库中的{review_context_label}：
{context or '未检索到相关知识。评审需注明规则或标准证据不足。'}

待评作品：
{draft}

输出 JSON schema：
{ReviewReport.model_json_schema()}
"""
        report, _ = await self.gateway.complete_json("reviewer", REVIEWER_PROMPT, prompt, ReviewReport, tenant_id=state.tenant_id)
        # Do not trust a provider-generated total if it diverges from dimensions.
        if report.dimensions:
            computed = sum(d.score for d in report.dimensions)
            if 0 <= computed <= 100:
                report.total_score = computed
        return report

    async def critic(self, state: SessionState, draft: str, review: ReviewReport, teacher_guidance: str = "") -> str:
        if not self.is_task_enabled("critic"):
            return "重点复核：是否存在无证据的高分项；目标明确不等于目标合理；所有量化成果必须回到事实材料核验。"
        query = self._knowledge_query(state, state.document_type or "", purpose="评审标准 成果要求")
        context, _ = self.retrieve_context(query, state)
        prompt = f"""知识库规则：\n{context or '无'}\n\nAdvisor / 人工指导意见：\n{teacher_guidance or '无'}\n\n原稿：\n{draft}\n\n评审报告：\n{review.model_dump_json(indent=2)}"""
        result = await self.gateway.complete("critic", CRITIC_PROMPT, prompt, tenant_id=state.tenant_id)
        return result.text.strip()

    async def revise(self, state: SessionState, draft: str, review: ReviewReport, student_evidence: str = "", teacher_guidance: str = "") -> tuple[str, EvidenceAudit, str]:
        critic = await self.critic(state, draft, review, teacher_guidance=teacher_guidance)
        if not self.is_task_enabled("revision"):
            revised = self._demo_revision(draft, review)
            return revised, audit_evidence(revised, state.profile.evidence_text), critic
        query = self._knowledge_query(state, state.document_type or "", purpose="评价标准 成果规范")
        context, _ = self.retrieve_context(query, state)
        prompt = f"""
赛道：{state.track}
已确认事实材料：
{student_evidence or state.profile.evidence_text}

Advisor / 人工指导意见：
{teacher_guidance or '无'}

知识库相关材料：
{context or '无'}

原稿：
{draft}

评审报告：
{review.model_dump_json(indent=2)}

质疑意见：
{critic}

请输出修订后的完整作品，不要解释修改过程。任何参与者个人事实只能来自“已确认事实材料”。
"""
        result = await self.gateway.complete("revision", REVISION_PROMPT, prompt, tenant_id=state.tenant_id)
        revised = result.text.strip()
        return revised, audit_evidence(revised, state.profile.evidence_text), critic

    async def coach(self, state: SessionState, message: str, locale: str = "zh-CN") -> tuple[str, list[KnowledgeRef]]:
        if not self.is_task_enabled("coach"):
            return self._demo_coach(state, message, locale=locale), []
        query = f"{message} {state.track if self._is_competition_mode else ''} {state.profile.target_job} {state.profile.major}".strip()
        context, refs = self.retrieve_context(query, state)
        job_context = self.retrieve_job_context(state)
        slim_state = state.model_dump(exclude={"draft", "revised_draft"})
        prompt = f"""
当前状态：{slim_state}
参与者消息：{message}

知识库检索：
{context or '未检索到直接相关材料。'}

结构化岗位数据：
{job_context or '未命中结构化岗位数据。'}

回答要求：
- 一次只推进最关键下一步；
- 涉及外部规则、评价口径、岗位或机会事实时，只能使用知识库命中的信息，并用“【来源：资料名】”标出；
- 未命中可靠知识时明确说需要核验，不要凭记忆编造；
- 参与者个人经历只能来自其画像与事实材料。
- 输出语言：{"English" if locale == "en-US" else "简体中文"}。Evidence ID、来源标题和用户原文不得翻译或改写。
"""
        result = await self.gateway.complete("coach", COACH_PROMPT, prompt, tenant_id=state.tenant_id)
        return result.text.strip(), refs

    @staticmethod
    def _demo_profile_extract(text: str, current: StudentProfile) -> StudentProfile:
        data = deepcopy(current.model_dump())
        # Canonical generic labels first; legacy campus labels remain accepted as preset-compatible aliases.
        label_map = {
            "显示名": "name", "姓名": "name",
            "所属组织": "school", "学校": "school",
            "背景方向": "major", "专业": "major",
            "当前阶段": "grade", "年级": "grade",
            "教育背景": "degree", "学历": "degree",
            "目标方向": "target_job", "目标岗位": "target_job",
            "目标领域": "target_industry", "目标行业": "target_industry",
        }
        for line in text.splitlines():
            clean = line.strip()
            for label, field in label_map.items():
                for sep in ("：", ":"):
                    prefix = f"{label}{sep}"
                    if clean.startswith(prefix):
                        value = clean[len(prefix):].strip()
                        if value:
                            data[field] = value
        if not data.get("target_job"):
            m = re.search(r"(?:目标方向|目标岗位|想做|想从事|希望从事)[：: ]*([^，。；\n]{2,40})", text)
            if m:
                data["target_job"] = m.group(1).strip()
        # Campus-specific inference remains optional compatibility behavior; it does not define Core identity.
        if not data.get("grade"):
            m = re.search(r"(大[一二三四五]|研[一二三]|博士[一二三四五]|本科[一二三四五])", text)
            if m:
                data["grade"] = m.group(1)
        if not data.get("major"):
            m = re.search(r"(?:我是|就读|读)([\u4e00-\u9fa5A-Za-z0-9·]{2,20})专业", text)
            if m:
                data["major"] = m.group(1)
        data["evidence_text"] = (data.get("evidence_text", "") + "\n" + text).strip()
        return StudentProfile.model_validate(data)

    @staticmethod
    def _demo_draft(state: SessionState, document_type: str) -> str:
        p = ParticipantProfile.from_legacy(state.profile)
        display_name = p.display_name or "Demo User"
        target = p.target_opportunity or "【待补充：目标方向】"
        education = "；".join(p.education) or "【待补充：教育或学习背景】"
        experience = p.experience + p.projects
        if document_type == "简历":
            return f"""# {display_name} — Resume Draft

## Target
目标方向：{target}
目标领域：{p.target_industry or '【待补充：目标领域】'}

## Background
{education}

## Evidence-backed Experience
{chr(10).join('- ' + x for x in experience) or '- 【待补充：仅填写真实发生的经历，并说明个人动作与可核验结果】'}

## Skills
{', '.join(p.skills) or '【待补充：技能及对应证据】'}

> DEMO_MODE：未调用真实大模型。正式环境请在管理端配置 Provider 与 Agent Route。
"""
        return f"""# Career Development Report Draft

## 1. Current Foundation
当前背景：{p.background or '【待补充：背景方向】'}。
可核验经历：
{chr(10).join('- ' + x for x in experience) or '- 【待补充：真实学习、实践、项目或工作经历】'}

## 2. Development Goal
目标方向：{target}。
选择依据：【待补充：用兴趣、能力、经历和外部机会证据解释选择依据】。

## 3. Requirement & Gap Analysis
【待补充：依据可靠机会/岗位信息列出核心要求，并逐项与个人 Evidence 对照。】

## 4. Action Plan
【待补充：按阶段拆解行动、完成标准、证据产出与复盘节点。】

## 5. Dynamic Adjustment
【待补充：说明环境、机会或个人条件变化时如何重新评估并修正路径。】

> DEMO_MODE：未调用真实大模型。正式环境请在管理端配置 Provider 与 Agent Route。
"""

    def _demo_review(self, draft: str, state: SessionState) -> ReviewReport:
        placeholders = draft.count("待补充")
        base = max(6, 16 - min(placeholders, 8))
        dims = [
            ReviewDimension(name="内容完整性", score=base, problems=["仍有关键事实缺口"] if placeholders else [], actions=["补齐所有待补充字段并核验事实来源"]),
            ReviewDimension(name="逻辑清晰度", score=14, problems=["目标—证据—行动链需进一步显性化"], actions=["按证据→目标→差距→行动重排"]),
            ReviewDimension(name="数据/案例支撑", score=8 if not state.profile.evidence_text else 13, problems=["事实材料仍不足或未完全转化为证据"], actions=["补充可核验经历、职责、成果和来源"]),
            ReviewDimension(name="个性化程度", score=12, problems=["部分结构仍偏模板化"], actions=["用个人真实决策节点替换通用表述"]),
            ReviewDimension(
                name="目标匹配度",
                score=(12 if state.track == "待确认" else 15) if self._is_competition_mode else 14,
                problems=(["需对照当前有效规则复核"] if state.track == "待确认" else []) if self._is_competition_mode else ["目标、证据与行动之间仍需建立更明确的对应关系"],
                actions=(["加入与当前有效评价规则的一一对应"] if self._is_competition_mode else ["逐项建立目标要求—Evidence—行动的映射"]),
            ),
        ]
        total = sum(d.score for d in dims)
        competition_unconfirmed = self._is_competition_mode and state.track == "待确认"
        return ReviewReport(
            total_score=total,
            dimensions=dims,
            fatal_issues=["业务赛道尚未最终确认，评价口径可能发生变化。"] if competition_unconfirmed else [],
            structural_issues=["证据链需要继续强化。"],
            surface_issues=["删除模板化提示语与占位符。"],
            overall_comment="当前为可运行 Demo 的结构性评审，不等同于真实大模型评审结果。",
            revision_priority=(["确认业务赛道"] if competition_unconfirmed else []) + ["补足真实事实材料", "强化证据链", "最后处理语言"],
        )

    @staticmethod
    def _demo_revision(draft: str, review: ReviewReport) -> str:
        return draft.replace(
            "> DEMO_MODE 初稿：未调用大模型。请在管理端配置模型路由后切换真实 Agent。",
            "> DEMO_MODE 修订版：已按结构性规则复核；待补充项仍需用户提供真实事实后才能消除。",
        ).replace(
            "> DEMO_MODE 初稿：未调用大模型。关闭 DEMO_MODE 并配置 API Key 后启用真实 Writer Agent。",
            "> DEMO_MODE 修订版：已按结构性规则复核；待补充项仍需用户提供真实事实后才能消除。",
        )

    def _demo_coach(self, state: SessionState, message: str, locale: str = "zh-CN") -> str:
        english = locale == "en-US"
        if not state.profile.evidence_text:
            if self._is_competition_mode:
                return ("First, add verified facts: your current stage, target direction, one to three real experiences, "
                        "and what you personally did in each experience.") if english else "下一步先补充真实事实材料：当前阶段、目标方向、1—3段真实经历，以及每段经历中你实际做了什么。"
            return ("First, add verified facts: your background, target direction, one to three real experiences, "
                    "and what you personally did in each experience.") if english else "下一步先补充真实事实材料：你的当前背景、目标方向、1—3段真实经历，以及每段经历中你实际做了什么。"
        if self._is_competition_mode and state.track == "待确认":
            return ("Next, confirm the competition track against current eligibility rules. Do not rely only on model inference."
                    if english else "下一步确认业务赛道。请结合当前有效规则与资格要求进行核验，不要仅依赖模型推断。")
        if not state.draft:
            if self._is_competition_mode:
                return (f"The current track is {state.track}. Next, generate the first artifact draft using only confirmed facts; "
                        "missing facts remain explicitly marked.") if english else f"当前已进入“{state.track}”。下一步生成成果初稿；所有事实仅从已确认材料调用，缺失部分保留待补充标记。"
            return ("Next, generate the first artifact. The system uses only confirmed facts and traceable Evidence; "
                    "missing information remains marked and is never invented.") if english else "下一步生成第一版成果物。系统只使用已确认事实与可追踪 Evidence；缺失信息保留待补充，不会自动编造。"
        if not state.review:
            return ("A draft is ready. Run a rigorous review of the goal–evidence–action chain before language polishing."
                    if english else "已有初稿。下一步执行严格评审，优先检查目标—证据—行动链和事实支撑，而不是先润色语言。")
        if not state.revised_draft:
            return ("The review is ready. Next, let the Critic Agent verify the key issues and the Revision Agent revise from evidence."
                    if english else "已有评审报告。下一步由 Critic Agent 复核关键问题，再由 Revision Agent 基于证据完成修订。")
        return ("The core workflow is complete. Add more verified evidence, run another review, or continue with advisor feedback and interview training."
                if english else "核心闭环已跑通。可继续补充真实材料、重新评审，或进入 Advisor 反馈、展示与模拟训练阶段。")



# Backward-compatible alias for integrations built before v0.9.
CompetitionAgentService = CareerAgentService
