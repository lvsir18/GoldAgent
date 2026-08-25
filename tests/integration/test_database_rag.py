from __future__ import annotations

from backend.app.db.repositories import DEMO_USER_ID, UserRepository
from backend.app.db.session import build_database
from backend.app.providers.embedding.local_hash import LocalHashEmbeddingProvider
from backend.app.rag.service import KnowledgeService, chunk_text, parse_document
from src.settings import AppSettings


async def test_sqlite_database_and_tenant_scoped_rag(tmp_path):
    settings = AppSettings(database={"url": f"sqlite:///{tmp_path / 'test.db'}"})
    database = build_database(settings)
    try:
        await database.create_all()
        async with database.session() as session:
            await UserRepository(session).ensure_demo_user()
        service = KnowledgeService(database, LocalHashEmbeddingProvider())
        document = await service.ingest(DEMO_USER_ID, "notes.md", "黄金与实际利率通常呈现负相关关系。\n央行购金会影响长期需求。".encode())
        results = await service.search(DEMO_USER_ID, "实际利率", top_k=3)
        assert document.status == "ready"
        assert results and results[0]["document_id"] == document.id
        assert await service.search("other-tenant", "实际利率") == []
    finally:
        await database.dispose()


def test_document_parser_and_chunk_overlap():
    text, media_type = parse_document("note.txt", b"gold market")
    assert text == "gold market" and media_type == "text/plain"
    chunks = chunk_text("A" * 1800, chunk_size=500, overlap=50)
    assert len(chunks) >= 4
    assert chunks[0][-50:] == chunks[1][:50]
