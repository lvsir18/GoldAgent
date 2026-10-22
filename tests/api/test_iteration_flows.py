import time
from fastapi.testclient import TestClient

from backend.app.api.app import create_app
from backend.app.api.routes import agent as routes
from backend.app.llm.base import ChatResponse
from backend.app.agent.graph import GoldAgentRuntime
from backend.app.tools.registry import ToolRegistry
from src.settings import AppSettings


def test_authenticated_research_report_and_tenant_boundaries(tmp_path, monkeypatch):
    class OfflineGateway:
        async def chat(self, messages, tools=None):
            return ChatResponse(content="这是离线测试研究结论，不包含实时行情。")
    monkeypatch.setattr(routes, "build_agent_runtime", lambda settings, **kwargs: GoldAgentRuntime(settings, OfflineGateway(), ToolRegistry([]), kwargs.get("checkpointer")))
    settings = AppSettings(database={"url": f"sqlite:///{tmp_path / 'trust.db'}"}, security={"demo_mode": True, "jwt_secret_key": "offline-test-secret"})
    with TestClient(create_app(settings)) as client:
        def register(email):
            result = client.post("/api/v1/auth/register", json={"email": email, "password": "isolated-test-password"})
            return {"Authorization": "Bearer " + result.json()["data"]["access_token"]}
        first, second = register("one@example.com"), register("two@example.com")
        assert client.get("/api/v1/reports", headers={"Authorization": "Bearer invalid"}).status_code == 401
        started = time.monotonic()
        response = client.post("/api/v1/chat/stream", headers=first, json={"message": "这是离线测试"})
        assert response.status_code == 200
        assert "event: run_finished" in response.text
        assert time.monotonic() - started < 3  # Previously the empty queue added ten seconds.
        run = client.get("/api/v1/agent/runs", headers=first).json()["data"][0]
        assert client.get(f"/api/v1/agent/runs/{run['id']}", headers=second).status_code == 404
        assert client.get("/api/v1/agent/runs", headers=second).json()["data"] == []
        report = client.post("/api/v1/reports", headers=first, json={"title": "离线研究报告", "run_id": run["id"]})
        assert report.status_code == 200
        body = report.json()["data"]
        assert "离线测试研究结论" in body["content"]
        assert body["metadata"]["run_id"] == run["id"]
        assert "evidence" in body["metadata"]
        assert client.get(f"/api/v1/reports/{body['id']}/download", headers=second).status_code == 404
        assert client.post("/api/v1/reports", headers=second, json={"title":"forbidden", "run_id":run["id"]}).status_code == 404
        assert client.post(f"/api/v1/agent/runs/{run['id']}/feedback", headers=first, json={"value":"helpful"}).status_code == 200
        assert client.post(f"/api/v1/agent/runs/{run['id']}/feedback", headers=second, json={"value":"helpful"}).status_code == 404
        deep = client.post("/api/v1/chat", headers=first, json={"message":"offline deep research", "mode":"deep"}).json()["data"]
        assert deep["mode"] == "deep"
        assert [p["phase"] for p in deep["metrics"]["phases"]] == ["plan", "synthesize"]
        assert deep["metrics"]["reasoning_strategy"] == "final_only"
        def unavailable(*args, **kwargs):
            raise RuntimeError("Offline provider configuration failure")
        monkeypatch.setattr(routes, "build_agent_runtime", unavailable)
        response = client.post("/api/v1/chat/stream", headers=first, json={"message": "test failure"})
        assert "event: error" in response.text
        latest = client.get("/api/v1/agent/runs", headers=first).json()["data"][0]
        assert latest["status"] == "failed"
        assert latest["question"] == "test failure"
