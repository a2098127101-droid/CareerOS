# StepIn Development Roadmap

## 当前主线

StepIn 当前不是课程平台或普通 Career Coach，而是以 **Learner Agent + Practice Runtime + Evidence/Artifact + Human Review** 为核心的实践能力系统。产品从简单真实任务开始，通过失败、修改、反馈、迁移和项目积累形成可验证能力证据。

主链：

**开始做 → 跟着做 → 自己做 → 失败时诊断 → 根据反馈改 → 换场景再做 → 小任务组成项目 → 多任务叠加能力 → 用证据说明自己真正做过什么。**

当前 production 基线继续以 **StepIn 2.2 + Spatial Practice Alpha 7 · Adaptive Showcase** 为视觉运行时，外层已经加入 Alpha 8 Runtime Telemetry 认证基础设施。自动回归合同锁定为 **208 / 208**，前端 dependency lock、`npm ci`、TypeScript/Vite build、后端审计、供应链安全和 production release package 均已进入正式 Gate。

---

## 已完成 P0：Production Foundation

- Foundation 已进入 production `main`；
- 公共实践能力与基础任务已建立；
- Beginner Gate；
- 信息 / 判断 / 表达三类跨材料探索；
- Teacher Growth 基础能力；
- SQLite / PostgreSQL Repository Container 兼容；
- Evidence / Artifact 继续作为 canonical business objects。

## 已完成 P0：Standalone Learner Agent Runtime

Learner Agent 已拥有独立 State、Policy、Tools、Memory、Trajectory、Execution Loop、Evaluation 与 Calibration。LLM 只作为语言与脚手架层，不能选择高权限 Tool、生成学生最终交付物、绕过服务器 Gate、验证 Evidence 或直接提升 Capability。

## 已完成 P0：Real Trajectory + Bounded Calibration

真实业务事件进入长期 Learner Trajectory，包括保存、求助、失败、完成、修订、迁移、教师反馈、Evidence 决策、项目里程碑、人工复核和 Agent 干预。Trajectory 与短期 Memory 分离；Calibration 只允许调整介入时机和脚手架强度，权限、安全边界、答案泄露防护、Foundation/Project Gate 与 Evidence verification 不参与自动学习。

## 已完成 P0：Project Library v2.2

默认项目已经从“职业规划填写”转为真实任务综合实践：任务与限制、原始材料、信息整理、问题发现、判断与理由、V1、反馈、V2、换场景迁移、过程证据和复盘。项目模板使用 immutable version，历史项目保持原模板绑定。

## 已完成 P0：Capability Verification 2.0

能力验证已经完成服务器侧保守分级：`unobserved → signal → evidence → verified_evidence`。Evidence 至少需要两个不同成功任务情境并出现独立完成、修订、迁移或组合实践信号；Verified Evidence 进一步要求 transfer success 与 canonical `VERIFIED` Evidence。同一任务多个 Artifact/Evidence 版本不能伪装成多个任务情境，前端交互不能提升 Capability。

## 已完成 P0：Real Work Sample Runtime

Real Work Sample 已形成 `ready → working_v1 → revision_required → transfer_ready → completed` 服务器流程，包含 V1、supervisor feedback、V2、transfer、Artifact version、Evidence 与 phase guard。Work Sample 完成与 Verified Evidence 明确分离。

## 已完成 P0：Server-authoritative Spatial Practice

空间系统已经发展为 Alpha 7 Adaptive Showcase，但仍保持严格服务器权威边界：

```text
source = server
readOnly = true
clientMayPromoteCapability = false
clientMayVerifyEvidence = false
clientMayRewriteTrajectory = false
```

当前包括 Shader workstation/screen、transmission glass、SSR、depth-aware volumetric、Bloom、GPU-instanced data field、GPGPU topology、Evidence → Capability flow、Capability awakening、Artifact destruction/assembly、Cinematic Sequencer、Lighting Timeline、Control Room transformation、Showcase Auto Demo 与 Adaptive render budget。

## 已完成 P0：Adaptive Showcase Production Hardening

Alpha 7 已具备 `auto / ultra / high / balanced / safe` 质量预算。Auto 根据设备信息、WebGL capability 与实时 FPS 逐级向下降档，并在 WebGL context loss 后保持 Safe。`frontend/package-lock.json` 已进入仓库，Spatial CI、Production Release 和 source multi-stage Docker build 均使用 deterministic `npm ci`。

