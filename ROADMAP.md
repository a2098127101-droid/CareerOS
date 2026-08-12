# StepIn 2.0 Development Roadmap

## 最终目标

StepIn 面向零基础、零实习经验、甚至不知道真实工作每天具体在做什么的学生。

产品不从课程、岗位标签或职业测评开始，而从一件真实、简单、可以马上动手的小任务开始。学生通过反复做、修改、换场景再做、组合任务和表达成果，逐渐形成能够独立完成、能够迁移、能够说清楚的实践能力。

目标主链：

**开始做 → 跟着做 → 自己做 → 根据反馈改 → 换场景再做 → 小任务组成项目 → 多任务叠加能力 → 把做过的事情讲出来 → 后续专业分化。**

---

# 已完成：Production Integration

原来的 P0“production 主线与 StepIn Foundation 分叉”已经解决。

正式 production integration 由 [PR #17](../../pull/17) 完成并进入 `main`：

- Foundation domain / service / router 已进入 production `app/`；
- 新手 Beginner Gate 已进入 production；
- 10 项公共实践能力与 8 个连续基础任务已进入同一 Runtime；
- 表达训练与信息 / 判断 / 表达三种跨材料探索已接入；
- Foundation 使用 production Repository Container，保持 SQLite / PostgreSQL 双后端；
- 教师基础成长视图已接入；
- 旧职业项目与 Demo 历史路径保持兼容；
- 锁定 CI 从 184 扩展到 **189/189 passed**；
- Foundation API contract **10/10**；
- dependency / repository / container security scan 全部通过；
- production deterministic ZIP + checksum 通过；
- `cryptography` 与 `pypdf` 已升级到修复版本并重新生成 hash-lock。

旧 PR #16 仅保留为历史 staging 资料，不再作为运行源码。

---

# 当前 P0 — Foundation 2.0

现有 Foundation 已能真实运行，但任务、能力和脚手架仍有较多内置定义。下一阶段目标是把“怎么从不会到会做”正式做成可配置 Runtime，而不是继续靠增加 Python 常量扩内容。

## P0.1 正式领域模型

新增或固化：

```text
FoundationAbility
FoundationTask
ScaffoldLevel
TaskAttempt
TaskChain
MiniProject
AbilityEvidenceLink
AbilityProgress
ExpressionPractice
ExplorationExperience
```

这些对象必须成为服务器权威状态，并继续复用现有 Evidence / Artifact，而不是复制第二套业务数据库。

## P0.2 统一脚手架等级

```text
L0 看一次
L1 跟着做
L2 少提示做
L3 自己做
L4 换场景做
L5 连起来做
```

Today Next、提示系统、Foundation Runtime 和后续 Practice Runtime 都只读取这一套等级。

## P0.3 Task Chain Runtime

任务链至少支持：

- 前置任务；
- 顺序与依赖；
- 可选分支；
- 重做；
- 提示上限；
- Done-when；
- 独立版本；
- 迁移版本；
- 材料继承；
- 多个任务如何进入 Mini Project；
- Mini Project 如何生成真实作品。

目标不是“做 8 道题”，而是让几个简单动作自然长成一件完整的工作。

---

# P0 — Capability Accumulation

当前 Evidence 能记录过程，但下一步必须真正回答：

> **这个学生现在已经会做什么？**

同一种能力不能因为一道任务做对就判定掌握。至少综合：

```text
不同任务数量
不同材料类型
独立完成比例
提示依赖
修改质量
迁移任务结果
教师验证
时间跨度
```

学生端仍用普通语言表达：

```text
刚开始
能跟着做
能自己做
换一种情况也能做
已经比较稳定
```

复杂评分和内部 Evidence 结构留在系统内部。

---

# P1 — Beginner Mode 继续收紧

Foundation production 首页已经做到“一次只做当前一步”，下一阶段继续保证复杂工作台不会过早出现。

基础阶段默认只显示：

```text
现在要做什么
材料
当前一步
提交 / 下一步
需要时的一点提示
```

随着 Scaffold Level 和任务经验增长，再逐步开放：

- 搜索；
- 附件；
- 多选；
- 对比；
- 高级筛选；
- 快捷键；
- 完整专业 Workbench。

产品应该跟学生一起“长出来”。

---

# P1 — Practice Studio 2.0

Practice Studio 需要正式增加两种创建模式。

## 基础练习

先选：

```text
这次想练什么基础能力？
```

再配置：

- 材料；
- 示例；
- 当前一步；
- Scaffold Level；
- 提示预算；
- Done-when；
- 独立版本；
- 迁移版本；
- 可以和哪些任务组成 Mini Project。

## 专业练习

继续保留 Spreadsheet、ATS、CRM、Interview Coding、Issue Tracker、Research Board、Prioritization Board，并让它们复用相同 Task Chain / Evidence / Artifact 底层。

---

# P1 — 表达与作品闭环

每个 Mini Project 结束后继续强化三种出口：

1. **自己复盘**：我做了什么、哪里改过、学会了什么；
2. **简历表达**：2–3 行，只引用真实 Practice / Evidence；
3. **面试表达**：60–90 秒，能讲清任务、行动、修改和结果。

AI 只能整理真实过程，不允许补写不存在的经历和成果。

---

# P1 — Teacher Growth 2.0

教师核心不是“谁没交”，而是：

```text
谁还需要很多提示
谁开始能独立做
谁收到反馈以后不会改
谁换材料以后仍然会做
谁已经能把几个任务连起来
```

继续增加：

- 尝试次数；
- 提示使用；
- V1 / V2 修改前后；
- 迁移结果；
- Mini Project；
- 表达版本；
- 需要教师介入的真正原因。

---

# P1 — Windows x64 真机发行 Gate

这一项仍未由当前 Linux GitHub Actions 代替完成。

必须在真实 Windows x64 完整验证：

```text
安装
首次启动
学生 / 教师登录
Foundation
完全断网
继续练习
附件
DOCX / XLSX / PPTX / PDF 导出
退出重启
数据仍在
备份
升级安装
恢复
卸载 / 重装
WebView2 Evergreen
Fixed WebView2
本机 Ollama
低配置电脑
```

只有这组通过后，Desktop / Offline 才从“架构与构建链完成”升级为“正式发行认证完成”。

---

# P2 — 后续再做

在 Foundation 2.0、能力叠加和 Windows 发行稳定以前，不优先：

- 大量新增岗位；
- 复杂职业测评；
- 更多 AI Agent 名称；
- Dashboard 堆叠；
- 大规模课程库；
- 社交社区；
- 排行榜；
- 过度游戏化。

后续可考虑：

- Local AI Manager；
- 可选 Cloud Sync；
- 学校多租户运营；
- 内容质量遥测；
- 能力覆盖矩阵；
- Portfolio public page；
- 企业合作 Practice Package。

---

# 推荐版本节奏

## StepIn 2.0 Beta — 当前

目标：production Foundation 主线统一。**已完成。**

## 2.1 — Foundation 2.0

目标：可配置基础任务、脚手架、Task Chain、Mini Project。

## 2.2 — Capability Accumulation

目标：多任务能力聚合与长期能力档案。

## 2.3 — Expression & Portfolio

目标：复盘、简历、面试表达、真实作品输出。

## 2.4 — Practice Studio 2.0

目标：老师不用改源码即可创建 Foundation + Professional Practice。

## 2.5 — Windows Offline Release

目标：正式 Windows 安装包、升级、备份恢复、完全断网发行认证。

---

## 当前原则

**不要先教很多，再让学生找机会练。**

**先给一件足够简单但真实的事情，让学生做起来；知识、课程、专业和 AI 都只在这个过程中提供帮助。**
