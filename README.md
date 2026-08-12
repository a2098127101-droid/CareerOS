# StepIn / CareerOS

**从一件简单真实的工作开始，在做、改、再做和项目积累中形成真正会做的能力。**

**Start with one simple, real task. Build practical capability by doing, revising, transferring, and combining work into projects.**

[中文说明](README.zh-CN.md) · [StepIn Foundation v1.9 Draft PR](../../pull/16) · [v1.9 integration branch](../../tree/agent/stepin-foundation-v1.9.0)

> **当前仓库状态 / Repository status**  
> `main` 仍然是经过生产化强化的 **CareerOS v1.5 production baseline**。StepIn Foundation v1.9 正在通过 [PR #16](../../pull/16) 安全集成，尚未直接覆盖主线。当前首页已经按照新的产品方向更新，但下文明确区分“产品方向”和“已合并主线代码”。

## 为什么做 StepIn

很多零基础、零实习经验的学生，并不是缺少更多课程，而是不知道真实工作每天到底在做什么，也不知道第一步该从哪里开始。

StepIn 不把“选专业、选岗位、学课程、堆项目”作为起点。它先给学生一件**足够简单、但具有真实工作逻辑的小任务**，让学生先动手，再在实践中逐渐学会：看懂任务、找重点、整理信息、作出判断、说明理由、按要求交付、根据反馈修改、换一个场景再做，以及把自己做过的事情讲清楚。

核心路径：

**开始做 → 跟着做 → 自己做 → 根据反馈改 → 换场景再做 → 小任务组成项目 → 多任务叠加能力 → 把做过的事情讲出来。**

专业、课程和知识不是产品本身，而是在学生真正需要时为当前任务提供帮助。职业方向也不要求学生一开始就选择，而是在完成多种真实任务以后逐渐出现。

## StepIn Foundation v1.9

当前 v1.9 开发线重点实现：

- **10 项跨专业公共实践能力**：看懂任务、找重点、整理信息、比较判断、发现问题、说明理由、清楚交付、根据反馈修改、换场景再做、把做过的事情讲出来；
- **8 个连续零基础小任务**，从“4 件事先做哪件”开始，而不是从专业项目开始；
- **逐步减少提示**：跟着做 → 少提示 → 自己做 → 修改 → 换场景做；
- **Task → Mini Project**：分散的小任务会组合成第一份真实小项目；
- **跨任务 Evidence 聚合**：不是做对一道题就宣布“掌握能力”，而是观察同一种能力是否在不同任务中重复出现；
- **表达训练**：把真实做过的项目转成复盘、简历表达和面试表达；
- **延迟专业分化**：完成基础阶段后先体验表格、访谈、排序等不同材料，再逐渐开放职业路径；
- **服务器级 Gate**：学生不能通过直接调用专业 Practice API 绕过 Foundation；
- **教师基础成长视图**：教师看到的是学生从“需要提示”到“能够独立完成”的变化，而不只是最终答案。

完整 v1.9 代码目前位于：

- [StepIn Foundation integration branch](../../tree/agent/stepin-foundation-v1.9.0)
- [Draft PR #16](../../pull/16)
- [中文项目介绍](../../blob/agent/stepin-foundation-v1.9.0/stepin-foundation-v1.9.0/PROJECT_DESCRIPTION.zh-CN.md)
- [English project overview](../../blob/agent/stepin-foundation-v1.9.0/stepin-foundation-v1.9.0/PROJECT_DESCRIPTION.en.md)

## 已形成的 Practice OS 能力

StepIn 开发线已经形成一套以实践为中心的工作环境，而不是“AI 聊天 + 项目列表”：

- Focus Workspace：打开后只看到今天真正要做的一件事；
- Contextual Help：AI/规则提示附着在当前工作对象旁边，而不是占据独立聊天窗口；
- Job-native Workbenches：Spreadsheet、ATS、CRM、访谈编码、Issue Tracker、Research Board、Prioritization Board；
- Practice Runtime：做 → 改 → 再做一次 → 成果；
- Evidence / Artifact：保存操作证据、版本历史、教师反馈和作品；
- Simulation：换一批材料、减少提示，再验证一次；
- Teacher Triage：教师只处理真正需要人工判断的事项；
- Content Ops / Practice Studio：内容来源、审核、试跑、发布与受控无代码练习编辑；
- Local-first / Offline：本机 FastAPI + SQLite，断互联网后核心练习仍可继续；
- Desktop Workbench：Windows Portable / pywebview / WebView2 / Inno Setup 构建链；
- Real Outputs：支持将成果导出为 DOCX、XLSX、PPTX、PDF 和 Markdown。

> 上述 StepIn 能力来自持续开发线。v1.9 Foundation 尚在 PR #16 中与当前 production `main` 做受控集成，不能把未合并能力误认为已经全部进入主分支。

## 当前 production `main`

GitHub 主分支目前仍保留 CareerOS v1.5 production-final 的生产化能力，包括：

- Domain Intelligence：Claim → Capability → Job Requirement → Gap；
- Evidence Trust 与版本化能力评估；
- Tenant / RLS / 权限与安全强化；
- SQLite / PostgreSQL Repository；
- Unified Runtime 与 Canonical API；
- 多模型 Gateway；
- 生产部署、发布包、安全扫描与锁定 CI。

StepIn v1.9 不会用旧基线整仓覆盖这些能力。PR #16 的目标是把 Foundation、Practice-first 学习路径和学生/教师工作流逐步移植到当前 production 基座上。

## Quick start — current `main`

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

Default local demo accounts are documented in `.env.example`. Never enable demo seeding in production.

## English overview

StepIn is a **practice-first capability development system** for students with little or no internship experience. Instead of beginning with courses, job labels, or career tests, it begins with one simple but realistic work task that a beginner can actually complete.

The system gradually reduces support as the learner moves from following a scaffold to working independently, revising from feedback, transferring the skill to new situations, combining small tasks into projects, and explaining what they can actually do.

**Start doing → Follow a scaffold → Work independently → Revise from feedback → Try again in a new context → Build a project from small tasks → Accumulate capability across tasks → Explain what you can actually do.**

Specialization comes later. Courses and knowledge are support resources for the work in front of the learner, not the product itself.

### v1.9 integration status

The current GitHub `main` is still the CareerOS v1.5 production baseline. StepIn Foundation v1.9 is staged in [Draft PR #16](../../pull/16) because the Foundation development line evolved from an older source baseline. The integration intentionally preserves the existing Domain Intelligence, security, deployment, RLS, and CI capabilities on `main` instead of replacing them wholesale.

## Validation notes

The StepIn v1.9 development line reports the following targeted validation before production-main integration:

- Foundation: **7/7 passed**
- Key targeted regressions: **51/51 passed**
- Foundation API contract: **8/8**
- Practice contract: **19/19**
- Interaction / Content contract: **18/18**
- localhost four-role HTTP smoke: passed
- Chromium DOM + FastAPI bridge: **0 pageerror / 0 console error**

These are development-line results, **not yet the final production-main integration CI result**.

## Documentation

For the current production baseline:

- `ARCHITECTURE_v1.5.md`
- `DOMAIN_INTELLIGENCE_MODEL.md`
- `API_DOMAIN_INTELLIGENCE_GUIDE.md`
- `PRODUCTION_READINESS_v1.5.md`
- `REMAINING_GAPS_v1.5.md`
- `SOURCE_PROVENANCE_v1.5.md`

For StepIn Foundation v1.9, use [PR #16](../../pull/16) and the `stepin-foundation-v1.9.0/` integration directory on its branch.
