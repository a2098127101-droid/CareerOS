# StepIn 2.2 Beta

**从一件简单真实的工作开始，让每次尝试、失败、修改、反馈和迁移都成为下一步教学决策的依据。**

[返回首页](README.md) · [开发路线图](ROADMAP.md) · [Learner Agent Runtime](docs/LEARNER_AGENT_RUNTIME_v2.1.md) · [真实轨迹与校准](docs/LEARNER_TRAJECTORY_AND_CALIBRATION_v2.2.md)

## 当前产品定义

StepIn 面向零基础、零实习经验，甚至不知道真实工作每天具体在做什么的学生。学生不先做职业测评，也不先堆课程，而是直接从一件足够简单的真实任务开始。

**开始做 → 跟着做 → 自己做 → 失败时被诊断 → 根据反馈修改 → 换场景再做 → 小任务组成项目 → 多任务叠加能力 → 把做过的事情讲出来。**

## Learner Agent 不再只是聊天功能

Learner Agent 已经拥有独立 State、Policy、Tools、Memory、Trajectory、Execution Loop、Evaluation 和 Calibration。Web、桌面端、LMS 或第三方界面只调用 `/api/learner-agent/v1`，不需要复制 Agent Policy。

LLM 只是语言层。它可以把已经选定的 ASK、EXPLAIN 等动作说得更自然，但不能自己决定工具，不能生成最终交付物，不能直接把学生标记为“已经掌握”，也不能绕过 Foundation / Project Gate。

## 真实任务过程已经进入 Agent

过去 Agent 主要依靠显式 `/step` 请求知道学生发生了什么。现在服务器会把真实业务事件直接写入 Learner Trajectory：

- 保存答案、失败、完成、请求帮助；
- 修订提交；
- Foundation transfer 和三类跨材料探索；
- 教师反馈、反馈解决、人工诊断标注；
- Evidence 自动验证和人工验证；
- 实践项目创建、更新、评审、要求修改、再次提交和完成；
- Agent 每次实际干预。

因此学生换页面、换客户端甚至不打开聊天窗口，Agent 仍然知道真正发生过什么。Foundation 页的“给一点提示”以及失败后的下一步支持也已经直接调用 Learner Agent，而不是继续在前端写死另一套教练逻辑。

## 用轨迹校准 Policy 与 Evaluation

系统会从真实轨迹计算：任务是否过易/适中/过难、提示依赖、不同 Agent 动作后的短期恢复、迁移成功率、Evidence 验证率、教师反馈是否得到处理，以及人工对 Agent 诊断的确认率。

达到最小样本量后，系统可以生成新的 candidate policy profile，但不会自动上线。只有组织管理员显式激活以后，ASK / HINT / EXPLAIN / REQUEST_EVIDENCE / ESCALATE 的介入时机才会改变。安全边界不参与学习。

这使“训练/校准”从修改 Prompt 变成了：**真实行为轨迹 → 可量化结果 → 候选策略 → 人工审核 → 版本化激活 → 再评价。**

## 项目库已改成最新实践逻辑

旧默认模板“个人职业发展规划”已经升级为 **真实任务综合实践 v2.2**。新模板不再先问目标岗位，而是从任务、材料、判断和交付开始，随后要求学生保留第一版、反馈、第二版、换场景结果、过程证据和自己的复盘。

项目模板继续采用不可变版本。新项目只能绑定当前最新版本；已有历史项目仍读取创建时的旧模板快照，不会因为项目库升级而被改写。

## 当前生产状态

**StepIn 2.2 已通过 PR #19 合并进入 production `main`。** 最终 PR head 通过 **204 / 204** 锁定回归，并通过 Learner Agent 13-route contract、Foundation 10-route contract、Project Library v2.2 audit、数据库访问审计、Repository contract、供应链安全扫描与 production release package。当前 `VERSION.txt` 为 `2.2.0-beta-agent-trajectory`。

这表示当前工程闭环、接口契约与发布边界已经对齐，但不代表教育效果已经完成真实用户验证。Policy Calibration 仍需真实学生会话与人工标注持续校准。

## 当前工程边界

Learner Trajectory 与 Policy Calibration 已经进入生产代码，但教育学阈值仍需要真实用户会话和人工标注继续验证。当前不自动跨租户汇总原始轨迹训练模型，也不允许候选 Policy 自动激活。Windows x64 真机安装、完全断网、升级与备份恢复仍然是独立发行 Gate。

## 快速启动

Windows：

```text
OPEN_CareerOS.cmd
```

Python：

```bash
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload
```

本地演示账号配置见 `.env.example`。生产环境不要启用 Demo 用户自动生成。
