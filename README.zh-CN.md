# StepIn 2.2 Beta

**从一件简单真实的工作开始，让每次尝试、失败、修改、反馈和迁移都成为下一步教学决策的依据。**

[返回英文首页](README.md) · [架构](ARCHITECTURE.md) · [开发路线图](ROADMAP.md) · [测试状态](TEST_REPORT.md) · [Runtime Telemetry](docs/SPATIAL_RUNTIME_TELEMETRY_ALPHA8.md) · [Learner Agent Runtime](docs/LEARNER_AGENT_RUNTIME_v2.1.md) · [真实轨迹与校准](docs/LEARNER_TRAJECTORY_AND_CALIBRATION_v2.2.md)

## 当前产品定义

StepIn 面向零基础、零实习经验，甚至还不知道真实工作每天具体在做什么的学生。产品不从职业测评、课程目录、徽章积累或泛化聊天开始，而是先给学生一件足够简单、可以马上动手的真实任务。

**开始做 → 跟着做 → 自己做 → 失败时被诊断 → 根据反馈修改 → 换场景再做 → 小任务组成项目 → 多任务叠加能力 → 用证据说明自己真正做过什么。**

## 当前生产核心

StepIn 2.2 以 **Learner Agent + Practice Runtime + Evidence/Artifact + Human Review** 为核心。Learner Agent 已拥有独立 State、Policy、Tools、Memory、Trajectory、Execution Loop、Evaluation 与有边界的 Calibration，并通过 `/api/learner-agent/v1` 向 Web、Desktop、LMS 或其他客户端提供稳定接口。

LLM 只负责语言表达与脚手架措辞，不能自行选择高权限工具，不能绕过服务器 Gate，不能替学生生成最终交付物，不能验证 Evidence，不能直接提升 Capability，也不能自动激活候选 Policy。

学生在真实任务中的保存、求助、失败、完成、修订、迁移、教师反馈、Evidence 决策、项目里程碑、人工复核和 Agent 干预都会进入服务器侧 Learner Trajectory。短期会话 Memory 与长期 Trajectory 分离。

## Capability Verification 2.0

能力状态由服务器权威判定，目前使用四级结构：

```text
unobserved
signal
evidence
verified_evidence
```

进入 `evidence` 至少需要多个不同任务情境中的成功记录，并同时出现独立完成、修订、迁移或组合实践信号。进入 `verified_evidence` 还要求迁移成功，并存在 canonical Evidence 且验证状态为 `VERIFIED`。同一任务的多个版本不能伪装成多个任务情境，前端点击、动画、停留时长和视觉强度均不能提升能力。

## Real Work Sample Runtime

当前 Real Work Sample 已完成完整服务器流程：

```text
ready
→ working_v1
→ revision_required
→ transfer_ready
→ completed
```

V1 会形成 Artifact/Evidence，并生成确定性的 supervisor feedback；V2 必须出现实质修改并通过服务器验证；Transfer 使用新的材料和新的任务要求，不提供提示。Work Sample 完成本身不等于 Verified Evidence。

## Spatial Practice Alpha 7 · Adaptive Showcase

当前 `/app` 主入口继续运行 **Alpha 7 Adaptive Showcase** 高保真视觉系统，并在外层加入 **Alpha 8 Runtime Telemetry** 认证基础设施。3D 场景仍然只是建立在服务器 SceneState 上的表现层，技术栈包括 React 19、React Three Fiber、Drei 与 Three.js。

当前已经实现：

- 自定义 WebGL Shader 工作站与控制屏；
- Transmission 玻璃、动态 CubeCamera 反射和高反射空间结构；
- SSR、深度感知 volumetric raymarch、Bloom 与全屏转场 Shader；
- 服务器 Evidence → Capability 能量流；
- GPU instancing 数据场与 GPGPU Capability topology reflow；
- Capability 大型觉醒序列；
- V1 / Feedback / V2 / Transfer Artifact 拆解、组装与对比演出；
- 基于时间轴的镜头、灯光和空间变形导演系统；
- 用于展示录屏的自动 Showcase Mode。

自动录屏模式：

```text
/app?demo=1
/app?showcase=1
```

演示模式只控制 camera、lighting、topology、room、Artifact 和 post-processing，不修改服务器学习数据，并明确显示为 visual rehearsal。

## 自适应渲染预算

