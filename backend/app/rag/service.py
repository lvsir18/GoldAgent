"""Document ingestion, chunking, persistent embeddings and tenant retrieval."""

from __future__ import annotations

import hashlib
import io
import math
import os
import re
from typing import Any

from pypdf import PdfReader
from sqlalchemy import delete, select

from src.settings import AppSettings

from ..db.models import DocumentChunk, DocumentRecord
from ..db.session import Database
from ..providers.embedding.base import EmbeddingProvider
from ..providers.embedding.local_hash import LocalHashEmbeddingProvider
from ..providers.embedding.openai_compatible import OpenAICompatibleEmbeddingProvider


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    cleaned = re.sub(r"\r\n?", "\n", text).strip()
    if not cleaned:
        return []
    chunks, start = [], 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        if end < len(cleaned):
            boundary = max(cleaned.rfind("\n", start, end), cleaned.rfind("。", start, end))
            if boundary > start + chunk_size // 2:
                end = boundary + 1
        chunks.append(cleaned[start:end].strip())
        if end >= len(cleaned):
            break
        start = max(start + 1, end - overlap)
    return [chunk for chunk in chunks if chunk]


def parse_document(filename: str, content: bytes) -> tuple[str, str]:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix in {"md", "txt"}:
        return content.decode("utf-8", errors="replace"), f"text/{'markdown' if suffix == 'md' else 'plain'}"
    if suffix == "pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages), "application/pdf"
    raise ValueError("Only PDF, Markdown and TXT documents are supported")


class KnowledgeService:
    def __init__(self, database: Database, embeddings: EmbeddingProvider):
        self.database, self.embeddings = database, embeddings

    async def ingest(self, user_id: str, filename: str, content: bytes) -> DocumentRecord:
        if len(content) > 10 * 1024 * 1024:
            raise ValueError("Document exceeds the 10 MB limit")
        text, media_type = parse_document(filename, content)
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError("Document contains no extractable text")
        vectors = await self.embeddings.embed(chunks)
        checksum = hashlib.sha256(content).hexdigest()
        async with self.database.session() as session:
            existing = await session.scalar(select(DocumentRecord).where(DocumentRecord.user_id == user_id, DocumentRecord.checksum == checksum))
            if existing:
                return existing
            document = DocumentRecord(user_id=user_id, filename=filename, media_type=media_type, status="processing", checksum=checksum, metadata_json={"embedding_provider": self.embeddings.name})
            session.add(document); await session.flush()
            for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
                session.add(DocumentChunk(document_id=document.id, user_id=user_id, chunk_index=index, content=chunk, embedding=vector, metadata_json={"filename": filename, "chunk_index": index}))
            document.status = "ready"
            document.metadata_json = {**document.metadata_json, "chunk_count": len(chunks)}
            await session.flush()
            return document

    async def list_documents(self, user_id: str) -> list[DocumentRecord]:
        async with self.database.session() as session:
            return list((await session.scalars(select(DocumentRecord).where(DocumentRecord.user_id == user_id).order_by(DocumentRecord.created_at.desc()))).all())

    async def get_document(self, user_id: str, document_id: str) -> DocumentRecord | None:
        async with self.database.session() as session:
            return await session.scalar(select(DocumentRecord).where(DocumentRecord.id == document_id, DocumentRecord.user_id == user_id))

    async def delete_document(self, user_id: str, document_id: str) -> bool:
        async with self.database.session() as session:
            result = await session.execute(delete(DocumentRecord).where(DocumentRecord.id == document_id, DocumentRecord.user_id == user_id))
            return bool(result.rowcount)

    async def search(self, user_id: str, query: str, top_k: int = 5, document_id: str | None = None) -> list[dict[str, Any]]:
        query_vector = (await self.embeddings.embed([query]))[0]
        async with self.database.session() as session:
            statement = select(DocumentChunk).where(DocumentChunk.user_id == user_id)
            if document_id:
                statement = statement.where(DocumentChunk.document_id == document_id)
            chunks = list((await session.scalars(statement)).all())
        scored = []
        for chunk in chunks:
            vector = list(chunk.embedding or [])
            if not vector:
                continue
            denominator = (math.sqrt(sum(a*a for a in query_vector)) or 1) * (math.sqrt(sum(b*b for b in vector)) or 1)
            score = sum(a * b for a, b in zip(query_vector, vector)) / denominator
            scored.append({"document_id": chunk.document_id, "chunk_id": chunk.id, "content": chunk.content, "score": float(score), "metadata": chunk.metadata_json, "source": "Knowledge Base"})
        return sorted(scored, key=lambda item: item["score"], reverse=True)[: max(1, min(top_k, 20))]


def build_knowledge_service(settings: AppSettings, database: Database) -> KnowledgeService:
    provider = os.getenv("EMBEDDING_PROVIDER", "local_hash" if settings.security.demo_mode else "openai_compatible")
    if provider == "local_hash":
        embeddings: EmbeddingProvider = LocalHashEmbeddingProvider()
    else:
        key, base_url = os.getenv("EMBEDDING_API_KEY"), os.getenv("EMBEDDING_BASE_URL")
        if not key or not base_url:
            raise RuntimeError("EMBEDDING_API_KEY and EMBEDDING_BASE_URL are required")
        embeddings = OpenAICompatibleEmbeddingProvider(key, base_url, os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"), dimensions=384)
    return KnowledgeService(database, embeddings)
