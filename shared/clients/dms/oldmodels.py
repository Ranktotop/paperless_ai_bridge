"""Generic DMS document model — backend-independent."""

from pydantic import BaseModel
import datetime


class DMSDocument(BaseModel):
    """Generic document returned by any DMS client implementation.

    All name fields are resolved by the client before this object is created —
    the rest of the application never deals with raw foreign-key IDs alone.

    ID fields are retained alongside names for hard metadata filtering in
    Qdrant.  They may be None or empty for DMS backends that have no equivalent
    concept (e.g. a system without a correspondent notion).
    """

    engine:str
    id: int
    title: str
    content: str
    owner_id: int | None = None
    created: datetime.datetime | None = None

    # Resolved human-readable names (populated by the DMS client)
    correspondent_name: str | None = None
    document_type_name: str | None = None
    tag_names: list[str]| None = None
    owner_username: str | None = None

    # Raw IDs kept for RAG metadata filtering
    correspondent_id: int | None = None
    document_type_id: int | None = None
    tag_ids: list[int] | None = None
