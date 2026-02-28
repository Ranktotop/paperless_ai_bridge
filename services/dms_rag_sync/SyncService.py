"""Synchronisation service.

Reads all documents from each DMS client, splits their text into chunks,
generates embeddings via an EmbedClient, and upserts the resulting vectors
into each RAG backend with a generic metadata payload.
"""

import asyncio
import uuid

from shared.clients.dms.DMSClientInterface import DMSClientInterface
from shared.clients.dms.models.Document import DocumentHighDetails
from shared.clients.rag.RAGClientInterface import RAGClientInterface
from shared.clients.rag.models.VectorPoint import VectorPoint
from shared.clients.embed.EmbedClientInterface import EmbedClientInterface
from shared.helper.HelperConfig import HelperConfig

CHUNK_SIZE = 1000       # characters per text chunk
CHUNK_OVERLAP = 100     # character overlap between consecutive chunks
UPSERT_BATCH_SIZE = 100 # max points per Qdrant upsert call
DOC_CONCURRENCY = 5     # max parallel document syncs


def _split_text(text: str) -> list[str]:
    """Split a document's OCR text into overlapping chunks.

    Args:
        text (str): The full document text.

    Returns:
        list[str]: Ordered list of text chunks.
    """
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - CHUNK_OVERLAP
    return chunks


