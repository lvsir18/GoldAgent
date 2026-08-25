# Security Policy

## Reporting a vulnerability

请不要在公开 Issue 中披露可利用漏洞、真实 API Key、访问令牌或用户数据。请通过仓库所有者在 GitHub Profile 中提供的私密联系方式报告，并包含受影响版本、复现步骤、潜在影响和建议修复方式（如有）。

在问题修复并完成披露协调前，请勿公开漏洞细节。

## Secrets and local data

- 从 `.env.example` 创建 `.env`，真实密钥不得提交到 Git。
- 如果密钥曾出现在 Commit、日志、终端录屏或截图中，应立即在服务商控制台轮换；删除文件不能替代密钥轮换。
- `data/`、`logs/`、`reports/` 和本地数据库属于运行产物，不应进入公开仓库。
- 生产环境必须关闭 Demo 配置，使用高强度 `JWT_SECRET_KEY`、PostgreSQL 和明确的 CORS Origin。

## Supported versions

当前仅维护 `main` 分支的最新版本。

