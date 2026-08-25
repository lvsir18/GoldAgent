# Contributing to GoldAgent

感谢你对 GoldAgent 的关注。提交变更前，请先创建 Issue 描述问题、使用场景和预期行为。

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env

Set-Location frontend
npm ci
```

真实 API Key 只能放在 `.env`，不得写入代码、测试、Issue、日志或截图。

## Pull request checklist

- 变更保持 `API → Agent/Service → Provider` 分层，不在 Router 或 Prompt 中复制业务算法。
- 新工具包含 Pydantic 输入 Schema、超时边界、明确失败语义和相应测试。
- 金融数据包含来源与时间信息；不得增加虚构行情或新闻 fallback。
- 后端运行 `python -m pytest`。
- 前端运行 `npm run typecheck`、`npm test`；交互变更补充 E2E。
- 更新相关 README、API 或迁移文档。

## Commit style

推荐使用简洁的 Conventional Commit：

```text
feat(agent): add macro indicator tool
fix(news): preserve rolling freshness window
docs(readme): clarify Docker setup
```

