from backend.app.agent.guardrails import apply_financial_guardrail, verify_tool_results
from backend.app.core.security import TokenService, hash_password, verify_password
from src.settings import SecuritySettings


def test_password_hash_and_access_token_roundtrip():
    encoded = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", encoded)
    assert not verify_password("wrong-password", encoded)
    service = TokenService(SecuritySettings(jwt_secret_key="test-secret-that-is-long-enough"))
    token = service.access_token("user-1")
    assert service.decode_access(token) == "user-1"


def test_guardrail_removes_certainty_and_discloses_derived_data():
    verification = verify_tool_results([{"tool": "price", "output": {"metadata": {"source_type": "derived", "is_stale": False}}}])
    answer, flags = apply_financial_guardrail("黄金保证上涨，建议满仓。", verification, has_portfolio=False)
    assert "保证上涨" not in answer
    assert "不构成投资建议" in answer
    assert "derived" in answer
    assert flags
