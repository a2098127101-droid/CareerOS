# StepIn SceneState & Spatial Practice UI · v3 alpha

## 目标

这一阶段不是把现有页面换成 3D 皮肤，而是先建立可以被 2D、3D、Desktop 或后续其他客户端共同消费的实践语义层。3D 只负责空间呈现、聚焦、检查和动画，不拥有成长判定权。

当前链路：

```text
Foundation / Learner Agent / Trajectory / Projects / Evidence / Artifacts
                         +
             Capability Verification 2.0
                         +
                Real Work Sample
                         ↓
                    SceneState
                         ↓
          React DOM Workbench + R3F Work Lab
```

## SceneState Contract

`GET /api/scene/v1/state` 返回当前 student + tenant + session 的服务器权威只读快照。它聚合 Foundation、Learner Agent State、Trajectory、Trajectory metrics、Projects、Evidence、Artifact versions、Capability Verification 和 Real Work Sample。

`spatial.nodes` 只是一组语义节点，而不是业务数据库。当前节点包括 Foundation Workstation、Real Work Sample Workstation、Project、Artifact version、Evidence、Capability 和最近的 Trajectory event。`spatial.connections` 表达 Evidence 对 Artifact/Capability 的支持关系。

所有 SceneState 明确声明：

```json
{
  "source": "server",
  "readOnly": true,
  "clientMayPromoteCapability": false,
  "clientMayVerifyEvidence": false,
  "clientMayRewriteTrajectory": false,
  "allowedClientEffects": ["focus", "inspect", "filter", "camera", "animation"]
}
```

React 客户端还会再次检查这组 authority 字段；如果服务器返回的 Contract 失去只读边界，客户端拒绝把它当成有效 SceneState。

## Capability Verification 2.0 minimum

当前验证层只有四个状态：

```text
unobserved
signal
Evidence
Verified Evidence
```

Signal 只表示系统已经观察到与该能力有关的实践，不能表达“已经会做”。Evidence 至少要求同一能力出现在两个不同的成功任务情境，并且出现独立完成、实质修订、迁移或组合任务信号。不同版本的同一 Evidence 不会被当成多个任务情境。

Verified Evidence 进一步要求已经达到 Evidence、存在一次换材料迁移成功，并且至少一条 canonical Evidence 的 verification status 为 `VERIFIED`。因此完成 V1、出现动画、停留时间、点击次数、Agent 一次判断、前端本地分数都不能把 Capability 升级成 Verified Evidence。

这个规则是最低工程可信度，不代表已经完成教育学效度验证。后续仍需要真实零基础学生纵向数据、人工标签和阈值校准。

## Real Work Sample 01

第一个工作样本是“高峰时段支持工单交接”。学生面对的是同时出现的聊天消息、工单、客户/系统信号和明确截止时间，不再被拆成十道明显问答题。

流程为：

```text
进入值班材料
→ 选择需要优先交接的事项
→ 写出 V1 交接 + 工作过程
→ 收到模拟主管反馈
→ 实质修改成 V2
→ 换一组新的运营材料
→ 无主管提示完成 Transfer
```

V1 只形成过程 Signal，并创建未核验 Evidence。V2 通过服务器检查后可以贡献一个成功任务情境；Transfer 成功可以贡献迁移信号。三个阶段产生的 Evidence 默认均为 `SELF_REPORTED`，不会因为 Work Sample 自己判分而变成 `VERIFIED`。

## React / 3D client

新的前端位于 `frontend/`，生产构建目标为 `app/static/app/`，FastAPI 通过 `/app`、`/app/foundation` 与 `/app/work-sample` 提供同一个 SPA shell。构建产物不存在时，服务器回退到旧 `/static/foundation.html`，因此当前静态 UI 没有删除。

3D Work Lab 当前只有一个小型空间，没有校园、城市、自由走动或 3D 吉祥物。镜头只能在 Hub、Foundation Workstation 和 Real Work Sample Workstation 之间由程序切换。真正需要阅读、选择、填写和修改的工作仍使用 DOM panel，以保证信息密度、键盘输入和可访问性。

场景还会呈现 Evidence shelf、Project/Artifact version table、Capability field 和最近 Trajectory line。Capability 球体的亮度和尺寸只读取服务器的 `verificationLevel`，不在浏览器中计算成长。

R3F Canvas 使用 demand rendering；静止时不需要持续刷新整个 3D 场景。当前场景不依赖远端 HDR、字体或 3D 模型资源，降低离线/桌面方向的隐式网络依赖。

## 当前工程边界

1. Spatial UI 仍是 alpha，不应该替代真实用户可用性测试。判断重点不是“是否更炫”，而是零基础学生是否更快理解当前任务、是否减少 Dashboard/问卷感，以及 3D 空间是否帮助理解项目、版本和能力证据之间的关系。
2. Capability Verification 2.0 目前是保守规则引擎，不是教育测量终稿，也没有把置信度解释为心理测量意义上的能力分数。
3. Frontend 已纳入 TypeScript typecheck 和 Vite build CI，但当前尚未提交确定性的 npm lockfile，因此前端依赖供应链还没有达到后端 hash-locked Python 依赖的发行强度。
4. Source checkout 未执行前端 build 时 `/app` 会回退旧 UI；正式发行流程需要生成 `app/static/app/` bundle。
5. Windows x64、完全断网、低配置机器、WebView2 与安装/升级/恢复仍需独立真机 Gate。

## 下一阶段

Spatial alpha 通过工程 Gate 后，不优先增加新 3D 房间。先用真实零基础学生测试 Foundation workstation 和第一个 Real Work Sample，观察任务理解时间、首次独立完成率、提示依赖、V1→V2 实质修改率、Transfer 成功、退出/回流和 3D 交互误触。只有这些数据表明空间表达有价值，才继续扩展 Evidence/Trajectory/Capability 的空间交互密度和更多 Work Sample。
