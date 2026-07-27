# 将 CareerOS v1.5 上传到 GitHub

交付压缩包解压后只有一个项目根目录：

```text
CareerOS-main_v1.5_domain-intelligence/
```

## 推荐方式：Git 命令行

进入解压后的项目根目录：

```bash
git init
git add .
git commit -m "Release CareerOS v1.5 Domain Intelligence"
git branch -M main
git remote add origin https://github.com/<YOUR_ACCOUNT>/<YOUR_REPOSITORY>.git
git push -u origin main
```

## GitHub 网页或 GitHub Desktop

1. 在 GitHub 创建空仓库，不勾选自动生成 README、License 或 `.gitignore`。
2. 解压交付包。
3. 使用 GitHub Desktop 添加本地仓库，或在网页端上传项目根目录内的文件。
4. 确认 `.github/workflows/ci.yml` 已上传。
5. 推送后打开 **Actions**，检查 `static-audit` 和 6 个 `pytest-groups` Job 是否全部通过。

## 上传前本地检查

```bash
python -m compileall -q app scripts tests alembic
python scripts/audit_database_access.py
python scripts/audit_repository_contract.py
pytest -q
alembic -c alembic.ini heads
```

若本地整套 `pytest` 因历史进程级配置或子进程清理问题不退出，可按 GitHub CI 的确定性分组运行：

```bash
for i in 0 1 2 3 4 5; do
  FILES="$(python scripts/select_test_group.py --groups 6 --index $i)"
  pytest -q ${FILES}
done
```

## 不得上传

- `.env`；
- API Key、OAuth Secret、数据库密码；
- 本地 SQLite 业务数据；
- `data/email_outbox.jsonl`、上传文件和日志；
- `__pycache__`、`.pytest_cache`、`.coverage`；
- 生产证书或认证结果文件。

项目 `.gitignore` 已覆盖常见本地产物，但提交前仍需执行：

```bash
git status
```

进行人工复核。

## 首次发布建议

创建 GitHub Release：

- Tag：`v1.5.0`
- Title：`CareerOS v1.5 Domain Intelligence`
- Release notes：使用 `RELEASE_NOTES_v1.5.md`
- 附件：可上传本次交付 ZIP 和 SHA-256 文件。
