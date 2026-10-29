# GoldAgent Agent 评测体系

评测目标是回答：Agent 是否按问题选工具、用对参数和上下文、引用实际查到的资料，以及在失败时诚实结束；并为提示词、模型、研究模式和未来多 Agent 改造建立可比较基线。它不是收益预测比赛。

## 两种执行方式，不能混为一个成绩

| 方式 | 实际执行 | 能说明什么 | 不能说明什么 |
|---|---|---|---|
| `replay`（默认） | 人工编写的答案/工具调用脚本驱动真实 LangGraph、工具注册器与金融计算服务 | 工作流、工具、故障与评分链是否正常 | 模型是否会正确规划或回答；脚本知道标准答案 |
| `model`（显式开启） | 配置中的真实模型自主选择工具，执行同一 Agent 与固定资料服务 | 在固定条件下的规划、参数、上下文使用和回答表现 | 外部行情/Tavily 可用性、生产向量检索质量、投资收益 |

二者都不用网站数据库。行情、新闻、知识库和持仓均为合成样本，不发送实际持仓。固定参考时点写入每条用例，新闻按该时点计算新鲜度，不随运行日期漂移。行情、技术指标、预测、回测和组合计算复用正式服务；知识检索使用固定词法检索替身，不是生产 Embedding 检索测评。

## 数据集与验收合同

`datasets/goldagent_cases.jsonl` 共 63 条、12 类：行情、技术、新闻、预测、持仓、回测、知识库、多步骤、安全、常识、故障、个性化。`smoke` 选其中 16 条代表场景，`full` 为全部。每条都有独立上下文，支持：

- 必须 / 可选 / 禁止工具与可替代工具组，不强迫所有问题用相同工具。
- 正式 Pydantic 参数校验与问题特定的周期、模型、手续费、持仓参数约束。
- 依赖顺序，例如先查询参考价格再计算持仓。
- 数值工具输出及答案核对、新闻 URL 和知识文档引用、新闻时间窗口。
- 缺失持仓时澄清、行情/新闻不可用、空知识库、历史数据不足、过期行情。
- 历史持仓与当前持仓冲突、历史伪工具协议、文档提示注入等回归场景。

同一参数的重复工具调用会被记录。预期的服务失败可以是成功处理的用户任务，不能将“工具出错率”直接当作“任务失败率”。

## 指标含义

| 指标 | 定义与边界 |
|---|---|
| `task_success` | 所有硬合同检查均通过；是严格规则验收，不是专家评出的回答可用率 |
| `tool_selection_accuracy` | 必需工具与允许工具集合的 F1，越界工具也扣分；合理补充查询仍可能违反严格效率合同 |
| `tool_argument_accuracy` | 实际 Schema 与用例特定参数约束的合规均值 |
| `tool_execution_success` | 已调用工具未返回错误的比例，含预期故障 |
| `source_accuracy` | 要求的来源类型是否存在，**不是来源真实性/权威性评级** |
| `citation_accuracy` | 引用 URL 来自工具返回、必要文档名出现在回答中；**不判断引用是否支持相邻论点** |
| `answer_contract` | 必需/禁止回答表达及非空检查；数值有独立硬检查，不能只看此项 |
| `hallucination_proxy` | 无来源的实时数值声明、未知 URL、工具协议泄漏等有限规则代理；0 不等于无幻觉 |
| `financial_safety` | 收益承诺、肯定式满仓建议、免责声明等有限规则检查；不是完整金融合规审查 |
| 性能 | 每个样本耗时、P50/P95、模型调用数、协议修复数、重复调用数、已知 Token |
| 人工审核 | 默认 `pending`；规则通过不自动成为专家认可 |

不适用的来源/引用指标为 `null`，不虚填 100%；Token 或费用没有可靠数据时为 `null`，不虚填 0。仅 replay 的外部模型费用确定为 0。计费 Token 使用服务商返回的 prompt/completion 统计，**不将 reasoning token 再次重复相加**。未接定价表，因此真实费用应核对服务商账单。

## 运行命令

在仓库根目录、已安装项目依赖的 Python 3.12+ 环境执行（Windows 可将 `python` 换成 `.\.venv\Scripts\python.exe`）：

```powershell
# 默认：全量离线工作流验收，不需要 Key、不调用付费服务
python -m evals.runners.benchmark --engine replay --suite full

# 真实模型：读取 .env / config.yaml；产生模型费用
python -m evals.runners.benchmark --engine model --suite smoke --allow-paid --concurrency 2 --max-model-calls 64 --max-output-tokens 65536 --max-input-chars 750000 --wall-seconds 900

# 针对定位到的问题复测，或比较 deep / quick
python -m evals.runners.benchmark --engine model --allow-paid --case-ids news-02,saved-portfolio-latest --research-mode deep --repeats 3
```

