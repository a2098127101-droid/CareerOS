# StepIn v1.9.0 · Windows Foundation / Offline Release

v1.9 继承 v1.8 的桌面与离线架构：`StepIn.exe → pywebview/WebView2 → 本机 FastAPI → SQLite`。Foundation Runtime、基础任务、成长记录、Evidence 和第一份小项目均存储在本机正式数据源中，不要求互联网。

## Windows 构建

在 Windows 10/11 x64 构建机中：

1. `windows\Setup_CareerOS_Windows.cmd`
2. `windows\Build_Portable_StepIn.cmd`
3. 产物必须通过 `StepIn.exe --self-test`
4. 如需安装器，再运行 `windows\Build_StepIn_Installer.cmd`

目标产物：

- `release\StepIn-Portable-Windows-x64-v1.9.0.zip`
- `release\StepIn-Setup-v1.9.0.exe`

## 离线行为

- 基础 8 步全部可在无互联网环境完成。
- 本机 SQLite 是正式状态源。
- Service Worker/IndexedDB 只保护页面壳和低风险草稿。
- 没有云模型时继续使用规则提示。
- 如已安装并提前下载 Ollama 模型，可使用本机生成式提示。
- 正式版本提交、教师反馈、验证状态不通过浏览器离线队列猜测。

## 数据

程序目录和用户数据目录分离。升级前自动备份逻辑沿用 v1.8；Foundation 状态、Evidence、Artifact、附件与数据库一起受本机备份机制保护。

## 发行 Gate

Linux 构建环境不能宣称 Windows EXE/Installer 已完成认证。最终必须在 Windows 真机验证：首次安装、Foundation 8 步、断网重启、表达、小项目、3 次桥接探索、备份恢复、升级覆盖以及 WebView2/Ollama 可选离线组件。
