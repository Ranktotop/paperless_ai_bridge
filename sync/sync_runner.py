"""Sync runner entry point.

Mirrors Paperless-ngx OCR text into Qdrant for semantic search.
Run directly for a one-shot full sync, or invoke do_incremental_sync()
from the webhook handler for event-driven updates.

Usage:
    python -m sync.sync_runner
"""

import asyncio

from shared.clients.DMSPaperless import DMSPaperless
from shared.clients.EmbedClientOllama import EmbedClientOllama
from shared.clients.VectorDBQdrant import VectorDBQdrant
from shared.helper.config_helper import HelperConfig
from shared.logging.logging_setup import setup_logging
from sync.services.SyncService import SyncService


async def main() -> None:
    """Run the full synchronisation pipeline."""
    logger = setup_logging()
    config = HelperConfig(logger=logger)

    paperless_client = DMSPaperless(helper_config=config)
    qdrant_client = VectorDBQdrant(helper_config=config)
    embed_client = EmbedClientOllama(helper_config=config)
    sync_service = SyncService(
        helper_config=config,
        paperless_client=paperless_client,
        qdrant_client=qdrant_client,
        embed_client=embed_client,
    )

    try:
        await paperless_client.boot()
        await qdrant_client.boot()
        await embed_client.boot()
        await paperless_client.do_healthcheck()
        await qdrant_client.do_healthcheck()

        # Ensure collection exists before syncing
        collection = qdrant_client.get_collection()
        if not await qdrant_client.do_existence_check(collection):
            await qdrant_client.do_create_collection(collection)

        await sync_service.do_full_sync()
    finally:
        await paperless_client.close()
        await qdrant_client.close()
        await embed_client.close()


if __name__ == "__main__":
    asyncio.run(main())