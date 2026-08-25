from pathlib import Path

import pytest

from src.errors import ConfigurationError
from src.settings import AppSettings


def test_duplicate_yaml_key_is_rejected(tmp_path: Path):
    config = tmp_path / "config.yaml"
    config.write_text("agent:\n  model: one\n  model: two\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Duplicate YAML key"):
        AppSettings.load(config)


def test_production_rejects_default_jwt_secret(tmp_path: Path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text("security:\n  demo_mode: false\n", encoding="utf-8")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.setenv("DEMO_MODE", "false")
    with pytest.raises(ConfigurationError, match="JWT_SECRET_KEY"):
        AppSettings.load(config)
