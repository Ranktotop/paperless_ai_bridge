"""FastAPI application entry point for the AI-Bridge API."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from server.api.routers.QueryRouter import query_router
from server.api.routers.WebhookRouter import webhook_router
from server.api.services.QueryService import QueryService
from shared.clients.dms.paperless.DMSClientPaperless import DMSClientPaperless
from shared.clients.EmbedClientOllama import EmbedClientOllama
from shared.clients.VectorDBQdrant import VectorDBQdrant
from shared.helper.HelperConfig import HelperConfig
from shared.logging.logging_setup import setup_logging
from sync.services.SyncService import SyncService

logging = setup_logging()
app_version = os.getenv("APP_VERSION", "unknown")

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown."""
    app.state.logging = setup_logging()
    app.state.config = HelperConfig(logger=app.state.logging)

    # Initialise clients
    paperless_client = DMSClientPaperless(helper_config=app.state.config)
    qdrant_client = VectorDBQdrant(helper_config=app.state.config)
    embed_client = EmbedClientOllama(helper_config=app.state.config)
    await paperless_client.boot()
    await qdrant_client.boot()
    await embed_client.boot()

    # Health checks
    await paperless_client.do_healthcheck()
    await qdrant_client.do_healthcheck()

    # Ensure Qdrant collection exists
    collection = qdrant_client.get_collection()
    if not await qdrant_client.do_existence_check(collection):
        await qdrant_client.do_create_collection(collection)
    else:
        app.state.logging.info("Qdrant collection %r already exists.", collection)

    # Wire up services
    app.state.sync_service = SyncService(
        helper_config=app.state.config,
        paperless_client=paperless_client,
        qdrant_client=qdrant_client,
        embed_client=embed_client,
    )
    app.state.query_service = QueryService(
        helper_config=app.state.config,
        qdrant_client=qdrant_client,
        embed_client=embed_client,
    )

    app.state.logging.info("AI-Bridge API ready.")
    yield

    # Shutdown
    await paperless_client.close()
    await qdrant_client.close()
    await embed_client.close()
    app.state.logging.info("AI-Bridge API shut down.")


app = FastAPI(
    title="Paperless AI Bridge",
    description="Intelligent middleware between Paperless-ngx and AI frontends.",
    version=app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router)
app.include_router(query_router)


# Server Start
if __name__ == "__main__":
    # start server
    import uvicorn
    logging.info(f"Starting AI-Bridge API Server v{app_version} from root dir: {os.environ['ROOT_DIR']} on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)