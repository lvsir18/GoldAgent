"""User-facing research facts, separate from private diagnostic records."""
import re
from ..llm.protocol import has_tool_protocol, strip_tool_protocol, PROTOCOL_NOTICE

TOOL_NAMES = {
    "get_gold_spot_price": "黄金现价", "get_market_history": "历史行情",
    "calculate_technical_indicators": "技术指标", "search_financial_news": "财经新闻",
    "forecast_gold_price": "价格预测", "analyze_portfolio": "持仓分析",
    "run_backtest": "策略回测", "retrieve_financial_knowledge": "知识库资料",
}


def tool_name(name: str) -> str:
    return TOOL_NAMES.get(name, "参考资料")


def source_name(name: str | None) -> str:
    if not name:
        return "来源待确认"
    if "derived from akshare" in name.lower():
        return "黄金参考行情（汇率换算）"
    if "sina" in name.lower():
        return "新浪期货行情"
    if name == "Knowledge Base":
        return "知识库文档"
    if re.search(r"fixture|fake|simulation", name, re.I):
        return "演示数据"
    if len(name) > 100 or re.search(r"error|exception|traceback|embedding|postgres|https?://|[\\{}]|token|secret|api[_-]?key", name, re.I):
        return "参考资料"
    return name


def public_answer(answer: str) -> str:
    if has_tool_protocol(answer):
        answer = PROTOCOL_NOTICE + "\n\n" + strip_tool_protocol(answer)
    # Migrate only the old generated diagnostic footer; leave ordinary prose intact.
    def replace(match):
        footer = match.group()
        if re.search(r"returned stale data|returned derived|\bfailed:|ValidationError|Traceback|pydantic", footer):
            return "\n\n数据说明：部分资料存在获取或时效限制，请结合来源与最新行情核查。"
        return footer
    return re.sub(r"\n\n数据说明：.*?(?=\n\n|$)", replace, answer, flags=re.S)


def limitation_text(value: str) -> str:
    if re.search(r"stale|过期|较早", value):
        return "部分资料时间较早，请结合最新行情核查。"
    if re.search(r"No tools|未调用", value):
        return "本次回答未查询外部资料，不能视为实时行情分析。"
    if re.search(r"derived|换算", value):
        return "部分行情通过换算获得，不是直接交易报价。"
    return "部分资料未能获取，相关结论可能不完整，请稍后重试核查。"
