"""Pydantic models for document data.

Hierarchy:
  Document           — generic, backend-independent document contract.
  PaperlessDocument  — Paperless-ngx concrete subclass with additional metadata.
  VectorPayload      — payload stored alongside each vector chunk in Qdrant.
"""

from pydantic import BaseModel


class Document(BaseModel):
    """Generic document representation — backend-independent.

    Defines the minimum contract that any DMS implementation must fulfil.
    DMSInterface uses this type so the interface stays decoupled from any
    concrete DMS backend.
    """

    id: int
    title: str
    content: str
    owner_id: int | None = None
    created: str | None = None
    added: str | None = None


class PaperlessDocument(Document):
    """Paperless-ngx document with additional metadata fields.

    Extends Document with Paperless-specific fields that carry over into
    the Qdrant payload for metadata-filtered search.
    """

    tag_ids: list[int] = []
    correspondent_id: int | None = None
    document_type_id: int | None = None


class VectorPayload(BaseModel):
    """Metadata stored alongside each vector chunk in Qdrant.

    The owner_id field is mandatory and enforced as a security invariant
    on every upsert and search operation.
    """

    paperless_id: int
    chunk_index: int
    title: str
    tag_ids: list[int] = []
    correspondent_id: int | None = None
    document_type_id: int | None = None
    owner_id: int
    created: str | None = None
    chunk_text: str | None = None
