"""Oracle-driven workflow replay: validates plumbing, NOT model intelligence."""
import json
from backend.app.llm.base import ChatResponse, ToolCall
from langchain_core.messages import ToolMessage


class ReplayGateway:
    def __init__(self, case):
        self.case, self.round = case, 0

    async def chat(self, messages, tools=None):
        self.round += 1
        expected = list(self.case.expected_tools)
        expected += [group[0] for group in self.case.alternative_tool_groups if not set(group).intersection(expected)]
        if self.round == 1 and expected:
            calls = []
            for i, name in enumerate(expected):
                args = {}
                for check in self.case.argument_checks:
                    if check.tool == name and check.value is not None and "." not in check.field:
                        args[check.field] = check.value
                if name in {"search_financial_news", "retrieve_financial_knowledge"}:
                    args.setdefault("query", self.case.query)
                if name == "analyze_portfolio":
                    args.setdefault("current_price", 525)
                calls.append(ToolCall(id=f"replay-{i}",name=name,arguments=args))
            return ChatResponse(tool_calls=calls)
        # Fixed human-authored oracle text, not an LLM answer or finance advice.
        content = "这是合成工作流回放，不是模型效果评测。资料截至固定评测时间，不能代表实时市场。"
        if self.case.behavior in {"clarify", "refuse"}:
            content += "缺少持仓克数、成本及风险信息，需要确认；无法保证收益，不建议满仓，不执行自动下单。"
        elif self.case.behavior == "graceful_failure":
            content += "资料不足、工具不可用或数据不足，暂时无法取得完整行情、新闻或知识库内容，不能生成可靠预测。"
        else:
            outputs = {}
            for message in messages:
                if isinstance(message, ToolMessage):
                    outputs[message.name] = json.loads(message.content)
            portfolio = outputs.get("analyze_portfolio", {})
            price = outputs.get("get_gold_spot_price", {}).get("price", portfolio.get("current_price", 525))
            pnl, cost = portfolio.get("pnl", 0), portfolio.get("break_even_price", 500)
            content += f"合成参考价{price:g}元/克；示例盈亏{pnl:g}元，平均成本{cost:g}元/克。实际利率与美元影响存在不确定性。"
            if "search_financial_news" in expected:
                content += "来源：https://example.com/eval/fed。"
            if "retrieve_financial_knowledge" in expected:
                content += "知识库《黄金宏观研报.md》第3页、《黄金风险笔记.md》第2页、《积存金规则.md》第1页、《黄金历史事件.md》第4页。"
        if self.case.scenario == "stale_market":
            content += "注意数据较早，已经过期。"
        # Do not emit unrelated citations for cases that never queried sources.
        if "search_financial_news" not in expected:
            content = content.replace("https://example.com/eval/fed", "固定评测资料")
        if self.case.language == "en":
            content = "Synthetic workflow replay: gold safe-haven demand may rise during uncertainty, but risk remains. Not investment advice."
        return ChatResponse(content=content)
