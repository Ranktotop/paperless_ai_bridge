"""Query router — natural language search against the Qdrant vector index."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from shared.dependencies.auth import verify_api_key
from shared.models.search import SearchRequest

query_router = APIRouter()


@query_router.post(
    "/query",
    dependencies=[Depends(verify_api_key)],
    tags=["Query"],
)
async def handle_query(request: Request, body: SearchRequest) -> JSONResponse:
    """Handle a natural language document search request.

    The owner_id in the request body determines which documents the user
    may access. This filter is enforced unconditionally by QueryService.

    Args:
        request (Request): The incoming FastAPI request (carries app state).
        body (SearchRequest): The parsed query with text and owner_id.

    Returns:
        JSONResponse: Ranked list of matching document chunks.

    Raises:
        HTTPException: 501 if the query service is not yet implemented.
    """
    request.app.state.logging.info(
        "Query received — owner_id=%d query=%r", body.owner_id, body.query[:80]
    )

    query_service = request.app.state.query_service
    if query_service is None:
        raise HTTPException(status_code=501, detail="Query service not yet implemented.")

    result = await query_service.do_query(body)
    return JSONResponse(content=result.model_dump())
