from __future__ import annotations

from copy import deepcopy
from typing import Any

FOUNDATION_ABILITIES: list[dict[str, Any]] = [
    {"id": "understand_task", "name": "看懂要做什么", "plain": "能先弄清楚任务要什么，不急着动手。"},
    {"id": "extract_info", "name": "找出关键信息", "plain": "能从一堆材料里找到真正有用的几条。"},
    {"id": "organize_info", "name": "把信息理清楚", "plain": "能分类、排序，把杂乱内容整理成可继续处理的样子。"},
    {"id": "judge", "name": "比较后作判断", "plain": "能用同一把尺子比较几个选项，再做取舍。"},
    {"id": "spot_problem", "name": "发现明显问题", "plain": "能看出缺失、重复、冲突或不合理的地方。"},
    {"id": "explain_reason", "name": "把理由说清楚", "plain": "能指出自己为什么这样判断，而不是只给结论。"},
    {"id": "deliver_clear", "name": "把结果交代清楚", "plain": "能让下一位接手的人知道发生了什么、做了什么、接下来做什么。"},
    {"id": "revise_feedback", "name": "根据意见再改一次", "plain": "听懂反馈后能真正改出一个更好的版本。"},
    {"id": "transfer", "name": "换个场景还能做", "plain": "材料变了以后，仍然能用同一个方法完成。"},
    {"id": "articulate", "name": "把自己做过的讲出来", "plain": "能用普通话说明自己做了什么、为什么这样做、最后怎样。"},
]

ABILITY_BY_ID = {x["id"]: x for x in FOUNDATION_ABILITIES}

