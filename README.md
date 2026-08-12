# StepIn 2.0 Beta

**从一件简单真实的工作开始，在做、改、再做和项目积累中形成真正会做的能力。**

**Start with one simple, real task. Build practical capability by doing, revising, transferring, and combining work into projects.**

[中文说明](README.zh-CN.md) · [开发路线图](ROADMAP.md) · [Production integration PR #17](../../pull/17)

## StepIn 是什么

StepIn 面向零基础、零实习经验，甚至不知道真实工作每天具体在做什么的学生。

它不要求学生一开始就选专业、选岗位、学一堆课程或做职业测评，而是先给一件**真实、简单、马上能动手的小任务**。学生在不断做、修改、换场景再做和组合任务的过程中，逐渐形成能够独立完成、能够迁移、最后能够说清楚的实践能力。

**开始做 → 跟着做 → 自己做 → 根据反馈改 → 换场景再做 → 小任务组成项目 → 多任务叠加能力 → 把做过的事情讲出来。**

专业、课程和知识不是产品本身。它们只在学生当前任务需要时提供帮助。职业方向也不会要求学生一开始就决定，而是在完成多种真实任务以后逐渐出现。

## 从零基础开始

StepIn Foundation 已经进入 production `main`。新手阶段围绕 10 项跨专业公共实践能力展开：

- 看懂任务
- 找出关键信息
- 整理信息
- 比较与判断
- 发现问题
- 说明理由
- 按要求清楚交付
- 根据反馈修改
- 换一个场景再做
- 把自己做过的事情讲清楚

学生先完成 8 个足够简单的小任务。提示会逐渐减少；随后完成一次真实表达，再使用信息、判断、表达三种不同材料独立做一次，之后才进入更完整的职业实践。

## 当前 production 已具备

- **Foundation Runtime**：零基础任务、渐退式提示、基础成长记录
- **Beginner Gate**：production 新手不能绕过基础阶段直接创建职业项目
- **Task → Mini Project**：基础小任务组合成第一份真实小项目
- **Evidence / Artifact**：操作记录、版本、反馈和作品进入现有生产证据链
- **Teacher Growth View**：教师查看提示次数、独立完成、换场景表现和成长轨迹
- **Domain Intelligence**：CareerOS Core 原有 Claim → Capability → Job Requirement → Gap 生产能力继续保留
- **Tenant / RLS / Security**：现有租户隔离、权限、安全、审计和生产部署能力继续保留
- **SQLite / PostgreSQL**：Foundation 跟随 production Repository Container，不另建数据库路径
- **Local / Offline foundation**：现有本地 FastAPI + SQLite 能力继续作为离线桌面方向的基础

## 为什么不是课程平台

StepIn 的起点不是“先学完再实践”。知识、课程和 AI 只在当前任务需要时出现：学生先遇到真实问题，再得到足够的解释、示范或提示，随后继续自己完成。

因此产品关注的不是“看了多少课”，而是：

> **现在到底能不能把一件事情做出来、改好，并在换一种材料以后仍然会做。**

## English overview

StepIn is a **practice-first capability development system** for students with little or no internship experience.

Instead of beginning with courses, job labels, or career tests, it begins with one simple but realistic task. Support gradually fades as learners move from following a scaffold to working independently, revising from feedback, transferring the skill to a new context, combining small tasks into projects, and explaining what they can actually do.

**Start doing → Follow a scaffold → Work independently → Revise from feedback → Try again in a new context → Build projects from small tasks → Accumulate capability across tasks → Explain what you can actually do.**

Foundation is now integrated into the production codebase. The existing CareerOS Core — Domain Intelligence, tenant isolation, security, repositories, model routing, deployment, and CI — remains the production foundation underneath StepIn.

## Production validation

The production integration completed through [PR #17](../../pull/17) with the following GitHub Actions gates:

- locked regression matrix: **189/189 passed**
- Foundation production API contract: **10/10**
- database access audit: passed
- repository contract audit: passed
- Python dependency audit: passed
- repository vulnerability / secret / misconfiguration scan: passed
- release container vulnerability scan: passed
- Python and image CycloneDX SBOM: generated
- deterministic production ZIP + checksum verification: passed

During integration, known dependency vulnerabilities were removed by updating `cryptography` to `50.0.0` and `pypdf` to `6.15.0`, with the full hash-locked dependency file regenerated.

## Rollout behavior

- production participants with no existing professional project enter Foundation first;
- students with an existing professional project are not forced backwards;
- Demo / historical compatibility mode keeps the previous project flow by default;
- set `STEPIN_FOUNDATION_DEMO_GATE=true` only when Foundation needs to be exercised in Demo mode;
- `STEPIN_FOUNDATION_DISABLED=true` is an emergency operational rollback switch for the beginner gate.

## 下一步

Production integration 已完成。接下来不再维护两条源码主线，开发重点转为：

1. **Foundation 2.0**：把能力、脚手架等级、任务链和 Mini Project 从硬编码进一步数据化、可配置化；
2. **Capability Accumulation**：让不同任务共同形成“我已经会做什么”的长期能力档案；
3. **Practice Studio 2.0**：让教师不用改 Python 就能创建基础练习和任务链；
4. **Windows x64 Release Gate**：真正构建 `StepIn.exe` / Installer，并完成安装、断网、备份、升级、恢复的桌面 E2E。

完整计划见 [ROADMAP.md](ROADMAP.md)。

<details>
<summary>技术底座 / Engineering foundation</summary>

StepIn 2.0 Beta 运行在 CareerOS Core 上。Core 继续提供 Domain Intelligence、Evidence Trust、Canonical API、Tenant / RLS、安全策略、SQLite / PostgreSQL Repository、模型网关、生产部署、SBOM、安全扫描和锁定 CI。

旧 PR #16 保留为 v1.9 Foundation 的历史 staging 资料；正式 production integration 由已合并的 [PR #17](../../pull/17) 完成。

Windows x64 的最终桌面安装包与完全断网 E2E 仍是独立发行 Gate，尚不能因为 Linux GitHub Actions 通过就视为已完成 Windows 真机认证。

</details>

## Quick start

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
