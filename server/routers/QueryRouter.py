from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from server.dependencies.auth import verify_api_key
from server.dependencies.services import get_search_service, get_user_mapping_service, get_dms_clients
from server.models.requests import SearchRequest
from server.user_mapping.UserMappingService import UserMappingService
from services.rag_search.SearchService import SearchService
from shared.clients.dms.DMSClientInterface import DMSClientInterface
from services.rag_search.helper.IdentityHelper import IdentityHelper
from shared.clients.rag.models.Point import PointHighDetails, PointDetails, PointsSearchResponse

router = APIRouter(prefix="/query", tags=["query"], dependencies=[Depends(verify_api_key)])


@router.post("/{frontend}")
async def query_documents(
    frontend: str,
    body: SearchRequest,
    search_service: SearchService = Depends(get_search_service),
    user_mapping_service: UserMappingService = Depends(get_user_mapping_service),
    dms_clients: list[DMSClientInterface] = Depends(get_dms_clients),
) -> PointsSearchResponse:
    """Execute a semantic search query against the RAG backend.

    Resolves the frontend user_id against every configured DMS engine via
    UserMappingService, collecting all (owner_id, engine) pairs for this user.
    The search then covers documents from all matched engines simultaneously.
    Returns HTTP 403 if the user_id has no mapping in any configured engine.

    Args:
        frontend: AI system identifier from the URL path (e.g. "openwebui").
        body: JSON body with query, user_id, limit, and optional chat_history.
        dms_clients: Injected list of DMS clients — one per configured engine.
        search_service: Injected search service from app state.
        user_mapping_service: Injected mapping service from app state.

    Returns:
        PointsSearchResponse: Matching document chunks with metadata.
    """
    # Resolve user_id for every configured DMS engine
    identity_helper = IdentityHelper(user_mapping_service=user_mapping_service, dms_clients=dms_clients, frontend=frontend, user_id=body.user_id)
    if not identity_helper.has_mappings():
        raise HTTPException(
            status_code=403,
            detail="No mapping found for frontend '%s', user_id '%s' in any configured engine."
            % (frontend, body.user_id),
        )

    results: list[PointHighDetails] = await search_service.do_search(
        query=body.query, 
        identity_helper=identity_helper,
        chat_history=body.chat_history,
        limit=body.limit
    )
    return PointsSearchResponse(
        query=body.query,
        points=[PointDetails(**r.model_dump()) for r in results],
        total=len(results),
    )
