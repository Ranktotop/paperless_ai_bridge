from fastapi import APIRouter, Depends, Request

from server.dependencies.auth import verify_api_key
from server.models.requests import SearchRequest
from server.models.responses import SearchResponse

router = APIRouter(prefix="/query", tags=["query"])


@router.post("")
async def query_documents(
    request: Request,
    body: SearchRequest,
    _: None = Depends(verify_api_key),
) -> SearchResponse:
    """Execute a semantic search query against the RAG backend.

    Args:
        request (Request): FastAPI request (provides app.state.query_service).
        body (SearchRequest): JSON body with query string, owner_id, and limit.
        _ (None): Auth dependency result (unused).

    Returns:
        SearchResponse: Matching document chunks with metadata.
    """
    query_service = request.app.state.query_service
    return await query_service.search(body)
