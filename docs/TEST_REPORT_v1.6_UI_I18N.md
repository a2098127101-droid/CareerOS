# CareerOS v1.6 UI、交互与国际化回归报告

## 范围

- 用户端：方案提交、Artifact 版本历史、版本恢复/差异入口、评分雷达图、模拟面试、任务重开。
- 顾问端：真实 Reviewer 调用、方案推荐、顾问反馈、任务状态、进度钻取。
- 系统端：工作流模板、成果模板、组织角色与账户状态分配。
- 全局：简体中文 / English 无刷新切换、语言偏好持久化、表单与常见错误文案。
- 保留：Model Gateway、RAG、Structured Job Store、Evidence Ledger/Graph、Artifact Versioning、Teacher Feedback、AI Task Center 与十阶段工作流。

## 自动化结果

- Python compileall：通过。
- JavaScript syntax：`i18n.js`、`student-workspace.js`、`teacher-workspace.js`、`admin-extension.js` 通过。
- pytest：**167 passed，1 个第三方 Starlette TestClient 弃用警告**。
- `git diff --check`：通过。
- `requirements.lock` 相对线上基线未改变；服务器外部镜像源超时时，可使用 `Dockerfile.incremental` 从既有验证镜像复制同依赖版本源码。

## 浏览器控制到 API 验证

| 端 | 可见控件 | 事件/接口 | 浏览器观察 |
|---|---|---|---|
| 登录 | 登录 | `POST /api/auth/login` | 用户、顾问、学校管理员均进入对应工作区 |
| 全局 | 地球语言入口 | `CareerI18n.setLocale` + LocalStorage | 不刷新切换为 English，刷新后仍保持 |
| 用户 | 提交并创建版本 | `POST /api/workspace/v1/artifacts` | Toast 成功，目录即时出现 V1 |
| 用户 | 版本节点 | `GET /api/workspace/v1/artifacts/{id}/versions` | 显示当前/归档时间轴 |
| 用户 | 成果评审 | `POST /api/review` | 展示渐变雷达图与红色丢分项 |
| 顾问 | 生成方案推荐 | `POST /api/workspace/v1/ai/coach` | 无模型路由时明确错误 Toast，不伪造建议 |
| 系统 | 创建工作流模板 | `POST /api/admin/templates/workflows` | Toast 成功，目录即时出现模板 |
| 系统 | 保存权限 | `PATCH /api/admin/users/{id}/role` 与 `/status` | Toast 成功，列表重新加载 |

## 明确边界

- 本地 Demo Reviewer 的 62/100 是明确标注的 Demo 结构化评审，不代表外部模型质量。
- 顾问方案推荐在未配置真实模型路由时返回真实错误，不做静态 Mock。
- 外部 OpenAI、DeepSeek、Claude、Gemini 的真实密钥调用未在本轮本地测试中执行。
- Windows、Firefox、Safari 的本轮新增交互尚未逐浏览器复测；现有静态兼容结构未删除。
- Production certification 仍需目标基础设施、真实模型与业务 E2E 证据，本报告不替代上线认证。
