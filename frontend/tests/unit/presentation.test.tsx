import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LanguageProvider } from "@/i18n/language";
import { ResearchEvidence } from "@/components/common/research-evidence";
import { SourceBadge } from "@/components/common/source-badge";
import { publicAnswer, sourceLabel, toolLabel, userError } from "@/lib/presentation";

const diagnostic = "ValidationError Traceback postgres://private-host INTERNAL_CANARY api_key=NOT_A_REAL_KEY";
const zh = (cn: string, _en: string) => cn;
const en = (_cn: string, english: string) => english;

describe("user-facing presentation boundary", () => {
  it.each([
    '<tool_call><function=goldspot_query_gold_price><parameter=product_type>国内期货</parameter></function></tool_call>',
    '<tool_call><function=goldspot_query_gold_price',
    '&lt;tool_call&gt;&lt;function=goldspot_query_gold_price&gt;',
    '```xml\n<tool_call><function=goldspot_query_gold_price></function></tool_call>\n```',
  ])("replaces unexecuted tool envelopes with an explicit retry notice", leaked => {
    const content = publicAnswer(leaked + "\n\n仅供参考。");
    expect(content).toContain("未执行的工具指令");
    expect(content).not.toMatch(/goldspot_|<tool_call>|<function=/);
  });
  it.each([zh, en])("does not echo raw exceptions or unknown tool identifiers", text => {
    expect(userError(new Error(diagnostic), text)).not.toContain("INTERNAL_CANARY");
    expect(userError({status:422, message:diagnostic}, text)).not.toContain("ValidationError");
    expect(userError({status:401, message:diagnostic}, text)).toBe(text("请检查登录信息，或重新登录后再试。", "Check your login details or sign in again."));
    expect(toolLabel("internal_debug_function", text)).not.toContain("internal_debug_function");
    expect(sourceLabel(diagnostic, text)).not.toContain("private-host");
  });
  it("shows readable evidence without raw state, chunk IDs or arguments", () => {
    render(<LanguageProvider><ResearchEvidence tools={[{tool:"get_market_history",error:diagnostic,arguments:{context:"PRIVATE_ARGUMENT_CANARY"}}]} evidence={{snapshots:[{tool:"get_market_history",metadata:{source:"AkShare/Sina Futures",retrieved_at:"2026-10-22T10:00:00Z"}}],citations:[{title:"黄金研究文档",chunk_id:"PRIVATE_CHUNK_CANARY",page:2,source:"Knowledge Base"}],limitations:[diagnostic]}}/></LanguageProvider>);
    fireEvent.click(screen.getByText(/参考来源与研究说明/));
    expect(screen.getByText(/新浪期货行情/)).toBeInTheDocument();
    expect(screen.getByText(/黄金研究文档/)).toHaveTextContent("页 2");
    expect(screen.getByText(/未能获取，可稍后重试/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/CANARY|ValidationError|Traceback|get_market_history/);
  });
  it("migrates legacy diagnostic footers without hiding normal content", () => {
    const answer = `行情需核查。\n\n数据说明：get_market_history failed: ${diagnostic}\n\n仅供参考。`;
    expect(publicAnswer(answer)).not.toContain("INTERNAL_CANARY");
    expect(publicAnswer(answer)).toContain("仅供参考");
    expect(publicAnswer("RSI 是技术指标。\n\n数据说明：截至昨日收盘。" )).toContain("截至昨日收盘");
  });
  it("recognizes the real market provider's price currency unit", () => {
    render(<LanguageProvider><SourceBadge source={{source:"AkShare/Sina Futures",source_type:"direct",currency:"CNY/g",market:"CN",symbol:"AU0",is_cached:false,is_stale:false,is_derived:false,retrieved_at:"2026-10-22T10:00:00Z"}}/></LanguageProvider>);
    fireEvent.click(screen.getByText("新浪期货行情 · 本次获取"));
    expect(screen.getByText(/AU0 · 国内市场 · 人民币/)).toBeInTheDocument();
  });
});
