from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.api.app import create_app
from backend.app.api.routes import agent as agent_routes
from backend.app.api.routes.agent import session_title_from_message
from backend.app.services.market import MarketService
from src.settings import AppSettings
from tests.conftest import FakeMarketProvider


def test_session_title_uses_first_question_content():
    assert session_title_from_message("  分析   本周黄金走势  ") == "分析 本周黄金走势"
    assert session_title_from_message("x" * 50).endswith("…")
    assert len(session_title_from_message("x" * 50)) == 37


def test_health_auth_and_all_primary_workbench_apis(tmp_path, market_frame, source_metadata, monkeypatch):
    settings = AppSettings(
        database={"url": f"sqlite:///{tmp_path / 'api.db'}"},
        security={"demo_mode": True, "jwt_secret_key": "test-only-secret", "frontend_origins": ["http://localhost:3000"]},
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/ready").json()["checks"]["database"] is True

        registered = client.post("/api/v1/auth/register", json={"email": "person@example.com", "password": "a-secure-password"})
        assert registered.status_code == 200
        access = registered.json()["data"]["access_token"]
        refresh = registered.json()["data"]["refresh_token"]
        assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 200
        me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {access}"})
        assert me.json()["data"]["email"] == "person@example.com"

        created = client.post("/api/v1/sessions", json={"title": "API smoke"})
        assert created.status_code == 200
        session_id = created.json()["data"]["id"]
        assert client.get(f"/api/v1/sessions/{session_id}").status_code == 200

        portfolio = client.put("/api/v1/portfolio", json={"grams": 20, "average_cost": 500, "planned_investment": 1000})
        assert portfolio.json()["data"]["grams"] == 20
        assert client.get("/api/v1/portfolio/analysis?current_price=525").json()["data"]["pnl"] == 500

        client.app.state.services.market = MarketService(FakeMarketProvider(market_frame, source_metadata))
        assert client.get("/api/v1/market/summary").status_code == 200
        forecast = client.post("/api/v1/forecasts", json={"symbol": "AU0", "horizon": 3, "model": "linear"})
        assert forecast.status_code == 200
        forecast_id = forecast.json()["data"]["id"]
        assert client.get(f"/api/v1/forecasts/{forecast_id}/evaluation").status_code == 200
        backtest = client.post("/api/v1/backtests", json={"parameters": {"short_window": 5, "long_window": 20}})
        assert backtest.status_code == 202
        assert client.get(f"/api/v1/backtests/{backtest.json()['data']['id']}").json()["data"]["status"] == "completed"

        async def fake_run(request, body, database, user_id, **kwargs):
            if callback := kwargs.get("on_event"):
                await callback("run_progress", {"stage": "fixture", "message": "fixture progress"})
            return {"run_id": "run-fixture", "session_id": session_id, "status": "completed", "final_answer": "fixture", "verification": {"passed": True}, "tool_results": []}
        monkeypatch.setattr(agent_routes, "_run", fake_run)
        assert client.post("/api/v1/chat", json={"message": "分析黄金", "session_id": session_id}).json()["data"]["final_answer"] == "fixture"
        stream = client.post("/api/v1/chat/stream", json={"message": "分析黄金", "session_id": session_id})
        assert "event: run_progress" in stream.text
        assert "event: answer_delta" in stream.text

        upload = client.post("/api/v1/knowledge/documents", files={"file": ("gold.md", "黄金与实际利率相关。", "text/markdown")})
        assert upload.status_code == 200
        assert client.post("/api/v1/knowledge/search", json={"query": "实际利率", "top_k": 3}).json()["data"]

        report = client.post("/api/v1/reports", json={"title": "测试报告", "report_type": "analysis", "payload": {"price": 525}})
        assert report.status_code == 200
        report_id = report.json()["data"]["id"]
        assert client.get(f"/api/v1/reports/{report_id}/download").status_code == 200
