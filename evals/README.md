# GoldAgent Evaluations

`datasets/goldagent_cases.jsonl` contains 55 scenarios across market, technical,
news, forecast, portfolio, backtest, knowledge, multi-step, safety, general and
failure behavior. The default runner evaluates recorded JSONL runs and never calls
a paid API. Use `python -m evals.runners.run_evals --runs <recording.jsonl>` and
`python -m evals.runners.compare baseline.json candidate.json` in regression jobs.
