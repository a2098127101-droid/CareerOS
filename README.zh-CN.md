# StepIn 2.2 Beta

**从一件简单真实的工作开始，让每次尝试、失败、修改、反馈和迁移都成为下一步教学决策的依据。**

[返回首页](README.md) · [架构](ARCHITECTURE.md) · [开发路线图](ROADMAP.md) · [测试状态](TEST_REPORT.md) · [Learner Agent Runtime](docs/LEARNER_AGENT_RUNTIME_v2.1.md) · [真实轨迹与校准](docs/LEARNER_TRAJECTORY_AND_CALIBRATION_v2.2.md)

## 当前产品定义

StepIn 面向零基础、零实习经验，甚至还不知道真实工作每天具体在做什么的学生。产品不从职业测评、课程目录或泛化聊天开始，而是先给学生一件足够简单、可以马上动手的真实任务。

**开始做 → 跟着做 → 自己做 → 失败时被诊断 → 根据反馈修改 → 换场景再做 → 小任务组成项目 → 多任务叠加能力 → 把做过的事情讲出来。**

## 当前生产核心

StepIn 2.2 以 **Learner Agent + Practice Runtime + Evidence/Artifact + Human Review** 为核心。Learner Agent 已拥有独立 State、Policy、Tools、Memory、Trajectory、Execution Loop、Evaluation 与有边界的 Calibration，并通过 `/api/learner-agent/v1` 向 Web、Desktop、LMS 或其他客户端提供稳定接口。

LLM 只负责语言表达与脚手架措辞，不能自行选择高权限工具，不能绕过服务器 Gate，不能替学生生成最终交付物，不能直接宣布能力已经掌握，也不能自动激活候选 Policy。

## 真实学习轨迹

学生在真实任务中的保存、求助、失败、完成、修订、迁移、教师反馈、Evidence 验证、项目里程碑、人工复核和 Agent 干预都会进入服务器侧 Learner Trajectory。短期会话 Memory 与长期 Trajectory 分离，因此 Agent 不依赖聊天窗口才能知道学生实际发生了什么。

## Policy Calibration

系统可以根据真实轨迹形成 ASK、HINT、EXPLAIN、REQUEST_EVIDENCE、ESCALATE 等介入时机的候选策略，但必须达到最小样本要求并由管理员显式激活。权限、安全边界、答案泄露防护、Foundation/Project Gate 和 Evidence 验证不参与自动学习。

## 实践项目库 v2.2

新项目使用当前不可变的 Project Library v2.2。项目从任务要求和原始材料开始，依次保留信息处理、判断、第一版交付、反馈、第二版修订、换场景验证、过程 Evidence 与实践复盘。历史项目继续绑定创建时的模板版本，避免项目库升级改写既有过程证据。

## 当前生产验证

当前版本为 `2.2.0-beta-agent-trajectory`。StepIn 2.2 已进入 production `main`，CI 合同固定为 **204 / 204** 自动化测试，并保留 Learner Agent 13-route contract、Foundation 10-route contract、Project Library v2.2 audit、数据库访问审计、Repository contract、供应链安全扫描和 production release package 等工程 Gate。

这些工程结果不等于教育效果已经验证。真实学生轨迹与人工标签仍是后续校准依据；Windows x64 真机安装、完全断网、升级、备份恢复以及目标生产环境认证仍属于独立发布 Gate。

## 快速启动

Windows：

```text
OPEN_StepIn.cmd
```

Python：

```bash
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload
```

本地演示账号配置见 `.env.example`。生产环境不要启用 Demo 用户自动生成。
