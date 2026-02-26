"""Synchronisation service.

Reads all documents from Paperless-ngx, splits their OCR text into chunks,
generates embeddings via an EmbedInterface client, and upserts the resulting
vectors into Qdrant with a full metadata payload.
"""

from shared.clients.DMSInterface import DMSInterface
from shared.clients.EmbedInterface import EmbedInterface
from shared.clients.VectorDBInterface import VectorDBInterface
from shared.helper.config_helper import HelperConfig
from shared.models.document import Document

CHUNK_SIZE = 1000     # characters per text chunk
CHUNK_OVERLAP = 100   # character overlap between consecutive chunks


class SyncService:
    """Orchestrates the full sync pipeline from Paperless-ngx to Qdrant."""

    def __init__(
        self,
        helper_config: HelperConfig,
        paperless_client: DMSInterface,
        qdrant_client: VectorDBInterface,
        embed_client: EmbedInterface,
    ) -> None:
        self.logging = helper_config.get_logger()
        self._paperless = paperless_client
        self._qdrant = qdrant_client
        self._embed_client = embed_client

    ##########################################
    ############### CORE SYNC ################
    ##########################################

    async def do_full_sync(self) -> None:
        """Fetch all documents from Paperless-ngx and upsert them into Qdrant."""
        self.logging.info("Starting full sync...")
        page = 1
        total_synced = 0

        while True:
            self.logging.info("Fetching page %d from Paperless-ngx...", page)
            response = await self._paperless.get_documents_page(page=page)
            results = response.get("results", [])

            if not results:
                break

            for raw_doc in results:
                doc = await self._paperless.get_document(raw_doc["id"])
                await self._sync_document(doc)
                total_synced += 1

            if not response.get("next"):
                break
            page += 1

        self.logging.info("Full sync complete. Documents synced: %d", total_synced)

    async def do_incremental_sync(self, document_id: int) -> None:
        """Fetch and upsert a single document by ID.

        Called by the webhook handler when Paperless-ngx reports a new
        or updated document.

        Args:
            document_id (int): The DMS document ID to sync.
        """
        self.logging.info("Incremental sync for document_id=%d", document_id)
        doc = await self._paperless.get_document(document_id)
        await self._sync_document(doc)
        self.logging.info("Incremental sync complete for document_id=%d", document_id)

    ##########################################
    ############### HELPERS ##################
    ##########################################

    async def _sync_document(self, doc: Document) -> None:
        """Vectorise and upsert a single document's text chunks into Qdrant.

        Args:
            doc (Document): The document to process.
        """
        if not doc.content:
            self.logging.debug("Skipping document %d — no content.", doc.id)
            return

        if doc.owner_id is None:
            self.logging.warning("Skipping document %d — owner_id is None.", doc.id)
            return

        await self._qdrant.do_delete_by_document(doc.id)

        chunks = self._split_text(doc.content)
        self.logging.debug(
            "Syncing document %d (%r): %d chunk(s).", doc.id, doc.title[:60], len(chunks)
        )

        for index, chunk in enumerate(chunks):
            vector = await self._embed(chunk)
            payload = self._paperless.build_vector_payload(doc, index, chunk)
            await self._qdrant.do_upsert(vector=vector, payload=payload)

    def _split_text(self, text: str) -> list[str]:
        """Split text into overlapping chunks.

        Args:
            text (str): The full document text.

        Returns:
            list[str]: Ordered list of text chunks.
        """
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE
            chunks.append(text[start:end])
            start += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks

    async def _embed(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text.

        Args:
            text (str): The text to embed.

        Returns:
            list[float]: The embedding vector.

        Raises:
            Exception: If the embedding request fails.
        """
        return await self._embed_client.embed_text(text)