Alpha 7 保留 Alpha 6 的全效果路径作为 Ultra，同时提供生产环境质量分档：

```text
/app?quality=auto
/app?quality=ultra
/app?quality=high
/app?quality=balanced
/app?quality=safe
/app?qualitydebug=1
```

`auto` 会综合 CPU 核数、device memory、屏幕像素负载、WebView 特征和 WebGL capability 选择初始档位，并持续采样 FPS。自动模式只在性能持续低于预算时向下降档，不会在同一 session 内反复自动升降。

- **Ultra**：SSR + volumetric + Bloom，48×48 即 2,304 个 GPGPU topology particles，1,800 个 instanced data；
- **High**：保留 SSR/volumetric/Bloom，40×40 topology，1,200 个 data instances；
- **Balanced**：32×32 topology、720 个 data instances，关闭 SSR/volumetric，保留 Bloom 与 transition；
- **Safe**：DPR 固定为 1，24×24 topology、320 个 data instances，同时关闭 SSR、volumetric、Bloom 和实时阴影。

如果 WebView2 或显卡驱动发生 WebGL context loss，当前 session 会直接进入 Safe；context restored 后仍保持 Safe，不会立即重新启动最高负载路径。

## 动态效果无障碍策略

现在“画质”和“持续动态”已经分离。用户可以保留 Ultra 材质和光照，同时关闭连续动画：

```text
/app?motion=full
/app?motion=reduced
/app?motion=off
```

未显式指定时，系统会尊重 `prefers-reduced-motion: reduce`，进入 reduced 模式。Reduced/Off 不再通过强制 Safe 来实现，而是把 React Three Fiber 从持续 animation loop 切换为 demand rendering；状态变化和交互仍能生成新画面，但不会持续执行镜头、粒子和空间运动。

## Alpha 8 Runtime Telemetry

当前增加三条认证遥测接口：

```text
GET  /api/spatial-runtime/v1/telemetry/contract
POST /api/spatial-runtime/v1/telemetry
GET  /api/spatial-runtime/v1/telemetry/summary
```

遥测只接受白名单字段：quality tier/request、motion mode、FPS、P50/P95/P99 frametime、分桶后的 viewport/device 特征、WebView 标志、WebGL capability limits 和粗粒度 GPU 厂商类别。系统不接受 raw User-Agent、raw GPU renderer、学生答案、任务材料、Evidence 文本、user ID 或 session ID。持久 analytics 记录使用空 user/session 标识，遥测结果也不会写入 Capability、Evidence、Artifact 或 Learner Trajectory。

## 服务器权威边界

3D 场景继续严格保持只读：

```text
source = server
readOnly = true
clientMayPromoteCapability = false
clientMayVerifyEvidence = false
clientMayRewriteTrajectory = false
```

镜头、Shader、灯光、粒子、质量档位、motion policy、telemetry 和 cinematic sequence 都只能改变视觉执行与认证证据，不会给学生增加任何成长记录。

## 当前生产验证

当前 production baseline 的自动回归合同锁定为 **208 / 208**。生产 Gate 同时包括：

- canonical StepIn release baseline audit；
- Alpha 8 spatial runtime telemetry/privacy audit；
- 前端 package-lock 零漂移校验；
- deterministic `npm ci`；
- TypeScript typecheck 与 Vite production build；
- FastAPI spatial bundle entry；
- Foundation、Learner Agent 与 Project Library audit；
- 数据库访问与 Repository contract audit；
- dependency audit 与 CycloneDX SBOM；
- repository vulnerability / secret / misconfiguration scan；
- source multi-stage release container build / vulnerability scan；
- deterministic production ZIP 与 archive boundary 校验。

前端依赖和 Docker/Release 构建已经统一使用同一 lockfile。以上工程结果说明代码和发布合同一致，但不等于教育效果已经验证，也不等于所有 GPU 或目标部署环境已经认证。真实 pilot 环境以及 Windows WebView2、Intel 核显、AMD APU、NVIDIA 多机型性能认证仍由 Issue #20 单独记录证据。

## 快速启动

Windows：

```text
OPEN_StepIn.cmd
```

Python 后端：

```bash
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Spatial Frontend：

```bash
cd frontend
npm ci
npm run typecheck
npm run build
```

Vite 构建结果会进入 FastAPI `/app` 使用的 spatial bundle。演示账号配置见 `.env.example`，生产环境不要启用 Demo 用户自动生成。
