# GoldAgent Migration Plan

> 全部阶段已执行完成。本文保留为实施记录；Phase 14 的最终门禁和删除结果见
> `docs/legacy_compatibility.md`。

本计划以可运行、可验证、可回滚为约束。Phase 0 只新增审计文档；Phase 1 必须获得确认后开始。

## Delivery Rules

- 新实现与 legacy 并行，直到功能覆盖和测试通过。
- 外部 API 在单元/API/Agent 测试中默认 mock。
- 每个任务完成后更新实现状态、测试记录和已知风险。
- 不把推导或 mock 数据标记为实时直接行情。
- 数据库、Agent、前端分别做小步 vertical slice，不制造一次性大爆炸迁移。

## P0 Critical

### P0.1 Secret and request-boundary hardening

- **Goal**：移除明文 secret，阻断 session 路径越界，建立安全默认值。
- **Files**：`config.yaml`、`.env.example`、`.gitignore`、`src/chat_service.py`、`web_app.py`、security tests。
- **Dependencies**：用户撤销并重发已暴露 Key；不依赖外部服务。
- **Risk**：环境变量重命名可能让现有启动失败。
- **Estimated Scope**：Small–Medium。
- **Test Strategy**：secret scan；合法/非法 session ID；路径 resolve 边界；CORS 配置测试；旧环境变量兼容测试。
- **Acceptance Criteria**：仓库无明文 Key；配置缺 Key 时安全降级；任意 session ID 不能访问会话目录外文件；生产 CORS 不允许 wildcard。

### P0.2 Typed configuration and packaging baseline

- **Goal**：消除重复 YAML，建立 Pydantic Settings、启动验证和 `pyproject.toml`。
- **Files**：`backend/app/core/settings.py` 或渐进式 `src/settings.py`、`config.yaml`、`pyproject.toml`、`.env.example`。
- **Dependencies**：Pydantic Settings；先定义 legacy config adapter。
- **Risk**：旧代码依赖点路径和隐式默认值。
- **Estimated Scope**：Medium。
- **Test Strategy**：重复键、类型错误、URL、范围、环境覆盖、legacy adapter 单测。
- **Acceptance Criteria**：重复键 fail-fast；有效配置只有一个指标段；LLM provider/model/key 命名一致；CLI/Web 仍可导入。

### P0.3 Test harness and CI-ready checks

- **Goal**：建立 pytest 基线和无网络测试规范。
- **Files**：`tests/`、`pyproject.toml`、fixtures、后续 CI workflow。
- **Dependencies**：pytest、pytest-asyncio、httpx；外部 Provider fake。
- **Risk**：旧模块 import 时初始化全局 service，影响隔离。
- **Estimated Scope**：Medium。
- **Test Strategy**：unit/import/API smoke；禁止网络 fixture；coverage 初始基线。
- **Acceptance Criteria**：单命令运行测试；默认不访问付费 API；语法、import、config 和 health smoke 进入回归。

### P0.4 Market data correctness and provenance

- **Goal**：修复汇率 fallback、缺失值和溢价语义，建立统一 provenance schema。
- **Files**：market schemas/provider/service、legacy `data_fetcher.py`/`data_processor.py` adapter、tests。
- **Dependencies**：P0.2；确定真实国际行情 provider 策略。
- **Risk**：数值变化会改变历史报告结果。
- **Estimated Scope**：Large。
- **Test Strategy**：单位换算、fallback、direct/derived metadata、缺失 OHLC、日期对齐 tolerance、golden datasets。
- **Acceptance Criteria**：所有市场结果含完整 metadata；derived 不冒充 direct；fallback 无 100 倍错误；premium 只在有效独立来源上计算或明确标注限制。

## P1 Core Agent

### P1.1 Provider and Service extraction

- **Goal**：把 Market、News、Technical、Forecast 从入口/God Object 中解耦。
- **Files**：`backend/app/providers/`、`backend/app/services/`、schemas、legacy adapters。
- **Dependencies**：P0.2–P0.4。
- **Risk**：迁移期重复调用或结果结构变化。
- **Estimated Scope**：Large。
- **Test Strategy**：mock provider service unit tests；legacy/new parity fixtures；timeout/error mapping。
- **Acceptance Criteria**：业务 Service 不依赖 FastAPI/LangGraph；Provider 可替换；网络 I/O 使用 async httpx + bounded retry。

