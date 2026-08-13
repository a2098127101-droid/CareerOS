# StepIn Development Roadmap

## 当前主线

StepIn 当前不是课程平台或普通 Career Coach，而是以 **Learner Agent + Practice Runtime + Evidence/Artifact + Human Review** 为核心的实践能力系统。产品从简单真实任务开始，通过失败、修改、反馈、迁移和项目积累形成可验证能力证据。

主链：

**开始做 → 跟着做 → 自己做 → 失败时诊断 → 根据反馈改 → 换场景再做 → 小任务组成项目 → 多任务叠加能力 → 用证据说明自己真正做过什么。**

当前 production `main` 已进入 **StepIn 2.2 + Spatial Practice Alpha 7 · Adaptive Showcase** 基线。自动回归合同锁定为 **208 / 208**，前端 dependency lock、`npm ci`、TypeScript/Vite build、后端审计、供应链安全和 production release package 均已进入正式 Gate。

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

Learner Agent 已拥有独立：

```text
State
Policy
Tools
Memory
Trajectory
Execution Loop
Evaluation
Calibration
```

LLM 只作为语言与脚手架层，不能选择高权限 Tool、生成学生最终交付物、绕过服务器 Gate、验证 Evidence 或直接提升 Capability。

## 已完成 P0：Real Trajectory + Bounded Calibration

真实业务事件进入长期 Learner Trajectory，包括保存、求助、失败、完成、修订、迁移、教师反馈、Evidence 决策、项目里程碑、人工复核和 Agent 干预。

Trajectory 与短期 Memory 分离，并作为 Evaluation 和 Policy Calibration 的长期数据面。Calibration 只允许调整介入时机和脚手架强度，权限、安全边界、答案泄露防护、Foundation/Project Gate 与 Evidence verification 不参与自动学习。

## 已完成 P0：Project Library v2.2

默认项目已经从“职业规划填写”转为真实任务综合实践：

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

项目模板使用 immutable version，新项目进入当前库版本，历史项目保持原模板绑定，避免升级改写既有过程证据。

## 已完成 P0：Capability Verification 2.0

能力验证已经完成服务器侧保守分级：

```text
unobserved
signal
evidence
verified_evidence
```

核心规则包括：

- Signal 至少需要一个服务器可观察的实践信号；
- Evidence 至少需要两个不同成功任务情境；
- 还必须出现独立完成、修订、迁移或组合实践信号；
- Verified Evidence 进一步要求 transfer success；
- 必须存在 canonical Evidence 且 verification status 为 `VERIFIED`；
- 同一任务多个 Artifact/Evidence 版本不能伪装成多个任务情境；
- 前端点击、动画、停留时长和视觉状态不能提升 Capability。

## 已完成 P0：Real Work Sample Runtime

Real Work Sample 已形成真实工作式服务器流程：

```text
ready
→ working_v1
→ revision_required
→ transfer_ready
→ completed
```

当前已实现 V1、supervisor feedback、V2、transfer、Artifact version、Evidence 与 phase guard。V2 必须出现可验证的实质修改，Transfer 使用新的材料和新的判断要求。Work Sample 完成与 Verified Evidence 明确分离。

## 已完成 P0：Server-authoritative Spatial Practice

空间系统已经从简单 3D Work Lab 发展为 Alpha 7 Adaptive Showcase，但仍保持严格服务器权威边界：

```text
source = server
readOnly = true
clientMayPromoteCapability = false
clientMayVerifyEvidence = false
clientMayRewriteTrajectory = false
```

已完成的空间能力包括：

- Shader workstation / screen；
- transmission glass 与动态反射；
- SSR、depth-aware volumetric、Bloom、fullscreen transition；
- GPU-instanced data field；
- GPGPU capability topology network；
- Evidence → Capability particle flow；
- Capability awakening sequence；
- Artifact V1 / Feedback / V2 / Transfer destruction / assembly；
- Cinematic Sequencer；
- Lighting Timeline；
- Control Room transformation；
- Showcase Auto Demo Mode；
- Adaptive render budget。

## 已完成 P0：Adaptive Showcase Production Hardening

Alpha 7 已解决此前两个主要工程缺口。

第一，前端已经具备 `auto / ultra / high / balanced / safe` 质量预算。Auto 会综合设备信息、WebGL capability 与实时 FPS 逐级向下降档，并在 WebGL context loss 后保持 Safe。

第二，`frontend/package-lock.json` 已正式进入仓库，Spatial CI 与 Production Release 全部切换为 deterministic `npm ci`。独立 lockfile Gate 会重新生成候选 lockfile并要求零 diff，因此 package manifest 与实际发布依赖不能静默漂移。

---

# 下一 P0：Alpha 8 Runtime Certification & Telemetry

下一阶段不应继续无边界堆叠 Shader，而应验证 Alpha 7 在真实终端上的稳定性，并建立可审计性能证据。

重点：

- 首屏启动时间与首次可交互时间；
- FPS、1% low FPS 与 frametime 分布；
- GPU/renderer/WebGL capability fingerprint；
- 自动 quality 选择结果；
- 自动降档次数与触发原因；
- WebGL context-loss / restore 统计；
- SSR / volumetric / GPGPU 单项性能开销；
- Showcase Auto Demo 固定镜头性能基准；
- 长时间运行稳定性；
- Windows WebView2 certification harness；
- Intel 核显、AMD APU、NVIDIA 独显分档实机矩阵。

Runtime Telemetry 只能记录性能和渲染执行信息，不得把学生学习内容、Evidence 原文或私密实践数据混入性能遥测。

# 下一 P0：Windows x64 Release Certification

在真实 Windows 机器上完成：

```text
安装
→ 首次启动
→ 登录
→ Foundation / Work Sample
→ Spatial Showcase
→ quality auto 分档
→ 完全断网
→ 保存与重启
→ 导出
→ 备份
→ 升级
→ 数据迁移
→ 恢复
→ 卸载 / 重装
```

GitHub Actions Linux CI 不能替代 Windows/WebView2 真机认证。

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

配置系统需要持续服从服务器 Capability Verification 与 Evidence 权威规则，不能让模板配置自行宣布掌握。

# P1：Trajectory Analytics / Experimentation

增加 tenant 内可审计实验能力：

- Policy profile 版本比较；
- intervention recovery A/B；
- diagnosis agreement；
- hint dependency decline；
- transfer success；
- revision quality；
- human escalation precision；
- capability verification calibration。

默认不跨租户汇总原始学生轨迹；研究或模型训练必须另行处理授权、去标识和数据治理。

# P1：Teacher Growth 3.0

教师端继续从“批改”转向成长观察：

```text
这个学生在哪里连续失败
哪种提示真正有效
反馈后有没有实质修改
换材料后是否仍然会做
哪些 Evidence 已经被核验
Agent 哪些诊断被老师否定
什么时候应该人工介入
```

# P1：Independent Agent Deployment

当前 Learner Agent 已经做到行为独立、API 独立和依赖注入。只有当 LMS、第三方产品或多客户端跨系统调用规模明显增大后，再物理拆成独立服务。拆分时保持 `/api/learner-agent/v1` 客户端协议稳定。

---

## 当前发布原则

StepIn 的下一阶段判断标准不再是“又增加了多少页面或视觉特效”，而是：

1. 实践过程是否留下可追溯 Evidence；
2. Capability 是否由多个真实任务情境支撑；
3. Agent 是否能基于真实 Trajectory 做出受边界约束的下一步判断；
4. 高保真空间表现是否在不同硬件上稳定运行；
5. 构建、依赖、发布包和服务器权威边界是否保持可复现、可审计。
