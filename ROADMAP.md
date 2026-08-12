# StepIn Development Roadmap

## 最终目标

StepIn 面向零基础、零实习经验、甚至不知道真实工作每天具体在做什么的学生。

产品不从课程、岗位标签或职业测评开始，而从一件真实、简单、可以马上动手的小任务开始。学生通过反复做、修改、换场景再做、组合任务和表达成果，逐渐形成真正能够独立完成、能够迁移、能够说清楚的实践能力。

目标主链：

**开始做 → 跟着做 → 自己做 → 根据反馈改 → 换场景再做 → 小任务组成项目 → 多任务叠加能力 → 把做过的事情讲出来 → 后续专业分化。**

---

## 当前最主要的问题

### 1. Production 主线与 StepIn 开发线仍然分开

当前 `main` 保留 CareerOS 的生产化技术基座，StepIn Foundation v1.9 以 PR #16 的 staging 形式存在。两条线长期并行会带来版本、README、CI、数据模型和发布认知混乱。

**这是当前 P0。**

### 2. Foundation 已能运行，但仍偏“内置流程”

当前 10 项公共能力、8 个基础任务、脚手架渐退、小项目和表达链已经建立，但仍缺完整可配置层。内容人员还不能自由组合 Foundation Task、Scaffold Level、Task Chain 和 Mini Project。

### 3. Beginner Mode 还没有成为完整产品模式

专业 Workbench 已经很强，但零基础用户仍可能过早接触复杂工具。Foundation 阶段应该一次只显示当前动作，高级搜索、快捷键、复杂工作台、附件等能力应逐步解锁。

### 4. Evidence 已记录过程，但跨任务能力聚合还不够强

“做完一个任务”不能直接等于“掌握能力”。同一种能力应该在不同任务、不同材料、较少提示条件下重复出现，才逐渐提升可信度。

### 5. 小任务 → 项目仍需升级为正式 Runtime

目前可以组合第一份 Mini Project，但未来应该支持可配置 Task Chain、依赖关系、分支、重做、跨任务素材继承和项目输出模板。

### 6. Practice Studio 仍偏专业 Workbench Builder

下一步需要同时支持 Foundation Builder：先选基础能力，再配置材料、步骤、提示、完成条件、独立阶段、迁移任务和项目组合。

### 7. Windows 桌面 / 离线仍缺真实发行认证

构建链、WebView2、Portable、Installer、备份恢复已经准备，但仍需 Windows x64 真机构建与完整离线 E2E。

---

# P0 — 先统一代码主线

## P0.1 建立新的 production integration 分支

不要继续在旧基线 Foundation 分支上堆产品功能。

建议：

```text
main
  └─ integration/stepin-foundation-production
```

从最新 `main` 创建，再把 Foundation 功能逐段移植进去。

### 移植顺序

1. Foundation domain models；
2. Foundation Progress service；
3. Foundation router；
4. Today Next Foundation priority；
5. Practice Gate；
6. Student Foundation UI；
7. Teacher Foundation Growth；
8. Foundation contract / regression tests；
9. production CI / security / release gates。

### 禁止做法

不要用旧开发线的 `app/main.py`、安全配置、部署配置或 CI 文件整仓覆盖 production `main`。

### 完成标准

- `main` 只有一套运行时；
- Foundation API 在 production app 中直接注册；
- 原 Domain Intelligence / RLS / security / deployment 保持；
- Foundation + Practice + production tests 全部在同一 CI 中通过；
- PR #16 从 staging 任务转为已完成历史记录或被新的 production integration PR 取代。

---

# P0 — Foundation 2.0

## P0.2 正式领域模型

建议新增或固化：

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

## P0.3 脚手架等级

统一为：

```text
L0 看一次
L1 跟着做
L2 少提示做
L3 自己做
L4 换场景做
L5 连起来做
```

Today Next、提示系统和 Practice Runtime 都只读取这一套级别，不再各自判断。

## P0.4 Task Chain

任务链必须支持：

- 前置任务；
- 顺序；
- 可选分支；
- 重做；
- 提示上限；
- 通过条件；
- 迁移任务；
- 输出如何进入 Mini Project。

---

# P1 — Beginner Mode

Foundation 阶段默认只显示：

```text
现在要做什么
材料
当前一步
提交 / 下一步
需要时的一点提示
```

隐藏：

- 专业路径；
- 复杂 Workbench 设置；
- Ctrl+K 高级命令；
- 高级筛选；
- 能力术语；
- 复杂 Evidence 技术状态。

随着 Scaffold Level 和任务经验增长，再逐步展开 Workspace Mode。

---

# P1 — 多任务能力叠加

## 能力不按单题判定

建议能力可信度至少综合：

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

输出面向学生时仍使用普通语言：

```text
刚开始
能跟着做
能自己做
换一种情况也能做
已经比较稳定
```

不要直接暴露复杂评分模型。

---

# P1 — 表达训练

每个 Mini Project 结束后生成三种训练：

1. **自己复盘**：我做了什么、哪里改过、学会了什么；
2. **简历表达**：2–3 行，不虚构结果；
3. **面试表达**：60–90 秒，能讲清任务、行动、修改和结果。

表达必须引用真实 Practice / Evidence / Artifact，不允许 AI 编造经历。

---

# P1 — Practice Studio 2.0

新增两种创建模式：

## 基础练习

先选：

```text
练什么基础能力
```

再配置：

- 材料；
- 当前一步；
- 示例；
- 提示；
- Scaffold Level；
- Done-when；
- 独立版本；
- 迁移版本；
- 可组合进哪个 Mini Project。

## 专业练习

继续保留 Spreadsheet、ATS、CRM、Interview Coding、Issue Tracker、Research Board、Prioritization Board。

---

# P1 — Teacher Growth View

教师核心不再是“谁没交作业”，而是：

```text
谁还需要很多提示
谁开始能独立做
谁在反馈后不会改
谁能换场景继续做
谁已经能把几个任务连起来
```

教师能够进入学生过程轨迹：

- 尝试次数；
- 提示使用；
- 修改前后；
- 迁移结果；
- Mini Project；
- 表达版本。

---

# P1 — Windows 真机发行 Gate

必须在 Windows x64 真机完成：

```text
安装
首次启动
学生 / 教师登录
完全断网
练习
附件
导出
退出重启
备份
升级安装
恢复
卸载 / 重装
WebView2 Evergreen
Fixed WebView2
本机 Ollama
低配置电脑
```

只有这组通过后，才能把 Desktop / Offline 从“构建链完成”升级为“发行完成”。

---

# P2 — 后续再做

在上述底层稳定以前，不优先：

- 继续增加大量岗位；
- 做复杂职业测评；
- 做更多 AI Agent 名称；
- 继续堆 Dashboard；
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

## v1.9.x — Production Integration

目标：结束 production / Foundation 两条线并行。

## v2.0 — Foundation 2.0

目标：可配置基础任务、脚手架、Task Chain、Mini Project。

## v2.1 — Capability Accumulation

目标：多任务能力聚合与长期能力档案。

## v2.2 — Expression & Portfolio

目标：复盘、简历、面试表达、真实作品输出。

## v2.3 — Practice Studio 2.0

目标：老师不用改源码即可创建 Foundation + Professional Practice。

## v2.4 — Windows Offline Release

目标：正式 Windows 安装包、升级、备份恢复、完全断网发行认证。

---

## 当前原则

**不要先教很多，再让学生找机会练。**

**先给一件足够简单但真实的事情，让学生做起来；知识、课程、专业和 AI 都只在这个过程中提供帮助。**