### P1.2 Provider-neutral LLM Gateway

- **Goal**：将 LLM 直连从 `AgentBrain` 移入支持 chat/stream/tools/structured output 的 Gateway。
- **Files**：`backend/app/llm/`、provider adapters、settings、tests。
- **Dependencies**：P0.2；确认 MiMo base URL 与 tool-calling capability。
- **Risk**：不同 OpenAI-compatible provider 的流式/tool schema 不完全一致。
- **Estimated Scope**：Medium–Large。
- **Test Strategy**：fake transport、retry/timeout、stream parsing、tool calls、structured output、capability flags。
- **Acceptance Criteria**：Agent 业务无硬编码 URL/Key；默认配置为 `mimo/mimo-v2.5-pro`；缺少能力时明确失败或选择受控 fallback。

### P1.3 Structured Tool registry

- **Goal**：为高价值 Service 建立 Pydantic 输入/输出的 Structured Tools。
- **Files**：`backend/app/tools/market|technical|news|forecast|portfolio|backtest|rag|report`、registry、tests。
- **Dependencies**：P1.1、P1.2。
- **Risk**：Tool 返回过大、错误语义不统一。
- **Estimated Scope**：Large。
- **Test Strategy**：schema validation、timeout、retry、metadata、error type、serialization、DataFrame leakage checks。
- **Acceptance Criteria**：每个 Tool 可单测；结果含 source/freshness/reference；不把大 DataFrame 送给 LLM。

### P1.4 LangGraph supervisor runtime

- **Goal**：实现 State、Supervisor、Tool loop、Verification、Guardrail、Save Memory 和 max steps。
- **Files**：`backend/app/agent/`、graph nodes/prompts/guardrails、agent tests。
- **Dependencies**：P1.2、P1.3；先使用测试 checkpointer。
- **Risk**：循环失控、provider 工具调用兼容性、隐式推理泄露。
- **Estimated Scope**：Large。
- **Test Strategy**：tool selection、连续调用、max steps、tool failure、conflict verification、stale data、unsafe advice、stream events。
- **Acceptance Criteria**：LLM 真正选择工具；observation 返回 graph；有明确终止条件；verification/guardrail 可独立测试；SSE 不暴露 Chain-of-Thought。

### P1.5 Backtest and forecast evaluation

- **Goal**：实现无前视偏差的回测及统一 forecast evaluation。
- **Files**：services/models/schemas、CLI adapter、unit tests。
- **Dependencies**：P1.1；P0.4 数据契约。
- **Risk**：错误年化、成本时点或 signal shift 会产生误导结果。
- **Estimated Scope**：Large。
- **Test Strategy**：手算小样本、zero trade、drawdown、cost、benchmark、signal shift；rolling forecast fixtures。
- **Acceptance Criteria**：回测返回全部规定 KPI、交易和 equity/drawdown 序列；预测返回 MAE/RMSE/MAPE/direction accuracy；heuristic score 不再称 probability/confidence interval。

### P1.6 Persistence foundation

- **Goal**：建立 SQLAlchemy 2、Alembic、PostgreSQL schema、Repository 和 LangGraph persistent checkpoint。
- **Files**：`backend/app/db/`、models/repositories、migrations、JSON import script、integration tests。
- **Dependencies**：P0.2、P0.3；PostgreSQL test service。
- **Risk**：历史 JSON 迁移、事务/租户边界和 checkpoint schema。
- **Estimated Scope**：Large。
- **Test Strategy**：migration up/down、repository CRUD、user isolation、JSON idempotent import、resume graph state。
- **Acceptance Criteria**：session/message/profile/run/tool calls 持久化；可 resume；legacy JSON 可校验迁移；CLI 不被数据库强制阻断。

## P2 Productization

### P2.1 Versioned FastAPI API and SSE contract

