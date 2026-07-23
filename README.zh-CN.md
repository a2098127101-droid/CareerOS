# CareerOS v1.0-beta1

[English](README.md) | [简体中文](README.zh-CN.md)

**Business Runtime Verification Candidate**

> **预发布提示：** 本仓库是业务运行验证候选版，不是生产就绪或 Runtime Verified 版本。

CareerOS 是一个面向职业发展与人才智能场景的 AI 原生平台，将多 Agent 协作、证据约束内容生成、Hybrid RAG、人才与岗位分析、多租户治理及运行时认证整合在同一套系统中。

## 当前状态

| 层级 | 状态 | 说明 |
| --- | --- | --- |
| 离线 Showcase | 可用 | 单个匿名静态 HTML；不需要后端、数据库、支付服务或 API Key |
| 本地兼容运行时 | 已实现 | 默认使用 SQLite、本地私有文件、内存状态和进程内后台任务 |
| 随包测试报告 | 记录为通过 | `docs/TEST_REPORT_v1.0-beta1.md` 记录原始分组基线 |
| GitHub Actions 复验 | 132/132 通过 | Python 3.11.9、哈希锁定依赖、32 个隔离测试文件 |
| Staging 认证框架 | 已实现 | PostgreSQL/pgvector、Redis、MinIO、API、独立 Worker 与 Certifier 拓扑 |
| 真实外部运行时认证 | 尚未验证 | 未完成真实 PostgreSQL、Redis、MinIO、语义嵌入和生成模型认证 |
| 商业生产就绪 | 不作声明 | 大规模并发、真实支付、企业 SSO 与完整可观测性摄取不在当前认证范围内 |

P0 稳定化已修复 FastAPI 路由测试的内部结构依赖、Windows 快照
CRLF/LF 字节差异和 pytest 9 通过数统计，并加入可复现依赖锁。对应
[GitHub Actions 运行](https://github.com/a2098127101-droid/CareerOS/actions/runs/29988693142)
已通过 132/132。

本仓库和 `v1.0-beta1` Release 仍按 Pre-release 发布，因为真实
PostgreSQL、Redis、MinIO、语义嵌入、生成模型及完整 staging 认证尚未完成。

## 两种交付方式

### Showcase Edition

- 入口：`CareerOS_H5_Showcase.html`
- 可直接在现代浏览器中打开
- 使用通用匿名演示数据
- 不连接真实 API、数据库、支付服务或模型凭据

### Production-oriented Runtime

- FastAPI 应用与管理界面
- 身份认证、RBAC 与多租户隔离
- 多 Agent 业务工作流与多模型网关
- Hybrid RAG、知识管理与 Evidence Graph
- Artifact 版本、审阅、修订与追溯
- Job Intelligence、隐私生命周期与商业化基础
- PostgreSQL/pgvector、Redis 与 S3 兼容存储适配
- 签名的 Runtime Certification 与 Business E2E Certification

“Production-oriented” 只表示系统按生产架构和验证门槛设计，不表示当前包已在真实生产或 staging 基础设施上通过认证。

## v1.0-beta1 重点

### 业务端到端认证

```text
已认证参与者
→ Session
→ Profile Agent
→ Coach
→ 私有文件上传
→ Writer / Artifact V1
→ Reviewer
→ Evidence Verification
→ Critic + Revision / Artifact V2
→ Artifact Trace
→ 跨租户攻击检查
→ LLM 使用记录证明
```

认证身份使用随机临时凭据，并在清理阶段去标识化或归档。确定性演示回退不能替代真实模型使用证明。

### Semantic RAG 门槛

- 当前资料优先于过期资料；
- 权威来源优先于非权威来源；
- 认证案例满足 `Recall@5 = 1`；
- 不发生跨租户知识泄漏；
- 使用真实语义嵌入提供者，而不是离线 `local_hash` 回退。

### 独立 Worker 与恢复

- Redis 任务必须由独立 Worker 进程或容器消费；
- Certifier 不在自身进程执行探测任务；
- 检查过期 Worker 租约恢复、重新入队与独立执行；
- 记录 Worker 身份、心跳、运行集合和死信基础信息。

### 私有对象验证

```text
PUT
→ SDK GET + SHA256
→ 预签名 URL
→ 实际 HTTP GET + SHA256
→ DELETE
```

### 迁移与恢复演练

- SQLite 代表性夹具 → JSONL 快照 → 临时 PostgreSQL 数据库 → Alembic → 导入与 Repository 回读；
- 临时 PostgreSQL schema → `pg_dump` → 删除 → `pg_restore` → 完整性回读。

这些演练只能在 staging 或一次性资源上执行，不应针对生产数据库运行。

## 快速开始

### 离线 Showcase

直接打开：

```text
CareerOS_H5_Showcase.html
```

### Windows 本地运行

双击：

```text
OPEN_CareerOS.cmd
```

### 跨平台开发运行

```bash
python -m venv .venv
pip install --require-hashes -r requirements.lock
python -m uvicorn app.main:app --reload
```

启动后可通过 `/admin` 配置产品预设、模型提供者、知识、结构化岗位和商业化基础设置。

## Staging 认证

```bash
cd deploy
cp .env.staging.example .env.staging
docker compose --env-file .env.staging -f docker-compose.staging.yml up -d --build postgres redis minio minio-init api worker
docker compose --env-file .env.staging -f docker-compose.staging.yml --profile certify run --rm certifier
```

必须先替换全部 `CHANGE_ME`，并配置真实语义嵌入、至少一个真实生成模型、S3 公共签名端点和外部可观测性健康端点。不要提交 `.env.staging`。

生产模式 `/ready` 同时要求有效、未过期且与当前环境绑定的 Runtime Certificate 和 Business E2E Certificate。

## 主要文档

- `deploy/README_BETA1_STAGING.md`
- `docs/V1.0_BETA1_BUSINESS_RUNTIME_VERIFICATION.md`
- `docs/BUSINESS_E2E_CERTIFICATION_v1.0-beta1.md`
- `docs/RUNTIME_CERTIFICATION_GATE_v1.0-beta1.md`
- `docs/MIGRATION_RECOVERY_CERTIFICATION_v1.0-beta1.md`
- `docs/WORKER_RECOVERY_v1.0-beta1.md`
- `docs/TEST_REPORT_v1.0-beta1.md`

## 安全与隐私

- 不要提交 `.env`、`deploy/.env.staging`、运行数据库、认证报告、邮件 outbox 或真实模型凭据；
- 生产使用前应配置高强度 `APP_SECRET_KEY`、私有对象存储、最小权限数据库角色和外部密钥管理；
- 不得在未获明确授权时使用用户数据训练模型；
- 对外部模型调用执行数据最小化，并分离用户证据、顾问指导、外部知识和结构化岗位事实。

## 许可证

本仓库采用 `LICENSE` 中的 CareerOS 专有许可证。源代码公开可见仅用于评估和审阅；未经版权所有者事先书面许可，不授予使用、复制、修改、部署或分发权。本项目不宣称为开源软件。
