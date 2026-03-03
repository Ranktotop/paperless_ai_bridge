from fastapi import APIRouter, BackgroundTasks, Depends

from server.dependencies.auth import verify_api_key
from server.dependencies.services import get_sync_service
from server.models.requests import WebhookRequest
from services.dms_rag_sync.SyncService import SyncService

router = APIRouter(prefix="/webhook", tags=["webhook"], dependencies=[Depends(verify_api_key)])

@router.post("/{engine}/document")
async def webhook_document(
    engine: str,
    body: WebhookRequest,
    background_tasks: BackgroundTasks,
    sync_service: SyncService = Depends(get_sync_service),
) -> dict:
    """Accept a DMS document webhook and trigger an incremental sync for the given engine.

    Args:
        engine (str): DMS engine identifier from the URL path (e.g. "paperless").
        body (WebhookRequest): JSON body containing the document_id.
        background_tasks (BackgroundTasks): FastAPI background task queue.
        sync_service (SyncService): Injected sync service from app state.

    Returns:
        dict: Acknowledgement payload with status and document_id.
    """
    background_tasks.add_task(sync_service.do_incremental_sync, body.document_id, engine)
    return {"status": "accepted", "document_id": body.document_id}