## 已完成 P0：Alpha 8 Runtime Telemetry Foundation

认证所需的可观测基础设施已经完成：

- `boot / frame_sample / quality_change / context_lost / context_restored` 五类运行事件；
- FPS 与 P50/P95/P99 frametime；
- quality request/tier 与降档原因；
- 分桶 viewport、CPU/memory class、WebView flag；
- coarse Intel/AMD/NVIDIA/Apple/Qualcomm/ARM/software renderer class；
- WebGL version、texture/sample limits 与 shader precision；
- participant 提交、advisor/org-admin tenant summary；
- telemetry allow-list，拒绝自由文本和未知字段；
- 持久 analytics 使用空 user/session ID；
- telemetry 不进入 SceneState、Evidence、Artifact、Capability 或 Trajectory；
- CI 与 Production Release 均执行 telemetry/privacy contract audit。

同时完成真正独立的 motion policy：`?motion=full|reduced|off`。`prefers-reduced-motion` 不再通过强制 Safe 降画质实现；Reduced/Off 改为 demand rendering，画质和持续动态可以分别控制。

---

# 下一 P0：Target Runtime Certification

现在缺少的已经不是“系统不会测”，而是把最终 Release 放到真实目标设备和环境中运行并留下证据。Issue #20 是唯一认证清单。

重点证据：

- 首屏启动时间与首次可交互时间；
- FPS、1% low FPS 与 frametime 分布；
- 自动 quality 选择结果与降档原因；
- WebGL context-loss / restore；
- Showcase Auto Demo 固定镜头性能；
- 长时间运行稳定性；
- Intel 核显、AMD APU、NVIDIA 独显代表机型；
- Windows WebView2；
- PostgreSQL/pgvector RLS、Redis worker、MinIO/S3、真实模型 fallback、真实 retrieval；
- backup/restore、rollback、monitoring/alert、pilot load smoke。

Runtime Telemetry 只能记录性能和渲染执行信息，不得把学生学习内容、Evidence 原文或私密实践数据混入性能遥测。

# 下一 P0：Capability Verification Pilot Calibration

Capability Verification `2.0-min` 仍是规则系统。真实 pilot 需要形成系统判断、教师独立标签与陌生 transfer task 表现的三方对照，重点评估 false promotion、false negative、teacher-agent agreement、transfer predictive validity 与不同提示强度下的稳定性。完成这一步之前，不把当前 `confidence` 解释成统计概率意义上的能力掌握概率。

# P1：Practice Studio 2.0

内容人员无需修改 Python 即可配置 Foundation Ability、Work Sample、Scaffold Level、Done-when、Hint Budget、Revision、Transfer Variant、Task Chain、Mini Project 与 Agent-observable event mapping。配置系统继续服从服务器 Capability Verification 与 Evidence 权威规则，不能让模板自行宣布掌握。

# P1：Trajectory Analytics / Experimentation

增加 tenant 内可审计实验能力，包括 Policy profile 版本比较、intervention recovery A/B、diagnosis agreement、hint dependency decline、transfer success、revision quality、human escalation precision 与 capability verification calibration。默认不跨租户汇总原始学生轨迹；研究或模型训练必须另行处理授权、去标识和数据治理。

# P1：Teacher Growth 3.0

教师端继续从“批改”转向成长观察：连续失败在哪里、哪种提示有效、反馈后是否实质修改、换材料后是否仍能完成、哪些 Evidence 已核验、Agent 哪些诊断被老师否定、何时需要人工介入。

# P1：Independent Agent Deployment

当前 Learner Agent 已经做到行为独立、API 独立和依赖注入。只有当 LMS、第三方产品或多客户端跨系统调用规模明显增大后，再物理拆成独立服务，并保持 `/api/learner-agent/v1` 协议稳定。

---

## 当前发布原则

StepIn 的下一阶段判断标准不再是“又增加了多少页面或视觉特效”，而是：实践过程是否留下可追溯 Evidence；Capability 是否由多个真实任务情境支撑；Agent 是否能基于真实 Trajectory 做受边界约束的下一步判断；高保真空间表现是否在不同硬件上稳定运行；构建、依赖、发布包、遥测隐私和服务器权威边界是否保持可复现、可审计。
