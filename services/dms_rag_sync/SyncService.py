"""Synchronisation service.

Reads all documents from each DMS client, splits their text into chunks,
generates embeddings via an LLMClient, and upserts the resulting vectors
into each RAG backend with a generic metadata payload.
"""

import asyncio
import hashlib
import uuid

from shared.clients.dms.DMSClientInterface import DMSClientInterface
from shared.clients.dms.models.Document import DocumentHighDetails
from shared.clients.rag.RAGClientInterface import RAGClientInterface
from shared.clients.rag.models.VectorPoint import VectorPoint
from shared.clients.llm.LLMClientInterface import LLMClientInterface
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


def _compute_doc_hash(doc: DocumentHighDetails) -> str:
    """Compute a SHA-256 fingerprint over the fields that affect a document's vectors.

    Hashing content, title, owner, tags, correspondent, and document type means
    any change to these fields produces a different hash and triggers a re-sync.
    The hash is the same for every chunk of the same document.

    Args:
        doc (DocumentHighDetails): The enriched document to fingerprint.

    Returns:
        str: Hex-encoded SHA-256 digest.
    """
    parts = [
        doc.content or "",
        doc.title or "",
        str(doc.owner_id or ""),
        ",".join(sorted(str(t) for t in (doc.tag_ids or []))),
        str(doc.correspondent_id or ""),
        str(doc.document_type_id or ""),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _make_point_id(engine: str, doc_id: str, chunk_index: int) -> str:
    """Build a deterministic UUID5 point ID for a Qdrant vector.

    Using UUID5 ensures the same document chunk always maps to the same
    point ID so that re-syncing overwrites rather than duplicates.

    Args:
        engine (str): DMS engine identifier (e.g. "paperless").
        doc_id (str): Document ID in the DMS.
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
        embed_client: LLMClientInterface,
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

    async def do_incremental_sync(self, document_id: int) -> None:
        """Fetch and re-sync a single document identified by its DMS ID.

        Called by the webhook handler after Paperless-ngx signals that a document
        has been created or updated. The method re-fetches the document from every
        DMS client, resolves its metadata from the existing cache, builds a
        DocumentHighDetails object, and passes it to _sync_document with an empty
        rag_hashes dict so that the document is always re-embedded.

        Errors for individual DMS/RAG combinations are caught and logged so that
        the webhook can always return 202 Accepted.

        Args:
            document_id (int): DMS document ID to sync.
        """
        self.logging.info("Starting incremental sync for document id=%d...", document_id)
        sem = asyncio.Semaphore(DOC_CONCURRENCY)

        for dms_client in self._dms_clients:
            engine = dms_client.get_engine_name()
            try:
                # ensure reference caches are populated (no-op if already filled)
                await dms_client.fill_cache(force_refresh=False)

                # fetch fresh document details from the DMS
                doc_details = await dms_client.do_fetch_document_details(str(document_id))

                # resolve metadata from caches
                correspondent = None
                owner = None
                tags = []
                document_type = None

                if doc_details.correspondent_id and dms_client._cache_correspondents:
                    correspondent = dms_client._cache_correspondents.get(doc_details.correspondent_id)
                if doc_details.owner_id and dms_client._cache_owners:
                    owner = dms_client._cache_owners.get(doc_details.owner_id)
                if doc_details.tag_ids and dms_client._cache_tags:
                    for tag_id in doc_details.tag_ids:
                        tag = dms_client._cache_tags.get(tag_id)
                        if tag:
                            tags.append(tag)
                if doc_details.document_type_id and dms_client._cache_document_types:
                    document_type = dms_client._cache_document_types.get(doc_details.document_type_id)

                doc = DocumentHighDetails(
                    **doc_details.model_dump(),
                    correspondent=correspondent,
                    owner=owner,
                    tags=tags,
                    document_type=document_type,
                )
            except Exception as exc:
                self.logging.error(
                    "Incremental sync: failed to fetch/build document id=%d from DMS '%s': %s",
                    document_id, engine, exc,
                )
                continue

            for rag_client in self._rag_clients:
                try:
                    result = await self._sync_document(doc, rag_client, dms_client, sem, {})
                    if result:
                        self.logging.info(
                            "Incremental sync complete for document id=%d in DMS '%s' → RAG '%s'.",
                            document_id, engine, rag_client.get_engine_name(),
                        )
                    else:
                        self.logging.info(
                            "Incremental sync: document id=%d in DMS '%s' was skipped (no content or missing owner_id).",
                            document_id, engine,
                        )
                except Exception as exc:
                    self.logging.error(
                        "Incremental sync: failed to sync document id=%d to RAG '%s': %s",
                        document_id, rag_client.get_engine_name(), exc,
                    )

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

        # load existing content hashes from the RAG backend once before the sync loop
        rag_hashes = await self._load_rag_hashes(rag_client, engine)

        # process documents concurrently with bounded parallelism
        sem = asyncio.Semaphore(DOC_CONCURRENCY)
        results = await asyncio.gather(
            *[
                self._sync_document(doc, rag_client, dms_client, sem, rag_hashes)
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
        dms_ids = {doc.id for doc in enriched_docs}
        await self._cleanup_orphans(rag_client, engine, dms_ids)

    ##########################################
    ############ DOCUMENT SYNC ###############
    ##########################################

    async def _load_rag_hashes(
        self,
        rag_client: RAGClientInterface,
        engine: str,
    ) -> dict[str, str]:
        """Scroll the RAG backend once and build a {dms_doc_id: content_hash} map.

        Used before the sync loop so that unchanged documents can be skipped without
        hitting the embedding API. Only points that carry a non-None content_hash are
        included; points written by an older schema version without a hash are treated
        as unknown and will be re-synced on the next run.

        On any scroll error an empty dict is returned so that every document is treated
        as new — a safe fallback that avoids skipping documents due to a transient error.

        Args:
            rag_client (RAGClientInterface): The RAG client to query.
            engine (str): DMS engine identifier used as a scroll filter.

        Returns:
            dict[str, str]: Mapping of dms_doc_id → content_hash for all known points.
        """
        try:
            scroll_result = await rag_client.do_scroll_all(
                filters=[{"key": "dms_engine", "match": {"value": engine}}],
                with_payload=["dms_doc_id", "content_hash"],
                with_vector=False,
            )
        except Exception as exc:
            self.logging.error(
                "Failed to load RAG hashes for engine '%s': %s. All documents will be re-synced.",
                engine, exc,
            )
            return {}

        hashes: dict[str, str] = {}
        for point in scroll_result.result:
            payload = point.get("payload") or {}
            doc_id = payload.get("dms_doc_id")
            content_hash = payload.get("content_hash")
            if doc_id is not None and content_hash is not None:
                hashes[str(doc_id)] = content_hash
        return hashes

    async def _delete_document_vectors(
        self,
        rag_client: RAGClientInterface,
        engine: str,
        doc_id: str,
    ) -> None:
        """Delete all RAG vectors for a single document.

        Silently swallows errors after logging them so that callers can
        continue without raising.

        Args:
            rag_client (RAGClientInterface): The RAG client to delete from.
            engine (str): DMS engine identifier used in the filter.
            doc_id (str): Document ID whose vectors should be removed.
        """
        try:
            delete_filter = {
                "must": [
                    {"key": "dms_engine", "match": {"value": engine}},
                    {"key": "dms_doc_id", "match": {"value": doc_id}},
                ]
            }
            await rag_client.do_delete_points_by_filter(delete_filter)
        except Exception as exc:
            self.logging.error(
                "Failed to delete vectors for document id=%s: %s", doc_id, exc
            )

    async def _validate_document(
        self,
        doc: DocumentHighDetails,
        rag_client: RAGClientInterface,
        engine: str,
    ) -> list[str] | None:
        """Validate a document and return its text chunks if it is syncable.

        Performs all pre-sync checks in order. On the first failed check the
        existing RAG vectors for the document are deleted and ``None`` is
        returned so that ``_sync_document`` can exit early.

        Args:
            doc (DocumentHighDetails): The enriched document to validate.
            rag_client (RAGClientInterface): The RAG client used for cleanup on failure.
            engine (str): DMS engine identifier (used in delete filter and logging).

        Returns:
            list[str]: Non-empty list of text chunks when all checks pass.
            None: When any check fails (vectors already cleaned up).
        """
        # security invariant: documents without owner_id must never be indexed
        if not doc.owner_id:
            self.logging.warning(
                "Skipping document id=%s: missing owner_id (security invariant).", doc.id, color="yellow"
            )
            await self._delete_document_vectors(rag_client, engine, doc.id)
            return None

        # skip documents without OCR text
        if not doc.content or not doc.content.strip():
            self.logging.info("Skipping document id=%s ('%s'): no content.", doc.id, doc.title, color="yellow")
            await self._delete_document_vectors(rag_client, engine, doc.id)
            return None

        chunks = _split_text(doc.content)
        if not chunks:
            self.logging.info(
                "Skipping document id=%s ('%s'): content produced no chunks.", doc.id, doc.title, color="yellow"
            )
            await self._delete_document_vectors(rag_client, engine, doc.id)
            return None

        return chunks

    async def _sync_document(
        self,
        doc: DocumentHighDetails,
        rag_client: RAGClientInterface,
        dms_client: DMSClientInterface,
        sem: asyncio.Semaphore,
        rag_hashes: dict[str, str],
    ) -> bool:
        """Embed and upsert a single document's chunks into the RAG backend.

        Compares the document's content hash against the stored hash in the RAG
        backend. If they match the document is unchanged and embedding is skipped.

        Args:
            doc (DocumentHighDetails): The enriched document to sync.
            rag_client (RAGClientInterface): The RAG client to write to.
            dms_client (DMSClientInterface): Used for engine name in point IDs.
            sem (asyncio.Semaphore): Concurrency limiter.
            rag_hashes (dict[str, str]): Pre-loaded {dms_doc_id: content_hash} map.

        Returns:
            bool: True if synced successfully, False if skipped.

        Raises:
            Exception: Propagated to gather() if embedding or upsert fails.
        """
        async with sem:
            engine = dms_client.get_engine_name()

            chunks = await self._validate_document(doc, rag_client, engine)
            if chunks is None:
                return False

            current_hash = _compute_doc_hash(doc)
            if rag_hashes.get(str(doc.id)) == current_hash:
                self.logging.debug(
                    "Skipping document id=%s ('%s'): unchanged since last sync.", doc.id, doc.title
                )
                return False

            try:
                # batch embed — one HTTP request for all chunks of this document
                vectors = await self._embed_client.do_embed(texts=chunks)
            except Exception as exc:
                self.logging.error(
                    "Embedding failed for document id=%s ('%s'): %s", doc.id, doc.title, exc, color="red"
                )
                raise

            # delete stale chunks for this document before upserting the new ones
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
                    "Delete-before-upsert failed for document id=%s: %s", doc.id, exc, color="red"
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
                    content_hash=current_hash,
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
                    "Upsert failed for document id=%s: %s", doc.id, exc, color="red"
                )
                raise

            self.logging.info("Synced document id=%s ('%s'): %d chunks upserted.", doc.id, doc.title, len(points), color="green")
            return True

    ##########################################
    ############ ORPHAN CLEANUP ##############
    ##########################################

    async def _cleanup_orphans(
        self,
        rag_client: RAGClientInterface,
        engine: str,
        dms_ids: set[str],
    ) -> None:
        """Remove RAG vectors whose dms_doc_id no longer exists in the DMS.

        Scrolls only the points belonging to the given engine and deletes any
        whose dms_doc_id is absent from the current DMS document set.

        Args:
            rag_client (RAGClientInterface): The RAG client to clean up.
            engine (str): DMS engine identifier to scope the cleanup.
            dms_ids (set[str]): Set of valid dms_doc_ids currently in the DMS.
        """
        self.logging.info(
            "Starting orphan cleanup for engine '%s' (scrolling RAG for stale document IDs)...",
            engine,
        )

        rag_doc_ids: set[str] = set()
        try:
            scroll_result = await rag_client.do_scroll_all(
                filters=[{"key": "dms_engine", "match": {"value": engine}}],
                with_payload=["dms_doc_id"],
                with_vector=False,
            )
            for point in scroll_result.result:
                doc_id = (point.get("payload") or {}).get("dms_doc_id")
                if doc_id is not None:
                    rag_doc_ids.add(str(doc_id))
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
                    "Orphan cleanup: failed to delete vectors for engine='%s' dms_doc_id=%s: %s",
                    engine, orphan_id, exc,
                )

        self.logging.info("Orphan cleanup complete: removed vectors for %d document(s).", removed)
