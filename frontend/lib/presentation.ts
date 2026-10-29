// Product copy only: diagnostic payloads remain in internal records, not UI messages.
export type Translate = (zh: string, en: string) => string;

export function userError(error: unknown, text: Translate): string {
  const value = error as { code?: string; status?: number; message?: string } | null;
  const code = value?.code;
  const message = typeof error === "string" ? error : value?.message ?? "";
  const status = value?.status ?? Number(message.match(/HTTP (\d{3})/)?.[1]);
  if (status === 401) return text("请检查登录信息，或重新登录后再试。", "Check your login details or sign in again.");
  if (status === 403) return text("你暂时没有权限查看或修改这项内容。", "You do not have access to this content.");
  if (status === 404) return text("内容不存在或已被删除，请刷新列表。", "This item is unavailable or was deleted. Refresh the list.");
  if (status === 409) return text("当前状态无法完成此操作，请刷新后检查内容是否已存在或尚未完成。", "This action is unavailable in the current state. Refresh and check for an existing or unfinished item.");
  if (status === 413) return text("文件过大，请缩小文件后重新上传。", "The file is too large. Upload a smaller file.");
  if (status === 415) return text("暂不支持此文件格式，请上传 PDF、Markdown 或 TXT。", "Upload a PDF, Markdown or TXT file.");
  if (status === 422 || status === 400 || code === "VALIDATION_ERROR") return text("请检查填写内容、文件格式或参数范围后重试。", "Check your input, file format and parameter ranges, then retry.");
  if (status === 429) return text("请求较多，请稍等片刻后重试。", "Too many requests. Please wait a moment and retry.");
  if (code === "MARKET_DATA_UNAVAILABLE") return text("暂时无法获取行情，请稍后刷新；请勿将旧数据视为实时价格。", "Market data is temporarily unavailable. Refresh later; older data is not a live quote.");
  if (code === "CONFIGURATION_ERROR") return text("此功能暂未配置完成，请联系网站维护者。", "This feature is not configured yet. Contact the site maintainer.");
  if (/timeout|timed out|超时/i.test(message)) return text("本次请求等待过久，请稍后重试或缩小研究范围。", "This request took too long. Retry or narrow the research scope.");
  if (/fetch|network|offline/i.test(message)) return text("连接暂时中断，请检查网络后重试。", "Connection interrupted. Check your network and retry.");
  return text("暂时无法完成此操作，请稍后重试。若持续出现，请联系网站维护者。", "This action could not be completed. Retry later or contact the site maintainer if it persists.");
}

const tools: Record<string, [string, string]> = {
  get_gold_spot_price: ["获取黄金现价", "Gold spot price"],
  get_market_history: ["获取历史行情", "Market history"],
  calculate_technical_indicators: ["计算技术指标", "Technical indicators"],
  search_financial_news: ["搜索财经新闻", "Financial news"],
  forecast_gold_price: ["黄金价格预测", "Gold forecast"],
  analyze_portfolio: ["投资组合分析", "Portfolio analysis"],
  run_backtest: ["运行策略回测", "Strategy backtest"],
  retrieve_financial_knowledge: ["查阅知识库", "Knowledge lookup"],
};
export function toolLabel(name: string, text: Translate) {
  return tools[name] ? text(...tools[name]) : text("资料查询", "Research lookup");
}
export function sourceLabel(name: unknown, text: Translate) {
  if (typeof name !== "string" || !name.trim()) return text("来源待确认", "Source unconfirmed");
  if (/derived from akshare/i.test(name)) return text("黄金参考行情（汇率换算）", "Gold reference (currency-converted)");
  if (/akshare.*sina|sina.*futures/i.test(name)) return text("新浪期货行情", "Sina futures market data");
  if (/fixture|simulation|fake|^test$/i.test(name)) return text("演示数据", "Demo data");
  if (name === "Knowledge Base") return text("知识库文档", "Knowledge document");
  if (/traceback|exception|error|embedding|postgres|https?:\/\/|[\\{}]|api[_-]?key|token|secret/i.test(name) || name.length > 100) return text("参考资料", "Reference material");
  return name;
}
export function displayTime(value: unknown, locale: string) {
  if (typeof value !== "string" || !Number.isFinite(Date.parse(value))) return "—";
  return new Date(value).toLocaleString(locale === "zh" ? "zh-CN" : "en-US");
}
export function limitationLabel(value: string, text: Translate) {
  if (/stale|过期|较早/.test(value)) return text("部分资料时间较早，请结合最新行情核查。", "Some sources are older; cross-check against current market data.");
  if (/No tools|未调用/.test(value)) return text("本次回答未查询外部资料，不能视为实时行情分析。", "No external sources were consulted; this is not a live market assessment.");
  if (/derived|换算/.test(value)) return text("部分行情通过换算获得，不是直接交易报价。", "Some prices are converted references, not direct tradable quotes.");
  return text("部分资料未能获取，相关结论可能不完整，请稍后重试核查。", "Some sources could not be retrieved. Conclusions may be incomplete; retry to verify.");
}

// Only migrate the old automatically appended diagnostic footer, not normal prose/code.
export function publicAnswer(content: string) {
  const protocol = /<\s*(?:\/?tool_call\b|function\s*=|parameter\s*=)/i;
  const decoded = content.replace(/&lt;/gi, "<").replace(/&gt;/gi, ">");
  if (protocol.test(decoded)) {
    const cleaned = decoded
      .replace(/```[^\n]*\n[^]*?```/g, block => protocol.test(block) ? "" : block)
      .replace(/<\s*tool_call\b[^>]*>[^]*?<\s*\/tool_call\s*>/gi, "")
      .replace(/<\s*(?:\/?tool_call\b|function\s*=|parameter\s*=)[^]*/gi, "").trim();
    content = "这条回答包含未执行的工具指令，不能作为已完成分析。请重新发送问题。\n\n" + cleaned;
  }
  return content.replace(/\n\n数据说明：[^]*?(?=\n\n|$)/g, footer =>
    /(?:returned stale data|returned derived|\bfailed:|ValidationError|Traceback|pydantic)/.test(footer)
      ? "\n\n数据说明：部分资料存在获取或时效限制，请结合来源与最新行情核查。" : footer);
}
