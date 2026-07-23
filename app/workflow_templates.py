from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowStepDefinition:
    step_id: str
    index: int
    label: str
    description: str
    required_evidence: bool = False
    required_artifact: str = ""


@dataclass(frozen=True)
class WorkflowTemplate:
    template_id: str
    preset_id: str
    name: str
    steps: tuple[WorkflowStepDefinition, ...]


def _steps(items: list[tuple[str, str, str, bool, str]]) -> tuple[WorkflowStepDefinition, ...]:
    return tuple(
        WorkflowStepDefinition(step_id=sid, index=i + 1, label=label, description=desc,
                               required_evidence=req_ev, required_artifact=req_art)
        for i, (sid, label, desc, req_ev, req_art) in enumerate(items)
    )


TEMPLATES: dict[str, WorkflowTemplate] = {
    "career_development": WorkflowTemplate(
        "career_development_v1", "career_development", "Career Development",
        _steps([
            ("self_exploration", "自我探索", "建立可核验的经历、兴趣与能力基础。", True, ""),
            ("career_positioning", "职业定位", "收敛发展方向并形成选择依据。", True, ""),
            ("target_role", "目标方向", "明确职业、岗位或发展机会边界。", False, ""),
            ("person_job_match", "能力匹配", "把个人证据与目标机会要求对应。", True, ""),
            ("gap_analysis", "差距分析", "识别证据、能力与成果结构缺口。", True, ""),
            ("growth_path", "成长路径", "形成可执行的阶段行动方案。", False, "action_plan"),
            ("resume", "履历成果", "生成并迭代与目标方向匹配的履历型成果。", False, "resume"),
            ("career_report", "发展报告", "形成可追踪证据的职业发展成果。", True, "career_report"),
            ("ppt", "展示材料", "形成结构化展示材料并建立证据链。", True, "presentation"),
            ("mock_defense", "模拟训练", "进行面试、陈述或问答训练并复盘。", False, "mock_defense"),
        ]),
    ),
    "campus_career": WorkflowTemplate(
        "campus_career_v1", "campus_career", "Campus Career Education",
        _steps([
            ("self_exploration", "自我认知", "建立学生可核验的经历、兴趣、能力与成长证据。", True, ""),
            ("career_positioning", "方向探索", "比较职业方向并形成选择依据。", True, ""),
            ("target_role", "目标职业", "明确目标职业、岗位或升学发展方向。", False, ""),
            ("person_job_match", "能力匹配", "映射已有能力证据与目标要求。", True, ""),
            ("gap_analysis", "差距诊断", "识别能力、经历与成果缺口。", True, ""),
            ("growth_path", "成长行动", "形成课程、实践与项目行动计划。", False, "action_plan"),
            ("resume", "简历", "形成与目标方向一致的简历。", False, "resume"),
            ("career_report", "发展报告", "沉淀阶段性生涯发展成果。", True, "career_report"),
            ("ppt", "展示材料", "生成展示或汇报材料。", True, "presentation"),
            ("mock_defense", "模拟训练", "进行面试或陈述训练。", False, "mock_defense"),
        ]),
    ),
    "career_service": WorkflowTemplate(
        "career_service_v1", "career_service", "Career Service",
        _steps([
            ("self_exploration", "客户画像", "整理可核验的经历、能力与约束。", True, ""),
            ("target_role", "目标机会", "明确岗位、行业与机会边界。", False, ""),
            ("person_job_match", "机会匹配", "将证据与岗位要求逐项映射。", True, ""),
            ("gap_analysis", "差距诊断", "识别关键缺口与优先级。", True, ""),
            ("growth_path", "行动方案", "形成短中期求职与能力提升计划。", False, "action_plan"),
            ("resume", "申请材料", "生成履历、申请或作品集成果。", True, "resume"),
            ("mock_defense", "面试训练", "进行模拟面试并复盘。", False, "mock_defense"),
        ]),
    ),
    "career_competition": WorkflowTemplate(
        "career_competition_v1", "career_competition", "Career Competition",
        _steps([
            ("self_exploration", "个人画像", "建立可核验的成长与能力证据。", True, ""),
            ("career_positioning", "职业定位", "明确参赛职业方向与定位依据。", True, ""),
            ("target_role", "目标职业", "确定具体目标职业或岗位。", False, ""),
            ("person_job_match", "赛道与匹配", "完成赛道确认并映射职业要求。", True, ""),
            ("gap_analysis", "差距分析", "识别材料与评分维度缺口。", True, ""),
            ("growth_path", "成长路径", "形成阶段成长行动与验证路径。", False, "action_plan"),
            ("resume", "参赛简历", "形成参赛简历并迭代。", True, "resume"),
            ("career_report", "参赛报告", "形成职业发展报告并建立证据链。", True, "career_report"),
            ("ppt", "展示材料", "形成答辩展示材料。", True, "presentation"),
            ("mock_defense", "模拟答辩", "进行答辩问答训练与复盘。", False, "mock_defense"),
        ]),
    ),
    "enterprise_talent": WorkflowTemplate(
        "enterprise_talent_v1", "enterprise_talent", "Enterprise Talent Development",
        _steps([
            ("self_exploration", "能力画像", "建立员工经历、能力与绩效证据基础。", True, ""),
            ("career_positioning", "发展定位", "明确内部发展或流动方向。", True, ""),
            ("target_role", "目标机会", "明确目标岗位、职级或人才通道。", False, ""),
            ("person_job_match", "能力映射", "映射当前证据与岗位/职级能力要求。", True, ""),
            ("gap_analysis", "能力差距", "识别关键能力、经验与认证缺口。", True, ""),
            ("growth_path", "发展计划", "形成可执行的发展行动计划。", False, "action_plan"),
            ("career_report", "发展成果", "形成阶段评估与发展成果记录。", True, "development_report"),
        ]),
    ),
}


def get_workflow_template(preset_id: str | None) -> WorkflowTemplate:
    key = (preset_id or "career_development").strip()
    return TEMPLATES.get(key, TEMPLATES["career_development"])


def list_workflow_templates() -> list[dict]:
    return [
        {
            "template_id": t.template_id,
            "preset_id": t.preset_id,
            "name": t.name,
            "steps": [s.__dict__ for s in t.steps],
        }
        for t in TEMPLATES.values()
    ]


def workflow_template_from_record(record: dict) -> WorkflowTemplate:
    steps = tuple(
        WorkflowStepDefinition(
            step_id=str(item.get("step_id") or item.get("id") or ""),
            index=int(item.get("index") or idx + 1),
            label=str(item.get("label") or ""),
            description=str(item.get("description") or ""),
            required_evidence=bool(item.get("required_evidence", False)),
            required_artifact=str(item.get("required_artifact") or ""),
        )
        for idx, item in enumerate(record.get("steps") or record.get("definition", {}).get("steps") or [])
    )
    return WorkflowTemplate(
        template_id=str(record.get("template_id") or "custom_workflow"),
        preset_id=str(record.get("preset_id") or "career_development"),
        name=str(record.get("name") or "Custom Workflow"),
        steps=steps,
    )
