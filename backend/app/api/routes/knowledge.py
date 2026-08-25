from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from ..dependencies import get_current_user_id

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    document_id: str | None = None


def dump(item):
    return {"id": item.id, "filename": item.filename, "media_type": item.media_type, "status": item.status, "checksum": item.checksum, "metadata": item.metadata_json, "created_at": item.created_at.isoformat()}


@router.post("/documents")
async def upload_document(request: Request, file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)):
    content = await file.read(10 * 1024 * 1024 + 1)
    item = await request.app.state.knowledge.ingest(user_id, file.filename or "document.txt", content)
    return {"success": True, "data": dump(item), "meta": {}}


@router.get("/documents")
async def list_documents(request: Request, user_id: str = Depends(get_current_user_id)):
    items = await request.app.state.knowledge.list_documents(user_id)
    return {"success": True, "data": [dump(item) for item in items], "meta": {"count": len(items)}}


@router.get("/documents/{document_id}")
async def get_document(document_id: str, request: Request, user_id: str = Depends(get_current_user_id)):
    item = await request.app.state.knowledge.get_document(user_id, document_id)
    if not item: raise HTTPException(404, "Document not found")
    return {"success": True, "data": dump(item), "meta": {}}


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, request: Request, user_id: str = Depends(get_current_user_id)):
    if not await request.app.state.knowledge.delete_document(user_id, document_id): raise HTTPException(404, "Document not found")
    return {"success": True, "data": {"deleted": True}, "meta": {}}


@router.post("/search")
async def search(body: SearchRequest, request: Request, user_id: str = Depends(get_current_user_id)):
    items = await request.app.state.knowledge.search(user_id, body.query, body.top_k, body.document_id)
    return {"success": True, "data": items, "meta": {"count": len(items)}}