- **Goal**：建立分层 Router、统一 envelope/error、资源 API 和标准 Agent SSE。
- **Files**：`backend/app/api/`、schemas、middleware、contract/API tests。
- **Dependencies**：P1.1、P1.4、P1.6。
- **Risk**：旧前端接口兼容。
- **Estimated Scope**：Large。
- **Test Strategy**：FastAPI/httpx API tests、OpenAPI schema snapshot、SSE event ordering、legacy adapter tests。
- **Acceptance Criteria**：`/api/v1` 资源接口可用；业务逻辑不在 Router；旧 API 保留并标记 deprecated；`/health`、`/ready` 不触发付费 API。

### P2.2 Next.js frontend foundation and Dashboard slice

- **Goal**：新建 Next.js/TypeScript shell、design tokens、typed API client，并完成真实 Dashboard。
- **Files**：`frontend/` app/components/features/services/stores/tests。
- **Dependencies**：P2.1 market API。
- **Risk**：Node 工具链和图表体积；接口未稳定导致返工。
- **Estimated Scope**：Large。
- **Test Strategy**：typecheck、lint、Vitest/RTL、Playwright Dashboard；loading/error/empty/stale fixtures。
- **Acceptance Criteria**：响应式 shell；K 线/指标/summary 来自真实 API；显示 freshness/source；旧 HTML 未删除。

### P2.3 Agent Chat slice

- **Goal**：迁移核心 Chat，展示 session、标准流式答案、tool status 和 sources。
- **Files**：frontend chat feature、API client、backend run endpoints、E2E tests。
- **Dependencies**：P1.4、P2.1、P2.2。
- **Risk**：SSE 重连和部分失败状态复杂。
- **Estimated Scope**：Large。
- **Test Strategy**：stream parser unit、disconnect/retry、tool event UI、session CRUD E2E、no-CoT assertion。
- **Acceptance Criteria**：创建/切换/重命名/删除 session；显示 tool 名称/状态/耗时/来源；回答 source 可展开；partial/error 明确。

### P2.4 Analysis, Forecast, Portfolio and Backtest slices

- **Goal**：按后端 readiness 依次交付四个真实业务页面。
- **Files**：对应 frontend features/components/routes 与 API endpoints/tests。
- **Dependencies**：P1.5、P1.6、P2.1。
- **Risk**：页面并行造成重复 chart/view model。
- **Estimated Scope**：XL，拆为四个可独立发布任务。
- **Test Strategy**：每页 unit + contract + Playwright；回测 job state；预测免责声明；portfolio user isolation。
- **Acceptance Criteria**：所有按钮有真实 API；结构化指标/曲线/交易表可追踪来源；不执行自动交易。

### P2.5 Reports, News, Settings and Knowledge/RAG

- **Goal**：补齐资产管理、实时新闻、设置和长期知识页面；接 pgvector ingestion/retrieval。
- **Files**：backend RAG/report/news/user modules、migrations、frontend routes、integration/E2E tests。
- **Dependencies**：P1.6、P2.1、Embedding provider。
- **Risk**：文档解析安全、向量隔离、耗时 ingestion。
- **Estimated Scope**：XL，可拆四项。
- **Test Strategy**：PDF/MD/TXT fixtures、chunk metadata、tenant filters、source citations、job failures、report download authorization。
- **Acceptance Criteria**：实时搜索与 RAG 明确分离；文档可上传/检索/删除；source 可追踪；API Key 不返回前端。

### P2.6 Documentation and legacy compatibility

- **Goal**：让 README、OpenAPI、架构和实际功能同步。
- **Files**：README、docs、legacy adapters、notebook migration/deprecation note。
- **Dependencies**：随每个 slice 更新。
- **Risk**：提前宣传未实现能力。
- **Estimated Scope**：持续任务。
- **Test Strategy**：文档命令 smoke、link check、OpenAPI diff。
- **Acceptance Criteria**：README 只声明已有能力；Mermaid、启动、测试和 API 示例可复现。

## P3 Production Hardening

### P3.1 Authentication, authorization and rate limiting

