from fastapi import APIRouter, BackgroundTasks, Depends, Request

from server.dependencies.auth import verify_api_key
from server.models.requests import WebhookRequest

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/document")
async def webhook_document(
    request: Request,
    body: WebhookRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(verify_api_key),
) -> dict:
    """Accept a Paperless-ngx document webhook and trigger an incremental sync.

    Args:
        request (Request): FastAPI request (provides app.state.sync_service).
        body (WebhookRequest): JSON body containing the document_id.
        background_tasks (BackgroundTasks): FastAPI background task queue.
        _ (None): Auth dependency result (unused).

    Returns:
        dict: Acknowledgement payload with status and document_id.
    """
    sync_service = request.app.state.sync_service
    background_tasks.add_task(sync_service.do_incremental_sync, body.document_id)
    return {"status": "accepted", "document_id": body.document_id}