FOUNDATION_TASKS: list[dict[str, Any]] = [
    {
        "id": "FND-01-order",
        "order": 1,
        "title": "4 件事，先做哪一件",
        "intro": "先别想岗位。假设这是你今天刚接到的 4 件事，只需要排个顺序。",
        "why": "很多工作第一步都不是马上做，而是先判断哪件更急、更重要。",
        "type": "order",
        "scaffold": "guided",
        "hintBudget": 2,
        "abilities": ["understand_task", "judge", "explain_reason"],
        "data": {
            "items": [
                {"id": "refund", "title": "处理一笔退款", "detail": "客户今天上午已经追问两次，承诺今天回复。"},
                {"id": "report", "title": "整理本周数据", "detail": "周五下班前要交，现在是周二。"},
                {"id": "meeting", "title": "准备明天下午的会议", "detail": "需要一页材料，明天中午前准备好。"},
                {"id": "folder", "title": "整理共享文件夹", "detail": "文件比较乱，但暂时没人等着用。"},
            ],
            "expectedTop": ["refund", "meeting"],
        },
        "hints": ["先找‘有人正在等’和‘什么时候必须完成’。", "如果两件事都重要，先比较哪一件不及时处理的后果更直接。"],
    },
    {
        "id": "FND-02-key-info",
        "order": 2,
        "title": "6 条话里，只留下最重要的 3 条",
        "intro": "你不需要记住所有信息。先找出完成任务真正离不开的 3 条。",
        "why": "工作材料常常很多，先抓关键信息，后面才不会越做越乱。",
        "type": "select",
        "scaffold": "guided",
        "hintBudget": 2,
        "abilities": ["understand_task", "extract_info"],
        "data": {
            "question": "要在周四前交一份活动报名汇总，下面哪 3 条最影响你能不能按时完成？",
            "items": [
                {"id": "deadline", "text": "最终汇总必须在周四 16:00 前交。"},
                {"id": "people", "text": "还有 12 个人没有确认是否参加。"},
                {"id": "format", "text": "交付格式是一张包含姓名、电话、是否参加的表格。"},
                {"id": "color", "text": "上次活动海报使用的是蓝色。"},
                {"id": "room", "text": "活动地点在 3 楼会议室。"},
                {"id": "snack", "text": "有人建议现场准备瓶装水。"},
            ],
            "expected": ["deadline", "people", "format"],
            "pick": 3,
        },
        "hints": ["想一想：缺了哪条信息，你就没法按要求把东西交出去？", "先看时间、还差什么人/数据、最后要交成什么样。"],
    },
    {
        "id": "FND-03-group",
        "order": 3,
        "title": "把 6 条消息分清楚",
        "intro": "先别分析得太复杂，只把相似的内容放到一起。",
        "why": "整理信息的本质，经常就是先把不同类型的问题分开。",
        "type": "categorize",
        "scaffold": "assisted",
        "hintBudget": 1,
        "abilities": ["organize_info", "spot_problem"],
        "data": {
            "categories": ["要马上处理", "需要确认", "只是记录"],
            "items": [
                {"id": "m1", "text": "客户说付款成功但订单仍显示未支付。", "expected": "要马上处理"},
                {"id": "m2", "text": "同事问下周会议是不是改到周三。", "expected": "需要确认"},
                {"id": "m3", "text": "今天新增了 18 个报名。", "expected": "只是记录"},
                {"id": "m4", "text": "系统导出的文件打不开，下午要交。", "expected": "要马上处理"},
                {"id": "m5", "text": "合作方发来一版新名单，不确定是不是最终版。", "expected": "需要确认"},
                {"id": "m6", "text": "昨天一共处理了 24 条咨询。", "expected": "只是记录"},
            ],
        },
        "hints": ["先问：这条消息是在报告已经发生的事，还是要求你继续采取动作？"],
    },
    {
        "id": "FND-04-find-problem",
        "order": 4,
        "title": "找出这张小表里最明显的问题",
        "intro": "不用学数据分析。只像检查名单一样，看看哪里会让后面的人没法继续做。",
        "why": "很多工作不是从‘做更多’开始，而是先把明显错误找出来。",
        "type": "spot_issues",
        "scaffold": "assisted",
        "hintBudget": 1,
        "abilities": ["extract_info", "spot_problem", "explain_reason"],
        "data": {
            "rows": [
                {"id": "r1", "name": "王晴", "phone": "13800138001", "date": "8月14日"},
                {"id": "r2", "name": "李然", "phone": "", "date": "8月14日"},
                {"id": "r3", "name": "周思", "phone": "13900139002", "date": "8月15日"},
                {"id": "r4", "name": "周思", "phone": "13900139002", "date": "8月15日"},
            ],
            "issues": [
                {"id": "missing_phone", "text": "李然缺少电话"},
                {"id": "duplicate", "text": "周思出现两次"},
                {"id": "date_mix", "text": "日期不是同一天"},
                {"id": "name_short", "text": "姓名都是两个字"},
            ],
            "expected": ["missing_phone", "duplicate"],
        },
        "hints": ["先找‘缺了一项’或‘完全一样地出现两次’这种最直接的问题。"],
    },
    {
        "id": "FND-05-handoff",
        "order": 5,
        "title": "把这件事交代给下一位同学",
        "intro": "你做完了一半，下一位同学要接手。只要让他不用重新猜就可以。",
        "why": "工作里的表达，最基本的标准不是好听，而是下一位能接着做。",
        "type": "handoff",
        "scaffold": "independent",
        "hintBudget": 1,
        "abilities": ["understand_task", "deliver_clear", "articulate"],
        "data": {
            "situation": "你负责收集活动报名。现在 30 人里已经确认 24 人，还有 6 人没回复。名单周四 16:00 前要交。",
            "fields": [
                {"id": "done", "label": "已经做到哪", "placeholder": "例如：已经确认……"},
                {"id": "left", "label": "还剩什么", "placeholder": "例如：还有……"},
                {"id": "next", "label": "下一步先做什么", "placeholder": "例如：先……"},
            ],
        },
        "hints": ["只回答三件事：已经做了什么、还差什么、下一步先做什么。"],
    },
    {
        "id": "FND-06-revise",
        "order": 6,
        "title": "别人说不清楚，再改一版",
        "intro": "第一版不是要一次写对。看一条反馈，把它改到别人能接手。",
        "why": "真正的工作能力，很大一部分来自‘做一版—听意见—再改一版’。",
        "type": "revise",
        "scaffold": "revision",
        "hintBudget": 1,
        "abilities": ["deliver_clear", "revise_feedback", "articulate"],
        "data": {
            "original": "名单差不多了，还有几个人没回，之后再问一下，周四要用。",
            "feedback": "看完还是不知道已经确认多少人、还有几个人、什么时候必须交、下一步具体先联系谁。",
        },
        "hints": ["把反馈里缺的数字、时间和下一步动作一项项补进去，不需要换成漂亮词。"],
    },
    {
        "id": "FND-07-transfer",
        "order": 7,
        "title": "换件事，再自己判断一次",
        "intro": "这次材料换了，也不给提示。看看前面的方法能不能自己用出来。",
        "why": "会做一道题还不够，换个场景仍然能做，才更接近真正会做。",
        "type": "transfer",
        "scaffold": "transfer",
        "hintBudget": 0,
        "abilities": ["understand_task", "extract_info", "judge", "explain_reason", "transfer"],
        "data": {
            "question": "你上午只能先处理一件事，先做哪件？",
            "items": [
                {"id": "broken_link", "title": "报名链接打不开", "detail": "40 名同学今天 12:00 前要完成报名，现在是 9:30。"},
                {"id": "slides", "title": "美化下周汇报 PPT", "detail": "下周一才汇报，内容已经齐了。"},
                {"id": "archive", "title": "整理上个月文件", "detail": "没有明确截止时间。"},
            ],
            "expected": "broken_link",
        },
        "hints": [],
    },
    {
        "id": "FND-08-mini-project",
        "order": 8,
        "title": "把前面几步连起来做一次",
        "intro": "这次不再拆成一小步一小步。你要先找重点、再判断、最后把结果说清楚。",
        "why": "当几个小动作能连起来完成，一件小任务才开始变成一个真正的小项目。",
        "type": "mini_project",
        "scaffold": "combined",
        "hintBudget": 0,
        "abilities": ["extract_info", "organize_info", "judge", "explain_reason", "deliver_clear", "transfer", "articulate"],
        "data": {
            "brief": "社团周五要举办一次分享会。现在有 42 人报名，教室最多 35 人；7 人没有填写手机号；宣传海报上还是旧教室号；老师要求周三 18:00 前给出一页处理说明。",
            "facts": [
                {"id": "capacity", "text": "报名 42 人，但教室最多 35 人。"},
                {"id": "phone", "text": "7 人没有填写手机号。"},
                {"id": "poster", "text": "宣传海报仍然写着旧教室号。"},
                {"id": "deadline", "text": "周三 18:00 前要交一页处理说明。"},
                {"id": "weekday", "text": "活动安排在周五。"},
            ],
            "expectedKey": ["capacity", "poster", "deadline"],
        },
        "hints": [],
    },
]

TASK_BY_ID = {x["id"]: x for x in FOUNDATION_TASKS}


def ability_catalog() -> list[dict[str, Any]]:
    return deepcopy(FOUNDATION_ABILITIES)


def task_catalog() -> list[dict[str, Any]]:
    return deepcopy(FOUNDATION_TASKS)


def public_task(task: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(task)
    data = out.get("data") or {}
    data.pop("expected", None)
    data.pop("expectedTop", None)
    data.pop("expectedKey", None)
    for item in data.get("items") or []:
        if isinstance(item, dict):
            item.pop("expected", None)
    out["data"] = data
    out.pop("hints", None)
    return out
