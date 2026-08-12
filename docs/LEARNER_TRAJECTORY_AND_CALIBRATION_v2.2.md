# StepIn Learner Trajectory & Calibration v2.2

## 1. 目标

Learner Agent 不能只看到聊天内容，也不能只根据一次最终答案判断学生能力。本版本把真实工作过程统一成服务器事件轨迹，让任务失败、修改、迁移、教师反馈、Evidence 验证和项目里程碑都成为 Agent Observation。

## 2. Trajectory

`LearnerTrajectoryStore` 采用 tenant + owner + session 隔离的 append-oriented event model。核心事件包括 `task_failed`、`task_completed`、`revision_submitted`、`transfer_completed`、`teacher_feedback`、`evidence_verified`、`project_milestone` 和 `agent_intervention`。

Trajectory 与短期 Memory 分工不同：Memory 保留最近会话所需的有界上下文；Trajectory 用于长期评价、人工标注和 Policy Calibration。

## 3. Server Event Bridge

Foundation、跨材料探索、项目 Runtime、教师反馈和 Evidence Verifier 都可以通过 best-effort event bridge 写入 Agent。Observation 失败不会回滚已经完成的业务事务；业务事实仍以原 Domain Repository 为准。

## 4. Calibration

`LearnerAgentCalibrationService` 从真实轨迹计算：

- under / optimal / over challenge；
- hint dependency；
- ASK / HINT / EXPLAIN / REQUEST_EVIDENCE 等动作后的短期恢复；
- transfer success；
- Evidence verified rate；
- teacher feedback resolution；
- revision after feedback；
- human diagnosis agreement。

不足最小样本量时只返回指标，不生成策略候选。达到阈值后可生成 candidate policy profile；candidate 必须由组织管理员人工激活。

## 5. 不可学习的安全边界

Calibration 只能调整帮助介入时机，不能修改以下规则：

- 不能生成学生最终交付物；
- 不能直接标记 capability mastered；
- 不能绕过 Foundation / Professional Gate；
- 不能跳过 Evidence / Verifier；
- 不能让 LLM 自由选择 Tool。

## 6. Human Labels

Advisor / Admin 可以对具体 trajectory event 提交人工标签，包括 diagnosis 是否正确、人工观察到的 diagnosis、outcome 和 notes。这些标签进入新的 `human_review_resolved` 事件，并进入 calibration evaluation，而不是覆盖原事件。

## 7. Independent HTTP Contract

在原有 Agent API 基础上新增：

- `GET /api/learner-agent/v1/trajectory`
- `POST /api/learner-agent/v1/trajectory/{event_id}/label`
- `GET /api/learner-agent/v1/calibration`
- `POST /api/learner-agent/v1/calibration/refresh`
- `POST /api/learner-agent/v1/calibration/activate`

客户端不需要知道 Repository、SQLite/PostgreSQL 或 Foundation 实现。

## 8. Project Library v2.2

默认项目模板升级为“真实任务综合实践”。新项目从任务与材料开始，经信息处理、判断、第一版、反馈修改、迁移、Evidence 与实践复盘形成完整工作样本。模板通过 `library_version=2.2.0` 与 content hash 检测是否过期；旧项目继续绑定原 immutable template version。

## 9. 当前限制

本版本完成的是可验证、可版本化的 trajectory-driven calibration infrastructure，不等于已经完成教育学效果验证，也不自动对跨租户原始数据做模型微调。真实用户实验、人工标签质量和阈值稳健性仍需要后续验证。
