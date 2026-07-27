# CareerOS v1.5 · Domain Intelligence

CareerOS 是一套以证据链为基础的职业智能平台。v1.5 将核心链路 **Claim（主张）→ Capability（能力）→ Job Requirement（岗位要求）→ Gap（差距）** 升级为服务器端独立持久化、版本化、可解释、可审计的领域模型。

> 当前定位：内部 Beta / 可上传 GitHub 的完整源码版本。领域模型已经实现并完成回归测试；生产基础设施认证、能力测量校准和标准浏览器 staging 验证仍属于独立上线门槛。

## v1.5 核心能力

- Claim 独立实体与版本历史；
- Capability 定义、Assessment 与 Assessment Version；
- Claim ↔ Evidence、Claim ↔ Capability 关系；
- 岗位要求快照、Requirement Version 与 Requirement ↔ Capability 映射；
- Gap 独立实体、版本历史、状态流转和乐观锁；
- Potential Score 与 Verified Score 分离；
- 每项分数可追溯到具体 Claim、Evidence 和贡献权重；
- 重计算、映射、更新和状态变化均写入 Domain Audit Event；
- SQLite 与 SQLAlchemy/PostgreSQL Repository 对齐；
- `/api/domain/v1` Canonical API；
- H5 API 模式展示服务器权威能力画像、岗位要求映射和差距解释。

## 快速启动

Windows 解压后双击：

```text
OPEN_CareerOS.cmd
```

或使用 Python：

```bash
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## 验证结果

- 测试文件：36 个；
- 自动化测试：**153/153 通过**；
- SQLite Migration：**21/21**；
- Alembic Head：`0009_domain_intelligence_v15`；
- 独立 H5 与服务器静态副本一致；
- 所有内联 JavaScript 已通过语法检查。

## 必须注意

v1.5 的确定性分数属于“可解释的证据覆盖指标”，不能宣传为心理测量、职业资格认证或岗位绩效预测工具。生产上线前请阅读：

- `PRODUCTION_READINESS_v1.5.md`
- `REMAINING_GAPS_v1.5.md`
- `SOURCE_PROVENANCE_v1.5.md`

- `RELEASE_NOTES_v1.5.md`
