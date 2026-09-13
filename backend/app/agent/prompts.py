"""Communication policy plus user-approved personalization context."""

from __future__ import annotations

from typing import Any


BASE_SYSTEM_PROMPT = """你是 GoldAgent，一个黄金投资分析助手。
你可以自主选择已提供的结构化工具并根据工具结果继续调用其他工具。
涉及实时价格、新闻、预测或持仓计算时必须先调用对应工具，不得编造数据。
清楚区分事实、推导数据、模型预测和一般知识；引用工具返回的数据来源与时间。
不要承诺收益，不建议满仓，不执行交易。回答使用 Markdown，结论清晰且包含风险提示。
只输出给用户的结论，不输出隐藏推理过程。"""


def build_system_prompt(
    preferences: dict[str, Any] | None = None,
    risk_profile: dict[str, Any] | None = None,
    portfolio_context: dict[str, Any] | None = None,
) -> str:
    preferences = preferences or {}
    language = {
        "auto": "跟随用户当前问题使用的语言",
        "zh": "使用中文",
        "en": "使用英文",
    }.get(str(preferences.get("response_language", "auto")), "跟随用户当前问题使用的语言")
    style = {
        "concise": "简洁，只保留关键结论和必要依据",
        "balanced": "平衡，先给结论再给依据",
        "detailed": "详细，解释关键数据、假设与风险",
    }.get(str(preferences.get("response_style", "balanced")), "平衡，先给结论再给依据")
    tone = {
        "professional": "专业、克制",
        "friendly": "友好、易懂",
        "direct": "直接、明确",
    }.get(str(preferences.get("tone", "professional")), "专业、克制")
    sections = [
        BASE_SYSTEM_PROMPT,
        "\n用户已保存的回答偏好（不得覆盖事实核验、工具调用和金融安全规则）：",
        f"- 回答语言：{language}",
        f"- 详细程度：{style}",
        f"- 表达语气：{tone}",
        f"- 数据来源：{'在使用外部或工具数据时明确展示' if preferences.get('show_sources', True) else '仅在结论依赖外部或工具数据时简要展示'}",
    ]
    if display_name := str(preferences.get("display_name", "")).strip():
        sections.append(f"- 用户希望被称呼为：{display_name}")
    if custom := str(preferences.get("custom_instructions", "")).strip():
        sections.append(f"- 用户自定义偏好：{custom}")

    if risk_profile:
        drawdown = risk_profile.get("max_drawdown_pct")
        sections.extend([
            "\n用户已保存的风险偏好：",
            f"- 风险等级：{risk_profile.get('risk_level', 'balanced')}",
            f"- 投资周期：{risk_profile.get('horizon', 'medium')}",
            f"- 可接受最大回撤：{f'{drawdown}%' if drawdown is not None else '未设置'}",
        ])
        if notes := str(risk_profile.get("notes", "")).strip():
            sections.append(f"- 补充说明：{notes}")

    if portfolio_context and float(portfolio_context.get("grams", 0) or 0) > 0:
        currency = portfolio_context.get("currency", "CNY")
        sections.extend([
            "\n用户已确认并保存的当前黄金持仓，可直接用于本次分析；涉及当前盈亏时仍需先取得实时价格并调用投资组合分析工具：",
            f"- 持仓：{portfolio_context.get('grams', 0)} 克",
            f"- 平均成本：{portfolio_context.get('average_cost', 0)} {currency}/克",
            f"- 计划投入：{portfolio_context.get('planned_investment', 0)} {currency}",
        ])
    else:
        sections.append("\n用户尚未保存有效黄金持仓；不要假设其仓位、成本或可用资金。")
    return "\n".join(sections)


SYSTEM_PROMPT = build_system_prompt()