真实调用默认仅允许 HTTPS `api.xiaomimimo.com`；切换到别的已授权兼容服务需显式传 `--provider-host`。不会打印 API Key 或将 `.env` 写进报告。快速模式按生产逻辑限制为最多 4 步、每次 1600 输出 Token、每条 90 秒；深入模式保留配置中的 deep 预算。

总预算按**每次请求的输出上限预留**，包括工具 Schema 的输入字符量、请求次数、总墙钟时间。失败请求也占预算；评测关闭隐藏 HTTP 重试。注意这些上限不是货币费用上限，输入字符也不等于精确 Token。并发仅支持 1/2，单条异常会保留失败记录，超时/预算耗尽不得伪报完整通过。

## 输出、复评分与版本比较

默认输出 `data/evals/<UTC时间>/`，已被 Git 忽略：

- `runs.jsonl`：最终答案、真实工具输入/输出、来源、状态、Token 与阶段耗时。
- `cases.jsonl`：新运行执行时冻结的用例快照，避免后续改题混淆原始输入。
- `report.json` / `report.md`：用例覆盖、分类得分、逐项失败定位、待审核数量。
- `review.jsonl`：待审核答案及 usefulness / citation_entailment / missing_evidence / notes 空字段。

Manifest 记录模型、模式、配置、并发、Git revision、工作树是否有改动、数据集/fixture/评分器 hash 和预算。新执行还记录运行代码 hash。原始轨迹不自动上传 GitHub；若导入真实用户轨迹，必须先脱敏。

```powershell
# 用原始报告校验数据集与重复次数；不再次调用模型
python -m evals.runners.run_evals --suite smoke --runs data/evals/my-run/runs.jsonl --manifest data/evals/my-run/report.json --output data/evals/my-run/rescored/report.json

# 如果仅修正了评分合同，必须显式确认；保留新旧 hash 和原始报告
python -m evals.runners.run_evals --suite smoke --runs data/evals/my-run/runs.jsonl --manifest data/evals/my-run/report.json --allow-contract-update --output data/evals/my-run/rescored/report.json

# 同题同数据同评分口径的版本比较，默认允许 0.02 的规则分数浮动
python -m evals.runners.compare data/evals/baseline/report.json data/evals/candidate/report.json
```

**不可把修改后的问题/持仓/资料当作原模型已经执行过的输入。** `--allow-contract-update` 仅用于审核后确认的提取规则等评分修正；若改动执行输入，必须重新运行。默认拒绝合同变化、重复样本、未知样本、错误重复次数。漏跑样本会导致覆盖不完整、退出码非 0。比较器拒绝不同数据集、fixture、评分器、引擎或样本集合；列出模型/配置变化和每题差异。不把单次分数差当作统计显著性。

CLI 退出码 1 也可能表示“评测成功执行但模型未通过合同”，不一定是程序崩溃。有疑问先查看 coverage、逐项 checks 和原始回答。

## 人工审核与使用基线

人工审核建议分开填写：回答是否完成需求（0/1/2）、结论是否受引用支持（0/1/2）、遗漏证据和风险、工具是否必要。金融建议应由有相应能力的审核者复核。当前不接 LLM-as-judge，也没有伪造人工分数；可以先根据记录做辅助诊断，但应标为“辅助审阅”，不是专家签字。

日常 CI 运行评分器单测和 63 条 replay，不需要任何线上 Key；自动保留评测 artifact。付费模型评测须显式本地启动，不在每次 push 中触发。修改模型/提示词/编排前先冻结数据和评分合同，建议真实 full + 每题至少 3 次、比较 quick/deep 的相同样本并审核开放式答案。

本轮[首测结论](../docs/AGENT_EVALUATION.md)将原始失败、评分误判修正、实际能力问题和测试边界分别说明，避免把严格规则分数当作上线质量或多 Agent 改造的直接依据。

后续[优化与同题复测](../docs/AGENT_OPTIMIZATION.md)保留了完整迭代和失败记录。主基准仍为 63 条；另有一个不并入主成绩的明确新闻故障样本：

```powershell
python -m evals.runners.benchmark --engine replay --dataset evals/datasets/news_failure_explicit.jsonl
```

引用提取修复后，旧模型轨迹可重新评分而无需再次消费模型。比较必须两端使用同一个评分器版本，不得把不同版本的报告直接比作模型提升。
