"""Exercise the actual Alembic entry point against a disposable database."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_fresh_database_upgrades_to_head(tmp_path):
    path = tmp_path / "migration.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{path.as_posix()}"}
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(path) as connection:
        assert connection.execute("select version_num from alembic_version").fetchone()[0] == "0002"
        assert connection.execute("select count(*) from forecasts").fetchone()[0] == 0
