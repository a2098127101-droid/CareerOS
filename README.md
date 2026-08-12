# StepIn / CareerOS

**从一件简单真实的工作开始，在做、改、再做和项目积累中形成真正会做的能力。**

**Start with one simple, real task. Build practical capability by doing, revising, transferring, and combining work into projects.**

[中文说明](README.zh-CN.md) · [开发路线图](ROADMAP.md) · [Foundation v1.9 PR #16](../../pull/16)

## StepIn 是什么

StepIn 面向零基础、零实习经验，甚至不知道真实工作每天具体在做什么的学生。

它不要求学生一开始就选专业、选岗位、学一堆课程或做职业测评，而是先给一件**真实、简单、马上能动手的小任务**。学生在不断做、修改、换场景再做和组合任务的过程中，逐渐形成真正能够独立完成、能够迁移、最后能够说清楚的实践能力。

**开始做 → 跟着做 → 自己做 → 根据反馈改 → 换场景再做 → 小任务组成项目 → 多任务叠加能力 → 把做过的事情讲出来。**

专业、课程和知识不是产品本身。它们只在学生当前任务需要时提供帮助。职业方向也不会要求学生一开始就决定，而是在完成多种真实任务以后逐渐出现。

## 从零基础开始

Foundation 当前围绕 10 项跨专业公共实践能力组织入门任务：

- 看懂任务；
- 找出关键信息；
- 整理信息；
- 比较与判断；
- 发现问题；
- 说明理由；
- 按要求清楚交付；
- 根据反馈修改；
- 换一个场景再做；
- 把自己做过的事情讲清楚。

学生先完成一组足够简单的小任务。提示会逐渐减少，再进入独立完成、换场景练习、小项目组合和表达训练。专业化工作台放在这之后。

## 已形成的实践工作环境

StepIn 持续开发线已经形成：

- **Focus Workspace**：打开后只处理今天真正要做的一件事；
- **Foundation Runtime**：零基础任务、逐步减少提示、基础成长记录；
- **Practice Runtime**：做 → 改 → 再做一次 → 成果；
- **Job-native Workbenches**：Spreadsheet、ATS、CRM、访谈编码、Issue Tracker、Research Board、Prioritization Board；
- **Contextual Help**：提示附着在当前工作对象旁边，而不是单独占一个聊天页面；
- **Evidence / Artifact**：保存操作记录、版本、反馈和作品；
- **Simulation**：换一批材料、减少提示，再做一次；
- **Teacher View**：既看需要人工判断的事项，也看学生从“需要提示”到“能够独立完成”的变化；
- **Practice Studio**：受控地创建、审核、试跑和发布练习；
- **Local-first / Offline**：核心练习以本机 FastAPI + SQLite 为基础，可在无互联网情况下继续运行；
- **Desktop Workbench**：Windows Portable / pywebview / WebView2 / Inno Setup 构建链；
- **Real Outputs**：支持 DOCX、XLSX、PPTX、PDF 和 Markdown 输出。

## English overview

StepIn is a **practice-first capability development system** for students with little or no internship experience.

Instead of beginning with courses, job labels, or career tests, StepIn begins with one simple but realistic work task that a beginner can actually complete. Support gradually fades as the learner moves from following a scaffold to working independently, revising from feedback, transferring the skill to a new situation, combining small tasks into projects, and explaining what they can actually do.

**Start doing → Follow a scaffold → Work independently → Revise from feedback → Try again in a new context → Build projects from small tasks → Accumulate capability across tasks → Explain what you can actually do.**

Specialization comes later. Courses and knowledge are support resources for the work in front of the learner, not the product itself.

## 开发路线 / Development

当前开发重点不是继续堆更多岗位，而是先把三件事做扎实：

1. 把 Foundation 正式接入 production 主线，结束两条代码线并行；
2. 把基础任务、脚手架撤离、Task Chain、Mini Project 和跨任务能力聚合做成可配置底层能力；
3. 在 Windows 真机完成桌面安装、完全断网、备份恢复和升级验证。

完整计划见 [ROADMAP.md](ROADMAP.md)。

<details>
<summary>工程集成状态 / Engineering integration status</summary>

当前 GitHub `main` 保留 CareerOS 的生产化技术基座，包括 Domain Intelligence、权限与安全、Repository、Canonical API、模型路由、部署与 CI。StepIn Foundation v1.9 正在 [PR #16](../../pull/16) 中做受控集成。

PR #16 当前是 staging/integration PR，不应通过整仓覆盖的方式替换 production 主线。下一步应从最新 `main` 建立 production integration 分支，把 Foundation domain、Today Next、Practice Gate、学生/教师工作流和测试逐段接入，再执行完整 CI、安全和 Windows 发行验证。

The current production `main` remains the technical baseline. StepIn Foundation v1.9 is being integrated through [PR #16](../../pull/16). The integration should preserve the existing production security, deployment, Domain Intelligence and CI layers rather than replacing the repository wholesale.

</details>

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

Local demo account settings are documented in `.env.example`. Do not enable demo seeding in production.
