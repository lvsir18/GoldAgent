from fastapi.testclient import TestClient

from backend.app.api.app import create_app
from backend.app.api.routes import agent as routes
from backend.app.agent.graph import GoldAgentRuntime
from backend.app.llm.base import ChatResponse
from backend.app.tools.registry import ToolRegistry
from src.settings import AppSettings


def test_text_tool_calls_never_reach_sse_messages_or_completed_runs(tmp_path, monkeypatch):
    class InvalidGateway:
        async def chat(self, messages, tools=None):
            return ChatResponse(content='<tool_call><function=goldspot_query_gold_price></function></tool_call>')

    monkeypatch.setattr(routes, "build_agent_runtime", lambda settings, **kwargs:
        GoldAgentRuntime(settings, InvalidGateway(), ToolRegistry([]), kwargs.get("checkpointer")))
    settings = AppSettings(database={"url":f"sqlite:///{tmp_path / 'protocol.db'}"},security={"demo_mode":True,"jwt_secret_key":"offline-fixture-only-secret"})
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/v1/chat/stream", json={"message":"离线协议测试", "mode":"deep"})
        assert response.status_code == 200
        assert "event: run_finished" in response.text
        assert "goldspot_" not in response.text and "<tool_call>" not in response.text
        run = client.get("/api/v1/agent/runs").json()["data"][0]
        assert run["status"] == "incomplete"
        detail = client.get(f"/api/v1/agent/runs/{run['id']}").json()["data"]["state"]
        assert detail["tool_results"] == []
        assert detail["metrics"]["llm_calls"] == 2
        messages = client.get(f"/api/v1/sessions/{run['session_id']}/messages").json()["data"]
        assert "goldspot_" not in messages[-1]["content"]
        assert "未能正确完成" in messages[-1]["content"]
