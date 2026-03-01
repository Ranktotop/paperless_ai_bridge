"""VectorPoint model — generic metadata stored alongside each vector chunk in a RAG backend."""

from pydantic import BaseModel


class VectorPoint(BaseModel):
    """Generic metadata payload stored alongside each vector chunk in a RAG backend.

    Designed to be DMS-agnostic. All field names reflect general document
    concepts, not the terminology of any specific DMS (e.g. Paperless-ngx).

    The owner_id field is mandatory and enforced as a security invariant on
    every upsert and search operation — it must never be absent or None.

    Attributes:
        dms_engine:       Identifier of the source DMS (e.g. "paperless").
        dms_doc_id:       Document ID as assigned by the source DMS.
        chunk_index:      Zero-based position of this chunk within the document.
        title:            Human-readable document title.
        owner_id:         MANDATORY — user ID in the DMS; used for access isolation.
        created:          ISO-8601 creation date of the document, if available.
        chunk_text:       Raw text content of this chunk.
        label_ids:        IDs of labels/tags attached to the document.
        label_names:      Human-readable names of those labels/tags.
        category_id:      ID of the document category (e.g. correspondent).
        category_name:    Human-readable name of the category.
        type_id:          ID of the document type classification.
        type_name:        Human-readable name of the document type.
        owner_username:   Username of the document owner, for display purposes.
        content_hash:     SHA-256 hex digest of the document's content and key metadata.
                          Identical across all chunks of the same document.
                          Used to skip re-embedding unchanged documents on subsequent syncs.
    """

    # Core identity
    dms_engine: str
    dms_doc_id: str
    chunk_index: int
    title: str

    # Security invariant — never None
    owner_id: str

    # Temporal metadata
    created: str | None = None

    # Chunk content
    chunk_text: str | None = None

    # Generic label / tag fields — used for hard metadata filtering
    label_ids: list[str] = []
    label_names: list[str] = []

    # Generic category field (e.g. correspondent in Paperless)
    category_id: str | None = None
    category_name: str | None = None

    # Generic type classification field (e.g. document_type in Paperless)
    type_id: str | None = None
    type_name: str | None = None

    # Owner display name
    owner_username: str | None = None

    # Change detection — SHA-256 over content + key metadata (document-wide, not per-chunk)
    content_hash: str | None = None
