# StepIn / CareerOS

**从一件简单真实的工作开始，在做、改、再做和项目积累中形成真正会做的能力。**

> 当前仓库状态：`main` 仍然是 CareerOS v1.5 production baseline；StepIn Foundation v1.9 正在通过 [PR #16](../../pull/16) 做受控集成。首页已经按照当前产品方向更新，但未合并能力不会被写成已经进入生产主线。

## StepIn 是什么

StepIn 面向零基础、零实习经验，甚至不知道真实工作每天具体在做什么的学生。

它不从“选专业、选岗位、学课程、做职业测评”开始，而是先让学生完成一件**真实、简单、可以马上动手的小任务**。学生在不断做、修改、换场景再做和组合任务的过程中，逐渐形成真正能够独立完成、能够迁移、最后能够说清楚的实践能力。

核心路径：

**开始做 → 跟着做 → 自己做 → 根据反馈改 → 换场景再做 → 小任务组成项目 → 多任务叠加能力 → 把做过的事情讲出来。**

专业、课程和知识只是服务当前任务的内容，不是产品本身。职业方向也不会要求学生一开始就选择，而是在学生真正做过多种任务以后逐渐出现。

## v1.9 Foundation

当前 StepIn Foundation v1.9 开发线重点实现：

- 10 项跨专业公共实践能力；
- 8 个连续零基础基础任务；
- 提示逐步减少的脚手架机制；
- 小任务组合成第一份 Mini Project；
- 跨任务 Evidence 能力聚合；
- 项目复盘、简历表达与面试表达；
- 完成基础阶段后先进行 3 次跨材料探索，再逐步开放职业路径；
- 服务器级 Foundation / Exploration Gate，普通学生无法绕过基础阶段直接进入专业 Practice；
- 教师“基础成长”视图。

10 项公共实践能力包括：

1. 看懂任务；
2. 找出关键信息；
3. 整理信息；
4. 比较与判断；
5. 发现问题；
6. 说明理由；
7. 按要求清楚交付；
8. 根据反馈修改；
9. 换一个场景再做；
10. 把自己做过的事情讲清楚。

完整 v1.9 集成内容：

- [StepIn Foundation v1.9 开发分支](../../tree/agent/stepin-foundation-v1.9.0)
- [Draft PR #16](../../pull/16)
- [中文项目介绍](../../blob/agent/stepin-foundation-v1.9.0/stepin-foundation-v1.9.0/PROJECT_DESCRIPTION.zh-CN.md)
- [English Project Overview](../../blob/agent/stepin-foundation-v1.9.0/stepin-foundation-v1.9.0/PROJECT_DESCRIPTION.en.md)

## 已形成的实践系统能力

StepIn 当前开发线已经不再是“AI 聊天 + 项目列表”，而是围绕真实任务组织工作：

- **Focus Workspace**：进入后只处理今天真正要做的一件事；
- **Contextual Help**：提示只出现在当前工作对象旁边；
- **Job-native Workbench**：Spreadsheet、ATS、CRM、访谈编码、Issue Tracker、Research Board、Prioritization Board；
- **Practice Runtime**：做 → 改 → 再做一次 → 成果；
- **Evidence / Artifact**：保留操作证据、版本、反馈和作品；
- **Simulation**：换一批材料、减少提示，再验证一次；
- **Teacher Triage**：教师优先处理真正需要人工判断的问题；
- **Content Ops / Practice Studio**：来源、审核、试跑、发布和受控无代码练习编辑；
- **Offline / Local-first**：本机 FastAPI + SQLite，断互联网以后核心练习仍可继续；
- **Desktop Workbench**：已经具备 Windows Portable、pywebview、WebView2 和 Inno Setup 构建链；
- **真实成果导出**：支持 DOCX、XLSX、PPTX、PDF 和 Markdown。

这些能力来自 StepIn 持续开发线。v1.9 Foundation 仍在 PR #16 中与当前 production `main` 做正式集成，因此不能把所有能力都视为已经进入主分支。

## 当前主分支技术基座

GitHub `main` 当前仍然保留 CareerOS v1.5 production-final 的生产化能力：

- Claim → Capability → Job Requirement → Gap 领域智能链；
- Evidence Trust 与版本化评估；
- Tenant / RLS / 权限与安全强化；
- SQLite / PostgreSQL Repository；
- Unified Runtime 与 Canonical API；
- Multi-Model Gateway；
- 生产部署、发布、安全扫描与锁定 CI。

StepIn v1.9 不会用旧代码整仓覆盖这些能力。当前 Draft PR 的目标，是把 Foundation、Practice-first 路径以及学生/教师工作流逐段接到现有 production 主线上。

## 当前主分快速启动

Windows：

```text
OPEN_CareerOS.cmd
```

Python：

```bash
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload
```

本地演示账号配置见 `.env.example`。生产环境不要启用 Demo 用户自动生成。

## v1.9 开发线验证

StepIn v1.9 在独立开发线上的定向验证结果：

- Foundation：**7/7 通过**；
- 关键跨版本定向回归：**51/51 通过**；
- Foundation API contract：**8/8**；
- Practice contract：**19/19**；
- Interaction / Content contract：**18/18**；
- localhost 四角色 HTTP smoke：通过；
- Chromium DOM + FastAPI bridge：**0 pageerror / 0 console error**。

这些结果属于 StepIn v1.9 开发线，**不是 production main 完成集成后的最终 CI 结果**。

## 当前最重要的集成任务

1. 把 Foundation domain / router 接入当前 production `app/main.py`；
2. 在不回退 Domain Intelligence、安全和部署能力的前提下移植 Today Next / Practice Gate；
3. 合并学生 Foundation UI 和教师基础成长视图；
4. 将 Foundation 测试加入现有锁定 CI；
5. 执行完整 production test / security / release matrix；
6. 在 Windows x64 真机构建并验证最终 `StepIn.exe`、Installer 与完全断网 E2E。

在这些工作完成以前，PR #16 保持 Draft。
