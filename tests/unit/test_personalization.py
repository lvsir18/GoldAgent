from backend.app.agent.prompts import build_system_prompt


def test_personalized_prompt_contains_saved_preferences_risk_and_portfolio():
    prompt = build_system_prompt(
        preferences={
            "response_language": "zh",
            "response_style": "detailed",
            "tone": "friendly",
            "show_sources": True,
            "custom_instructions": "先给结论",
        },
        risk_profile={"risk_level": "conservative", "horizon": "long", "max_drawdown_pct": 10, "notes": "控制回撤"},
        portfolio_context={"grams": 20, "average_cost": 500, "planned_investment": 1000, "currency": "CNY"},
    )
    assert "使用中文" in prompt
    assert "详细" in prompt
    assert "先给结论" in prompt
    assert "conservative" in prompt
    assert "持仓：20 克" in prompt
    assert "平均成本：500 CNY/克" in prompt


def test_prompt_does_not_assume_missing_portfolio():
    assert "尚未保存有效黄金持仓" in build_system_prompt(portfolio_context={"grams": 0})
