# StepIn 2.2 Beta

**从一件简单真实的工作开始，让每次尝试、失败、修改、反馈和迁移都成为下一步教学决策的依据。**

**Start with real work. Turn every attempt, failure, revision, feedback event, and transfer into evidence for the next learning decision.**

[中文说明](README.zh-CN.md) · [开发路线图](ROADMAP.md) · [Learner Agent Runtime](docs/LEARNER_AGENT_RUNTIME_v2.1.md) · [Trajectory & Calibration](docs/LEARNER_TRAJECTORY_AND_CALIBRATION_v2.2.md)

## StepIn 是什么

StepIn 面向零基础、零实习经验，甚至不知道真实工作每天具体在做什么的学生。产品不从岗位测评或课程目录开始，而是先给一件真实、简单、马上能动手的工作任务。

**开始做 → 跟着做 → 自己做 → 失败时被诊断 → 根据反馈修改 → 换场景再做 → 小任务组成项目 → 多任务叠加能力 → 把做过的事情讲出来。**

## Learner Agent 已经成为核心 Runtime

StepIn Learner Agent 不是聊天窗口，而是独立、状态化、受 Policy 约束的实践监督 Agent。它拥有自己的 State、Policy、Tools、Memory、Trajectory、Execution Loop、Evaluation 与 Calibration，并通过 `/api/learner-agent/v1` 被 Web、Desktop、LMS 或其他客户端调用。

模型只负责开放式语言表达和脚手架措辞，不能自己选择工具、不能绕过服务器 Gate、不能生成学生最终交付物，也不能直接宣布能力已经掌握。

## 真实任务轨迹 / Real task trajectory

本版本把 Agent 从“用户主动和它说话时才知道发生了什么”升级为服务器事件驱动。以下事件会直接进入 tenant + learner + session 隔离的 Learner Trajectory，并同步成为 Agent Observation：

- 保存答案、任务失败、任务完成、请求帮助；
- 第一版后的实质修改与 revision submission；
- Foundation transfer 与三类跨材料探索；
- 教师反馈、反馈解决和人工轨迹标注；
- Evidence 自动验证、人工验证、部分支持或拒绝；
- 实践项目创建、材料更新、评审/修改里程碑和项目完成；
- Agent 自己采取的 ASK / HINT / EXPLAIN / REQUEST_EVIDENCE / ESCALATE 等干预。

Foundation 页面中的“给一点提示”和失败后的支持也已经改为调用 Learner Agent API，而不是在前端复制一套提示策略。

## Policy Calibration

Trajectory 不会直接让系统自我修改生产策略。StepIn 先根据真实轨迹计算 challenge distribution、提示依赖、短期干预恢复、迁移成功、Evidence 验证、反馈解决和人工诊断标签等指标；达到最小样本量后只能生成 **candidate policy profile**，仍需组织管理员显式激活。

可校准的只是 ASK / HINT / EXPLAIN / REQUEST_EVIDENCE / ESCALATE 的介入时机。以下边界始终由代码固定：不代做最终答案、不直接标记掌握、不绕过 Gate、不绕过 Evidence/Verifier。

## 最新实践项目库

默认项目库已经从旧的“先填写职业方向、目标岗位和经历”升级为 **真实任务综合实践 v2.2**。当前模板从任务要求和原始材料开始，依次记录信息处理、判断、第一版交付、反馈修改、换场景验证、过程证据和实践复盘。

项目模板使用 immutable version：新项目只能使用当前最新版本；历史项目继续绑定创建时的旧版本，因此项目库可以升级而不会改写既有学生记录。API 还会返回 `library_version` 与 `agent_observable`，用于确认当前项目库版本。

## Production validation

**StepIn 2.2 已通过 PR #19 合并进入 production `main`。** 合并前的最终 PR head 通过 **204 / 204** 锁定回归，同时通过 Learner Agent 13-route contract、Foundation 10-route contract、Project Library v2.2 audit、database access audit、repository contract、供应链安全扫描和 production release package。当前 `VERSION.txt` 为 `2.2.0-beta-agent-trajectory`。

这些工程 Gate 证明当前代码和发布边界一致，但不等同于教育效果已经被真实用户研究验证。Policy Calibration 仍需要真实学生轨迹与人工标签持续校准。

## 当前边界

Trajectory/Calibration 现在已经是生产工程能力，但“某种诊断在真实学生中是否教育学上最优”仍需要真实用户标注和持续校准。系统当前不会自动拿跨租户原始轨迹训练模型，也不会自动激活新 Policy。Windows x64 安装、完全断网、升级与备份恢复仍是独立发行 Gate。

## Quick start

### Windows

```text
OPEN_CareerOS.cmd
```

### Python

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Local demo account settings are documented in `.env.example`. Do not enable demo seeding in production.
