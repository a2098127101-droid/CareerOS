# CareerOS v1.5.0-rc1 · Domain Intelligence

CareerOS is an evidence-grounded career intelligence platform. v1.5 promotes the core chain **Claim → Capability → Job Requirement → Gap** into persistent, versioned, explainable and auditable server-side domain entities.

> Release status: internal Beta / GitHub-ready source release. Domain Intelligence is implemented and regression-tested. Production infrastructure, calibrated assessment methodology and standard-browser staging certification remain separate release gates.

## 中文介绍：CareerOS Agent

CareerOS 是面向高校职规赛与学生职业发展的 AI-native Agent 操作系统。它不是单一聊天机器人，而是由工作流编排器协调多个专业 Agent，在持续保存学生画像、事实证据、任务进度和作品版本的基础上，完成职业探索、赛道建议、岗位匹配、能力差距分析、作品生成、严格评审、迭代修订和教师协同指导。

核心 Agent 包括：

- **Profile Agent**：从学生主动提供的材料中提取结构化画像，不自动虚构个人经历。
- **Coach Agent**：结合十阶段职业规划工作流，识别当前任务并驱动下一步行动。
- **Writer Agent**：基于学生 Evidence、赛事规则和岗位要求生成简历、生涯发展报告等 Artifact。
- **Reviewer Agent**：按照结构化 Rubric 提取证据、识别问题并给出可解释评分。
- **Critic Agent**：独立质疑评分、论证与证据链，降低自评偏差。
- **Revision Agent**：综合评审、教师反馈和新增证据生成新版本，保留历史版本而不覆盖旧稿。

系统通过 Multi-Model Gateway 为不同 Agent 独立配置 OpenAI、DeepSeek、Anthropic Claude、Google Gemini 或 OpenAI-Compatible 模型，并支持 Primary/Fallback 路由。知识层严格区分学生个人 Evidence、赛事与学校文档 RAG、结构化岗位数据，避免把外部岗位要求误写成学生已具备的能力。学生端采用 Chat-first Workspace，教师端采用 Attention-first AI Operations Workspace，管理端负责模型路由、知识投喂、调用统计和安全配置。

当前版本属于内部 Beta 与可验证源码版本。未提供真实模型凭据时使用明确标注的 Demo/降级能力；确定性评分是证据覆盖指标，不是心理测量、职业资格认证或岗位表现预测。

## What v1.5 adds

- First-class persistent claims and claim versions.
- Versioned capability definitions and capability assessment history.
- Claim ↔ Evidence and Claim ↔ Capability relations.
- Versioned job-requirement snapshots and Requirement ↔ Capability mappings.
- Versioned career gaps with optimistic locking and lifecycle status.
- Potential score versus verified score, with contribution-level explanations.
- Domain audit events for create, update, recompute, mapping and status changes.
- SQLite and SQLAlchemy/PostgreSQL repository parity.
- Canonical `/api/domain/v1` API and Unified H5 consumption.
- Evidence Trust lifecycle retained: self-reported evidence is not treated as verified evidence.

## Quick start

### Windows

1. Extract the repository.
2. Double-click `OPEN_CareerOS.cmd`.
3. Open the URL shown by the launcher.

### Python

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Default local demo accounts are documented in `.env.example`. Never enable demo seeding in production.

## Domain Intelligence API

```text
POST  /api/domain/v1/recompute
GET   /api/domain/v1/snapshot
GET   /api/domain/v1/claims
PATCH /api/domain/v1/claims/{claim_id}
GET   /api/domain/v1/claims/{claim_id}/versions
GET   /api/domain/v1/capabilities
GET   /api/domain/v1/capabilities/{capability_id}/explain
GET   /api/domain/v1/capabilities/{capability_id}/versions
GET   /api/domain/v1/requirements
GET   /api/domain/v1/requirements/{requirement_id}/versions
GET   /api/domain/v1/gaps
PATCH /api/domain/v1/gaps/{gap_id}
GET   /api/domain/v1/gaps/{gap_id}/versions
GET   /api/domain/v1/audit
```

## Validation

- Automated tests: **184/184 passed**
- SQLite migration: **22/22**
- Alembic head: `0012_project_tenant_rls`
- Immutable published-migration guard and upgrade-from-original-0007 test.
- Canonical `/api/v1` compatibility surface with OpenAPI cookie authentication.
- Deterministic Demo retrieval evaluation and disposable staging infrastructure probe.
- Chrome multi-role browser E2E.

Real generation-model, semantic Embedding and remote Reranker calls remain
environment-dependent gates and were not tested without credentials.

## Important boundaries

The deterministic v1.5 score is an explainable evidence-coverage indicator. It is **not** a psychometric test, professional certification or validated predictor of job performance. See `REMAINING_GAPS_v1.5.md` and `PRODUCTION_READINESS_v1.5.md`.

## Documentation

- `ARCHITECTURE_v1.5.md`
- `DOMAIN_INTELLIGENCE_MODEL.md`
- `API_DOMAIN_INTELLIGENCE_GUIDE.md`
- `MIGRATION_GUIDE_v1.5.md`
- `TEST_REPORT_v1.5.md`
- `PRODUCTION_READINESS_v1.5.md`
- `REMAINING_GAPS_v1.5.md`
- `GITHUB_UPLOAD_GUIDE.md`
- `CHANGELOG_v1.5.md`
- `RELEASE_NOTES_v1.5.md`
- `SOURCE_PROVENANCE_v1.5.md`
