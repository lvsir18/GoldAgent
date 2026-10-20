# 发布与恢复验收

本轮（2026-10-21）已执行备份归档验证和独立 PostgreSQL 测试库实际恢复，主要表计数一致；没有覆盖当前业务库。后端 33 项、前端 7 项、Edge E2E 4 项测试通过，前后端生产镜像构建通过。真实外部 LLM/Embedding 效果、公网安全和负载能力仍需单独验收。

## 更新前

1. 使用 Node 22 / Python 3.12；本地 `.env` 不进入 Git。
2. 运行后端测试、前端类型检查与单测；运行端到端测试。
3. 在项目根目录执行 `powershell -File scripts/backup.ps1`。检查 `data/backups` 中新建归档；备份包含私人资料，应加密保存到独立介质。
4. 保存当前 Git commit 和可回退镜像标签。不要执行 `docker compose down -v`，这会删除数据库卷。

## 构建与启动

```powershell
docker compose build backend frontend
docker compose up -d
docker compose ps
Invoke-RestMethod http://127.0.0.1:8080/health
Invoke-RestMethod http://127.0.0.1:8080/ready
```

`/ready` 只核查数据库、Checkpointer 和必要配置；market_provider=not_probed 不代表外部源异常，也不证明外部源连通。验收行情应检查实际行情响应时间和来源；验收 LLM 应使用无私人数据的测试账号，显式控制费用。

当前 Compose 是本地使用配置，默认 Demo 身份和开发密码不能直接公网发布。正式部署需关闭 Demo、使用独立用户、设置强密码/JWT 密钥、限制后端网络入口并配置 TLS；不得直接把示例配置当成生产安全配置。

## 数据库迁移

新生产数据库应先执行 `alembic upgrade head`，再运行服务。本轮没有增加业务表或列；新增研究元数据使用现有 JSON 字段。

注意：历史 Demo 通过 create_all 建表，不一定有 Alembic 版本记录。不要对这种已有库盲目 upgrade 或 stamp。先备份，核对实际 schema 与迁移版本，再由维护者确定基线。当前 Demo 启动仍保留 create_all 兼容行为，不宣称已完成生产迁移接管。

## 恢复演练（独立库）

先复制备份进 PostgreSQL 容器，使用新建测试库恢复；不要覆盖正在使用的 goldagent 库。

```powershell
docker compose cp data/backups/你的备份.dump postgres:/tmp/restore-test.dump
docker compose exec -T postgres createdb -U goldagent goldagent_restore_check
docker compose exec -T postgres pg_restore -U goldagent --no-owner -d goldagent_restore_check /tmp/restore-test.dump
docker compose exec -T postgres psql -U goldagent -d goldagent_restore_check -c "SELECT count(*) FROM users;"
```

仅检查 `pg_restore --list` 能证明归档可读，不能等价于完整恢复演练。确认数据与表结构后再安排正式恢复；旧数据库和备份保留到业务验收完成，不自动删除。

## 上线前必须补齐

- 强凭据、租户隔离、注册策略、上传限额、请求限额和备份权限复核。
- 真实中文 Embedding 的相关/无关检索验收；模型变更后重新索引。
- 登录 → 对话 → 停止/重试 → 证据 → 报告 → 认证下载的真实链路验收。
- 迁移、独立库恢复、重启与断连测试，按目标规模进行负载测试。
- 禁止将 `.env`、备份、真实会话、持仓、原始内部体验截图提交到公开仓库。
