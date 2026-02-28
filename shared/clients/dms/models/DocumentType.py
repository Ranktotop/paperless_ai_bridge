from datetime import datetime
"""Generic DMS Tag model — backend-independent."""

from pydantic import BaseModel

class DocumentTypeBase(BaseModel):
    """
    Represents a single Document Type with all its metadata, as returned by a DMS client.
    """
    engine:str
    id: int

class DocumentTypeDetails(DocumentTypeBase):
    """
    Represents a single Document Type with all its metadata, as returned by a DMS client.
    """
    name: str | None = None
    slug: str | None = None
    owner_id : int | None = None
    documents: int | None = None

class DocumentTypesListResponse(BaseModel):
    """
    Represents the response from a DMS when fetching a list of Document Types.
    """
    engine:str
    types : list[DocumentTypeBase] = []
    currentPage: int
    nextPage: int | None = None
    previousPage: int | None = None
    overallCount: int | None = None
    pageLength: int | None = None
    lastPage: int | None = None
