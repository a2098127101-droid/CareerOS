# StepIn 2.2 Development Roadmap

## 当前主线

StepIn 当前不是课程平台或普通 Career Coach，而是以 **Learner Agent + Practice Runtime + Evidence/Artifact + Human Review** 为核心的实践能力系统。产品从简单真实任务开始，通过失败、修改、反馈、迁移和项目积累判断学生下一步需要什么支持。

主链：

**开始做 → 跟着做 → 自己做 → 失败时诊断 → 根据反馈改 → 换场景再做 → 小任务组成项目 → 多任务叠加能力 → 把做过的事情讲出来。**

当前 production `main` 已完成 StepIn 2.2 合并（PR #19）。最终 PR head 通过 **204 / 204** 锁定回归、Learner Agent 13-route contract、Foundation 10-route contract、Project Library v2.2 audit、供应链安全扫描和 production release package。当前版本为 `2.2.0-beta-agent-trajectory`。

---

## 已完成 P0：Production Foundation

- Foundation 已进入 production `main`；
- 10 项公共实践能力和 8 个基础任务；
- Beginner Gate；
- 信息 / 判断 / 表达三类跨材料探索；
- Teacher Growth；
- SQLite / PostgreSQL Repository Container 兼容；
- Evidence / Artifact 继续作为 canonical business objects。

## 已完成 P0：Standalone Learner Agent Runtime

Learner Agent 已拥有独立：

```text
State
Policy
Tools
Memory
Execution Loop
Evaluation
```

固定 Action Space：

```text
ASK
HINT
EXPLAIN
SHOW_RESOURCE
REQUEST_EVIDENCE
CREATE_REVISION_TASK
VERIFY
ASSIGN_TRANSFER
ADVANCE
ESCALATE
WAIT
```

LLM 只作为语言层，不能选择 Tool、生成最终交付物、直接标记掌握或绕过 Gate。

## 已完成 P0：Real Trajectory + Calibration

真实业务事件现在直接进入 Learner Trajectory：

```text
answer_saved
hint_requested
task_failed
task_completed
revision_requested
revision_submitted
transfer_failed
transfer_completed
teacher_feedback
teacher_feedback_resolved
evidence_verified
evidence_partial
evidence_rejected
project_started
project_updated
project_milestone
project_completed
agent_intervention
human_review_resolved
```

Trajectory 与短期 Memory 分离，并成为 Evaluation 和 Policy Calibration 的长期数据面。

Policy Calibration 当前只允许调整：

```text
第几次失败继续 ASK
第几次失败出现 HINT
什么时候切换 EXPLAIN
什么时候请求过程 Evidence
什么时候升级 Human Review
```

候选 Policy 需要最小真实样本量，并且必须由组织管理员显式激活。安全边界不参与学习。

## 已完成 P0：Project Library v2.2

旧默认“个人职业发展规划”升级为 **真实任务综合实践**。默认项目不再先问目标岗位，而是围绕：

```text
任务与限制
→ 原始材料
→ 信息整理
→ 问题发现
→ 判断与理由
→ 第一版交付
→ 反馈
→ 第二版
→ 换场景再做
→ 过程证据
→ 实践复盘
```

项目模板使用 immutable version。系统通过 `library_version` + content hash 自动识别旧默认模板并创建最新版本；所有新项目使用当前最新 v2.2 模板，旧项目继续绑定历史版本，避免改写既有学生过程证据。

---

# 下一 P0：Capability Verification 2.0

当前轨迹已经能说明“学生发生了什么”，下一步要进一步提高“已经会做什么”的可信度。

重点：

- Signal / Evidence / Verified Evidence 分级；
- 同一能力至少来自多个不同任务与材料；
- 独立完成比例；
- 提示依赖变化；
- revision quality；
- transfer success；
- teacher verification；
- 时间跨度；
- capability confidence calibration。

最终学生只看到普通语言：

```text
刚开始
能跟着做
能自己做
换一种情况也能做
已经比较稳定
```

# 下一 P0：Real Work Sample Runtime

减少“答题感”，让项目材料更像真实工作输入：表格、聊天记录、访谈材料、需求、工单、候选人材料、Issue、反馈等。

Agent 观察重点从“最终答案对不对”转为：

- 是否看懂任务；
- 是否找到关键限制；
- 如何整理材料；
- 如何形成判断；
- 是否留下中间过程；
- 收到反馈后到底改了什么；
- 换材料后是否还能做。

# P1：Practice Studio 2.0

内容人员无需修改 Python 即可配置：

- Foundation Ability；
- Work Sample；
- Scaffold Level；
- Done-when；
- Hint Budget；
- Revision；
- Transfer Variant；
- Task Chain；
- Mini Project；
- Agent-observable event mapping。

# P1：Trajectory Analytics / Experimentation

增加 tenant 内的可审计实验能力：

- Policy profile 版本比较；
- intervention recovery A/B；
- optimal challenge distribution；
- diagnosis agreement；
- hint dependency decline；
- transfer success；
- human escalation precision。

默认不跨租户汇总原始学生轨迹；研究或模型训练必须另行处理授权、去标识与数据治理。

# P1：Teacher Growth 3.0

教师端从“批改”继续转向成长观察：

```text
这个学生在哪里连续失败
哪种提示有效
反馈后有没有真实修改
换材料后是否仍然会做
Agent 哪些诊断被老师否定
什么时候应该人工介入
```

# P1：Independent Agent Deployment

当前 Learner Agent 已经做到行为独立、API 独立和依赖注入。只有在 LMS / 第三方产品 / 多客户端跨系统调用规模明显增大后，再物理拆成独立服务。拆分时保持 `/api/learner-agent/v1` 客户端协议稳定。

# P1：Windows x64 Release Gate

仍需真实 Windows 机器完成：

```text
安装
→ 首次启动
→ Foundation / Agent 实践
→ 完全断网
→ 保存与重启
→ 导出
→ 备份
→ 升级
→ 数据迁移
→ 恢复
→ 卸载 / 重装
```

Linux GitHub Actions 通过不能替代 Windows 真机认证。