def _make_point_id(engine: str, doc_id: int, chunk_index: int) -> str:
    """Build a deterministic UUID5 point ID for a Qdrant vector.

    Using UUID5 ensures the same document chunk always maps to the same
    point ID so that re-syncing overwrites rather than duplicates.

    Args:
        engine (str): DMS engine identifier (e.g. "paperless").
        doc_id (int): Document ID in the DMS.
        chunk_index (int): Zero-based chunk index within the document.

    Returns:
        str: UUID string usable as a Qdrant point ID.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f"{engine}:{doc_id}:{chunk_index}"))


class SyncService:
    """Orchestrates the full sync pipeline from DMSs to RAGs."""

    def __init__(
        self,
        helper_config: HelperConfig,
        dms_clients: list[DMSClientInterface],
        rag_clients: list[RAGClientInterface],
        embed_client: EmbedClientInterface,
    ) -> None:
        self.logging = helper_config.get_logger()
        self._dms_clients = dms_clients
        self._rag_clients = rag_clients
        self._embed_client = embed_client

    ##########################################
    ############### CORE SYNC ################
    ##########################################

    async def do_full_sync(self) -> None:
        """Sync all DMS clients to all RAG clients."""
        self.logging.info("Starting full sync...")

        for dms_client in self._dms_clients:
            for rag_client in self._rag_clients:
                await self.do_sync(rag_client, dms_client)

    async def do_sync(self, rag_client: RAGClientInterface, dms_client: DMSClientInterface) -> None:
        """Sync documents from a single DMS client to a single RAG client.

        Args:
            rag_client (RAGClientInterface): The RAG client to sync to.
            dms_client (DMSClientInterface): The DMS client to sync from.

        Raises:
            Exception: If any step in the sync process fails critically.
        """
        engine = dms_client.get_engine_name()
        self.logging.info("Syncing DMS '%s' → RAG '%s'", engine, rag_client.get_engine_name())

        # fill the dms cache (all reference data + enriched documents)
        await dms_client.fill_cache()

        enriched_docs = dms_client.get_enriched_documents()
        if not enriched_docs:
            self.logging.warning("No documents found in DMS cache for engine '%s'. Skipping.", engine)
            return

        self.logging.info("Processing %d documents from '%s'...", len(enriched_docs), engine)

        # process documents concurrently with bounded parallelism
        sem = asyncio.Semaphore(DOC_CONCURRENCY)
        results = await asyncio.gather(
            *[
                self._sync_document(doc, rag_client, dms_client, sem)
                for doc in enriched_docs
            ],
            return_exceptions=True,
        )

        synced = sum(1 for r in results if r is True)
        skipped = sum(1 for r in results if r is False)
        errors = sum(1 for r in results if isinstance(r, Exception))
        self.logging.info(
            "Sync complete for '%s': %d synced, %d skipped, %d errors.",
            engine, synced, skipped, errors,
        )

        # clean up orphaned vectors in the RAG backend
        dms_ids = {int(doc_id) for doc_id in enriched_docs}
        await self._cleanup_orphans(rag_client, engine, dms_ids)

    ##########################################
    ############ DOCUMENT SYNC ###############
    ##########################################

    async def _sync_document(
        self,
        doc: DocumentHighDetails,
        rag_client: RAGClientInterface,
        dms_client: DMSClientInterface,
        sem: asyncio.Semaphore,
    ) -> bool:
        """Embed and upsert a single document's chunks into the RAG backend.

        Args:
            doc (DocumentHighDetails): The enriched document to sync.
            rag_client (RAGClientInterface): The RAG client to write to.
            dms_client (DMSClientInterface): Used for engine name in point IDs.
            sem (asyncio.Semaphore): Concurrency limiter.

        Returns:
            bool: True if synced successfully, False if skipped.

        Raises:
            Exception: Propagated to gather() if embedding or upsert fails.
        """
        async with sem:
            # security invariant: skip documents without owner_id
            if not doc.owner_id:
                self.logging.warning(
                    "Skipping document id=%s: missing owner_id (security invariant).", doc.id
                )
                return False

            # skip documents without OCR text
            if not doc.content or not doc.content.strip():
                self.logging.info("Skipping document id=%s ('%s'): no content.", doc.id, doc.title)
                return False

            chunks = _split_text(doc.content)
            if not chunks:
                self.logging.info("Skipping document id=%s ('%s'): content produced no chunks.", doc.id, doc.title)
                return False

            try:
                # batch embed — one HTTP request for all chunks of this document
                vectors = await self._embed_client.do_embed(texts = chunks)
            except Exception as exc:
                self.logging.error(
                    "Embedding failed for document id=%s ('%s'): %s", doc.id, doc.title, exc
                )
                raise

            # delete stale chunks for this document before upserting the new ones
            engine = dms_client.get_engine_name()
            try:
                delete_filter = {
                    "must": [
                        {"key": "dms_engine", "match": {"value": engine}},
                        {"key": "dms_doc_id", "match": {"value": doc.id}},
                    ]
                }
                await rag_client.do_delete_points_by_filter(delete_filter)
            except Exception as exc:
                self.logging.error(
                    "Delete-before-upsert failed for document id=%s: %s", doc.id, exc
                )
                raise

            # build RAG points
            points: list[dict] = []
            for chunk_index, (chunk, vector) in enumerate(zip(chunks, vectors)):
                payload = VectorPoint(
                    dms_engine=engine,
                    dms_doc_id=doc.id,
                    chunk_index=chunk_index,
                    title=doc.title or "",
                    label_ids=doc.tag_ids,
                    category_id=doc.correspondent_id,
                    type_id=doc.document_type_id,
                    owner_id=doc.owner_id,
                    label_names=[t.name for t in (doc.tags or []) if t.name],
                    category_name=doc.correspondent.name if doc.correspondent else None,
                    type_name=doc.document_type.name if doc.document_type else None,
                    owner_username=doc.owner.username if doc.owner else None,
                    created=doc.created_date.isoformat() if doc.created_date else None,
                    chunk_text=chunk,
                )
                points.append({
                    "id": _make_point_id(engine, doc.id, chunk_index),
                    "vector": vector,
                    "payload": payload.model_dump(),
                })

            # upsert in batches to avoid oversized requests
            try:
                for batch_start in range(0, len(points), UPSERT_BATCH_SIZE):
                    batch = points[batch_start: batch_start + UPSERT_BATCH_SIZE]
                    await rag_client.do_upsert_points(batch)
            except Exception as exc:
                self.logging.error(
                    "Upsert failed for document id=%s: %s", doc.id, exc
                )
                raise

            self.logging.info(
                "Synced document id=%s ('%s'): %d chunks upserted.", doc.id, doc.title, len(points)
            )
            return True

    ##########################################
    ############ ORPHAN CLEANUP ##############
    ##########################################

    async def _cleanup_orphans(
        self,
        rag_client: RAGClientInterface,
        engine: str,
        dms_ids: set[int],
    ) -> None:
        """Remove RAG vectors whose dms_doc_id no longer exists in the DMS.

        Scrolls only the points belonging to the given engine and deletes any
        whose dms_doc_id is absent from the current DMS document set.

        Args:
            rag_client (RAGClientInterface): The RAG client to clean up.
            engine (str): DMS engine identifier to scope the cleanup.
            dms_ids (set[int]): Set of valid dms_doc_ids currently in the DMS.
        """
        self.logging.info(
            "Starting orphan cleanup for engine '%s' (scrolling RAG for stale document IDs)...",
            engine,
        )

        rag_doc_ids: set[int] = set()
        try:
            scroll_result = await rag_client.do_scroll(
                filters=[{"key": "dms_engine", "match": {"value": engine}}],
                with_payload=["dms_doc_id"],
                with_vector=False,
                limit=10000,
            )
            for point in scroll_result.result:
                doc_id = (point.get("payload") or {}).get("dms_doc_id")
                if doc_id is not None:
                    rag_doc_ids.add(int(doc_id))
        except Exception as exc:
            self.logging.error("Orphan cleanup scroll failed: %s. Skipping cleanup.", exc)
            return

        orphan_ids = rag_doc_ids - dms_ids
        if not orphan_ids:
            self.logging.info("Orphan cleanup: no stale documents found.")
            return

        self.logging.info("Orphan cleanup: removing vectors for %d stale document(s).", len(orphan_ids))
        removed = 0
        for orphan_id in orphan_ids:
            try:
                delete_filter = {
                    "must": [
                        {"key": "dms_engine", "match": {"value": engine}},
                        {"key": "dms_doc_id", "match": {"value": orphan_id}},
                    ]
                }
                await rag_client.do_delete_points_by_filter(delete_filter)
                removed += 1
            except Exception as exc:
                self.logging.error(
                    "Orphan cleanup: failed to delete vectors for engine='%s' dms_doc_id=%d: %s",
                    engine, orphan_id, exc,
                )

        self.logging.info("Orphan cleanup complete: removed vectors for %d document(s).", removed)
