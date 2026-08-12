# StepIn 2.0 Beta

**从一件简单真实的工作开始，在做、改、再做和项目积累中形成真正会做的能力。**

[返回首页](README.md) · [开发路线图](ROADMAP.md) · [Production integration PR #17](../../pull/17)

## StepIn 是什么

StepIn 面向零基础、零实习经验，甚至不知道真实工作每天具体在做什么的学生。

它不要求学生一开始就选专业、选岗位、学一堆课程或做职业测评，而是先给一件**真实、简单、马上能动手的小任务**。学生在不断做、修改、换场景再做和组合任务的过程中，逐渐形成真正能够独立完成、能够迁移、最后能够说清楚的实践能力。

核心路径：

**开始做 → 跟着做 → 自己做 → 根据反馈改 → 换场景再做 → 小任务组成项目 → 多任务叠加能力 → 把做过的事情讲出来。**

专业、课程和知识不是产品本身。它们只在当前任务真正需要时提供帮助。职业方向也不会要求学生一开始就决定，而是在完成多种真实任务以后逐渐出现。

## 先练会做事，再谈专业

Foundation 已经正式进入 production `main`。当前零基础阶段围绕 10 项跨专业公共实践能力组织：

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

学生先完成 8 个足够简单的小任务。前期提示更多，后面逐渐减少，直到可以自己完成、根据反馈修改、换场景再做。第 8 步会形成第一份小项目；之后还要把做过的事情讲清楚，并使用信息、判断、表达三种不同材料独立做一次，才进入更完整的职业实践。

## 当前 production 已形成的能力

- **零基础入口**：新手先做眼前这一小步，不先选择职业方向；
- **Foundation Runtime**：8 个连续小任务、渐退式提示和基础成长记录；
- **服务器级新手 Gate**：production 新手不能绕过基础阶段直接创建职业项目；
- **小任务 → 第一个项目**：分散动作会组合成 `foundation_project`；
- **跨材料探索**：信息、判断、表达三类不同材料都做过后才开放后续职业项目；
- **能力记录与作品**：继续使用 production Evidence / Artifact，不再建立影子数据系统；
- **教师基础成长**：教师能看到完成步骤、提示次数、独立完成和换场景表现；
- **双数据库兼容**：Foundation 跟随 production Repository Container，SQLite 与 PostgreSQL 各走原生实现；
- **CareerOS Core 保留**：原有 Domain Intelligence、Tenant / RLS、安全、Canonical API、模型路由和部署能力没有被覆盖。

## 为什么不是课程平台

StepIn 的起点不是“先学完再实践”。知识、课程和 AI 只在当前任务需要时出现：先遇到真实工作问题，再得到足够的解释、示范或提示，随后继续自己完成。

因此产品关注的不是“看了多少课”，而是：

> **现在到底能不能把一件事情做出来、改好，并在换一种材料以后仍然会做。**

## Production 集成结果

正式集成通过 [PR #17](../../pull/17) 完成，GitHub Actions 最终 Gate 为：

- 锁定回归矩阵：**189/189 通过**；
- Foundation production API contract：**10/10**；
- Database access audit：通过；
- Repository contract audit：通过；
- Python dependency audit：通过；
- 仓库漏洞 / Secret / 配置扫描：通过；
- Release container 漏洞扫描：通过；
- Python 与镜像 CycloneDX SBOM：已生成；
- Production deterministic ZIP 与 checksum：通过。

集成过程中还实际发现并修复了两个依赖安全问题：`cryptography` 升级到 `50.0.0`，`pypdf` 升级到 `6.15.0`，并重新生成完整 hash-lock。

## Rollout 规则

- production 中，没有既有职业项目的新 student 默认先进入 Foundation；
- 已经存在职业项目的学生不会被强制退回基础阶段；
- Demo / 历史兼容环境默认继续原项目流程；
- Demo 中需要验证 Foundation 时设置 `STEPIN_FOUNDATION_DEMO_GATE=true`；
- `STEPIN_FOUNDATION_DISABLED=true` 仅作为新手 Gate 的紧急运营回滚开关。

## 下一阶段开发

Production 主线统一已经完成，后续不再维护两套源码线。优先级调整为：

1. **Foundation 2.0**：把 FoundationAbility、ScaffoldLevel、TaskChain、MiniProject 进一步数据化和可配置化；
2. **多任务能力叠加**：让不同练习共同形成长期“我已经会做什么”的能力档案；
3. **Practice Studio 2.0**：老师和内容人员不用改 Python，也能创建基础练习、脚手架和任务链；
4. **表达与作品闭环**：把真实过程转成复盘、作品、简历表达和面试表达；
5. **Windows x64 发行认证**：真正构建 `StepIn.exe` / Installer，并完成安装、完全断网、备份、升级、恢复和本机 AI 的桌面 E2E。

完整优先级见 [ROADMAP.md](ROADMAP.md)。

<details>
<summary>技术底座</summary>

StepIn 2.0 Beta 运行在 CareerOS Core 上。CareerOS Core 继续负责 Domain Intelligence、Evidence Trust、Canonical API、Tenant / RLS、安全策略、SQLite / PostgreSQL Repository、多模型路由、生产部署、SBOM、安全扫描和锁定 CI。

旧 PR #16 只保留为 Foundation v1.9 的历史 staging 资料；正式 production integration 已由 PR #17 完成。

Windows x64 最终桌面安装包与完全断网 E2E 仍然是独立发行 Gate，不能因为 Linux GitHub Actions 通过就视为 Windows 真机认证完成。

</details>

## 快速启动

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
