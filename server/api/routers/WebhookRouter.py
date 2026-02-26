"""Webhook router for Paperless-ngx document events.

Paperless-ngx calls POST /webhook/document whenever a document is
added or updated. The handler triggers an incremental sync so the
Qdrant index stays current without waiting for the nightly cron.
"""

import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from shared.dependencies.auth import verify_api_key

webhook_router = APIRouter()


@webhook_router.post(
    "/webhook/document",
    dependencies=[Depends(verify_api_key)],
    tags=["Webhook"],
)
async def handle_document_webhook(request: Request) -> JSONResponse:
    """Handle a Paperless-ngx document-added or document-updated event.

    Triggers an incremental sync for the affected document as a
    fire-and-forget background task so the response is returned immediately.

    Args:
        request (Request): The incoming webhook payload from Paperless-ngx.

    Returns:
        JSONResponse: Acknowledgement with the received document_id.
    """
    body = await request.json()
    document_id = body.get("document_id")
    request.app.state.logging.info("Webhook received for document_id=%r", document_id)

    if document_id is not None:
        sync_service = request.app.state.sync_service
        asyncio.create_task(sync_service.do_incremental_sync(document_id))

    return JSONResponse(content={"status": "accepted", "document_id": document_id})
