from types import SimpleNamespace

import pytest

from backend.app.db.session import Database


class _Connection:
    dialect = SimpleNamespace(name="postgresql")

    def __init__(self):
        self.statements: list[str] = []
        self.created_metadata = False

    async def execute(self, statement):
        self.statements.append(str(statement))

    async def run_sync(self, callback):
        self.created_metadata = callback.__self__ is not None


class _Begin:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_args):
        return False


class _Engine:
    def __init__(self, connection):
        self.connection = connection

    def begin(self):
        return _Begin(self.connection)


@pytest.mark.asyncio
async def test_postgres_enables_vector_before_creating_tables():
    connection = _Connection()
    database = Database(engine=_Engine(connection), sessions=None)

    await database.create_all()

    assert connection.statements == ["CREATE EXTENSION IF NOT EXISTS vector"]
    assert connection.created_metadata is True
