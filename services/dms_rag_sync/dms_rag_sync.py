"""Sync runner entry point.

Mirrors Paperless-ngx OCR text into Qdrant for semantic search.
Run directly for a one-shot full sync, or invoke do_incremental_sync()
from the webhook handler for event-driven updates.

Usage:
    python -m sync.sync_runner
"""

import asyncio

from shared.clients.dms.DMSClientManager import DMSClientManager
from shared.clients.rag.RAGClientManager import RAGClientManager
from shared.clients.rag.RAGClientInterface import RAGClientInterface
from shared.clients.dms.DMSClientInterface import DMSClientInterface
from shared.clients.embed.EmbedClientManager import EmbedClientManager
from shared.clients.embed.EmbedClientInterface import EmbedClientInterface
from services.dms_rag_sync.SyncService import SyncService
from shared.helper.HelperConfig import HelperConfig
from shared.logging.logging_setup import setup_logging
logging = setup_logging()

async def main() -> None:
    """Run the full synchronisation pipeline."""
    logger = setup_logging()
    config = HelperConfig(logger=logger)
    dmsManager = DMSClientManager(helper_config=config)
    ragManager = RAGClientManager(helper_config=config)
    embedManager = EmbedClientManager(helper_config=config)

    # init clients
    dms_clients = dmsManager.get_clients()
    rag_clients = ragManager.get_clients()
    embed_client = embedManager.get_client()

    try:
        booted_dms_clients: list[DMSClientInterface] = []
        booted_rag_clients: list[RAGClientInterface] = []
        booted_embed_client: EmbedClientInterface | None = None

        # boot all clients
        ## embed client is required, if it fails to boot, we cannot continue, as there is no point in syncing without embedding. So we abort the whole process if embed client fails.
        try:
            await embed_client.boot()
            await embed_client.do_healthcheck()
            booted_embed_client = embed_client
        except Exception as e:
            logger.error(f"Error booting Embed client {embed_client.get_engine_name()}: {e}. Aborting.")
            return

        # dms clients. At least one dms client needs to boot successfully to continue, if all fail, we abort the process.
        for dms_client in dms_clients:
            try:
                await dms_client.boot()
                await dms_client.do_healthcheck()
                booted_dms_clients.append(dms_client)
            except Exception as e:
                logger.error(f"Error booting DMS client {dms_client.get_engine_name()}: {e}. Skipping this client.")
        if not booted_dms_clients:
            logger.error("No DMS clients booted successfully. Aborting.")
            return

        
        # rag clients. At least one rag client needs to boot successfully to continue, if all fail, we abort the process.
        for rag_client in rag_clients:
            try:
                await rag_client.boot()
                await rag_client.do_healthcheck()
                booted_rag_clients.append(rag_client)
            except Exception as e:
                logger.error(f"Error booting RAG client {rag_client.get_engine_name()}: {e}. Skipping this client.")
        if not booted_rag_clients:
            logger.error("No RAG clients booted successfully. Aborting.")
            return

        # create all rag collections, if not already existing
        for rag_client in booted_rag_clients:
            if not await rag_client.do_existence_check():
                await rag_client.do_create_collection()

        # init sync service and run full sync
        sync_service = SyncService(
            helper_config=config,
            dms_clients=booted_dms_clients,
            rag_clients=booted_rag_clients,
            embed_client=booted_embed_client
        )
        await sync_service.do_full_sync()
    finally:
        if embed_client:
            await embed_client.close()
        for dms_client in dms_clients:
            await dms_client.close()
        for rag_client in rag_clients:
            await rag_client.close()

if __name__ == "__main__":
    asyncio.run(main())