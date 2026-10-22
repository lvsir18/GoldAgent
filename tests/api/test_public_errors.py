from fastapi.testclient import TestClient
from backend.app.api.app import create_app
from src.errors import ExternalProviderError
from src.settings import AppSettings


def test_provider_failure_does_not_return_private_diagnostics(tmp_path):
    app = create_app(AppSettings(database={"url":f"sqlite:///{tmp_path / 'errors.db'}"},security={"demo_mode":True}))

    @app.get("/_test/provider-failure")
    async def fail():
        raise ExternalProviderError("PRIVATE_PROVIDER_CANARY", "Traceback postgres://PRIVATE_ERROR_CANARY")

    with TestClient(app) as client:
        response = client.get("/_test/provider-failure")
        assert response.status_code == 502
        assert response.json()["error"]["code"] == "EXTERNAL_PROVIDER_ERROR"
        assert "CANARY" not in response.text and "Traceback" not in response.text