- **Goal**：JWT access/refresh、用户隔离、demo mode 和高成本接口限流。
- **Files**：auth middleware/services/models、API dependencies、frontend auth、security tests。
- **Dependencies**：P1.6、P2.1。
- **Risk**：token 存储、刷新竞态、demo/production 配置混淆。
- **Estimated Scope**：Large。
- **Test Strategy**：ownership matrix、expired/refresh token、rate limit、anonymous denial、demo mode。
- **Acceptance Criteria**：生产模式无匿名 portfolio/session/knowledge；限流覆盖 chat/forecast/backtest/refresh/upload；安全 CORS。

### P3.2 Observability and evaluation

- **Goal**：结构化 run/tool/LLM 追踪和可重复 Agent regression。
- **Files**：observability、evals datasets/evaluators/runners/reports、dashboards/docs。
- **Dependencies**：P1.4、P2.1。
- **Risk**：日志泄露 PII/Prompt，LLM judge 不稳定。
- **Estimated Scope**：Large。
- **Test Strategy**：redaction、trace completeness、deterministic evaluators、recorded model fixtures、baseline compare。
- **Acceptance Criteria**：run_id/user_id/session_id 全链路；记录 node/tool duration、retry、source、status；50–100 场景覆盖 task/tool/factual/source/safety/latency/cost。

### P3.3 MCP server

- **Goal**：暴露少量高价值 Gold Market MCP tools，同时保留本地调用。
- **Files**：`mcp_servers/gold_market/`、adapter、contract tests、docs。
- **Dependencies**：P1.1、P1.3。
- **Risk**：无价值网络边界、重复 schema 和认证。
- **Estimated Scope**：Medium。
- **Test Strategy**：MCP discovery/invocation、schema parity、timeout/error、auth boundary。
- **Acceptance Criteria**：至少 price/history/exchange-rate/indicators 可通过 MCP；Agent 可加载；业务逻辑仍在 Service。

### P3.4 Docker, CI and deployment readiness

- **Goal**：一条命令启动 frontend/backend/postgres，并建立 CI。
- **Files**：Dockerfiles、compose、health checks、CI workflows、deployment docs。
- **Dependencies**：P2 主链路完成。
- **Risk**：镜像体积、AkShare/TA native dependency、startup ordering。
- **Estimated Scope**：Medium–Large。
- **Test Strategy**：container build、compose smoke、migration、health/ready、frontend E2E。
- **Acceptance Criteria**：`docker compose up` 可启动 Demo；secret 不进镜像；health/ready 正确；CI 运行 backend/frontend/contract tests。

### P3.5 Legacy cutover and removal

- **Goal**：在完整覆盖后删除旧 routing、JSON persistence 和单 HTML 核心入口。
- **Files**：legacy modules/adapters/docs。
- **Dependencies**：新 API/Web/DB 全部通过回归，至少一个发布周期。
- **Risk**：隐藏用户流程或历史数据丢失。
- **Estimated Scope**：Medium。
- **Test Strategy**：feature parity checklist、数据迁移计数、CLI/API/E2E 回归、rollback rehearsal。
- **Acceptance Criteria**：无 legacy 调用者；历史数据迁移完成；回滚路径验证；删除后 README/依赖同步。

## Recommended Execution Order

```text
P0.1 Security
  → P0.2 Config
  → P0.3 Tests
  → P0.4 Data correctness
  → P1.1 Services/Providers
  → P1.2 LLM Gateway
  → P1.3 Structured Tools
  → P1.4 LangGraph
  → P1.5 Backtest/Forecast Eval
  → P1.6 Persistence
  → P2.1 API v1
  → P2.2 Dashboard
  → P2.3 Chat
  → P2.4 Domain Pages
  → P2.5 RAG/Remaining Pages
  → P3 Hardening
  → Legacy Removal
```

## Phase Gates

| Gate | Must be true before proceeding |
|---|---|
| Enter P1 | Secrets handled、typed config、tests runnable、data contract agreed |
| Enter LangGraph | Service/Provider and fake LLM are independently tested |
| Enter Frontend | `/api/v1` schema stable and contract tests pass |
| Enter RAG UI | PostgreSQL/pgvector migration and tenant filter tests pass |
| Production claim | Auth/rate limit/observability/evals/Docker/CI pass |
| Remove legacy | Feature parity、migration、E2E、rollback all verified |
