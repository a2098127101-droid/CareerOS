# StepIn v1.9.0 · Foundation Test Report

Date: 2026-08-12  
Version: `1.9.0-beta-foundation`

## Foundation 专项

`tests/test_v190_foundation.py`: **7/7 passed**。

覆盖：

- 新用户 Today Next 首屏为 Foundation，而不是职业/项目入口。
- 完整 8 步基础链、提示预算、脚手架阶段、Evidence、第一份小项目、表达。
- 基础完成后 3 次桥接探索，再显示职业路径。
- 已有进行中专业 Run 不被 Foundation 打断。
- 教师读取单个学生成长轨迹。
- 普通学生不能通过 Practice API 绕过 Foundation。
- Foundation/Practice 显式 Session 绑定与跨 Session 拒绝。
- 教师无需等待 Triage 即可读取 Foundation Cohort。

## 跨版本关键分组

最终代码分组执行结果：

- v1.9 Foundation：7/7
- v1.8 Desktop Workbench：8/8
- v1.7 Portable Studio：4/4
- v1.6 Deep Offline：5/5
- v1.5.3 Focus Studio：4/4
- v1.5 Interaction 2.0：2/2
- Practice Runtime：2/2
- 10-template Practice Catalog：1/1
- v1.4 Canonical Runtime：7/7
- v1.3 Unified Runtime：4/4
- Today Next legacy compatibility：2/2
- Windows delivery constraints：5/5

合计关键定向断言：**51/51 passed**。

这些是分组关键 release gates，不等于宣称历史仓库所有旧版本专属测试均重新认证。旧测试曾存在 pytest 父进程在断言输出完成后不自动退出的历史清理债，因此继续采用分组隔离运行。

## API Contract

- Foundation：**8/8 required routes registered**
- Practice：**19/19 required routes registered**
- Interaction/Content：**18/18 required routes registered**

Python `compileall` 通过；student/teacher inline JavaScript 和 workbench-shell 等静态脚本语法检查通过。

## 真实 localhost HTTP

临时 Uvicorn 真 TCP/HTTP 四账号测试通过：participant / advisor / organization_admin / platform_admin 会话隔离正常。验证：

`Foundation Today Next → Foundation API → 直接 Practice 被 423 锁定 → 管理员支持性创建 Run → active Run 优先 → Teacher Foundation Cohort`。

## Chromium DOM + FastAPI bridge

真实生产 HTML/JS 与四个独立认证会话执行通过：

`Foundation 第一小步 → 服务端保存 → 专业 API 锁定 → 支持性专业 Run → Job-native Workbench → Live Evidence → Contextual Copilot → Teacher 基础成长 → Teacher Triage → Content Ops`

最终：**0 pageerror / 0 console error**。

## Windows 边界

当前环境仍不是 Windows，因此不声明最终 `StepIn.exe` / `StepIn-Setup-v1.9.0.exe` 已在 Windows 真机构建通过。Windows x64 构建和完全断网 E2E 仍为最终发行 Gate。
