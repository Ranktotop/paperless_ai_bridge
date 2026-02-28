from datetime import datetime
"""Generic DMS Correspondent model — backend-independent."""

from pydantic import BaseModel

class CorrespondentBase(BaseModel):
    """
    Represents a single Correspondent with all its metadata, as returned by a DMS client.
    """
    engine:str
    id: int

class CorrespondentDetails(CorrespondentBase):
    """
    Represents a single Correspondent with all its metadata, as returned by a DMS client.
    """
    name: str | None = None
    slug: str | None = None
    owner_id : int | None = None
    documents: int | None = None

class CorrespondentsListResponse(BaseModel):
    """
    Represents the response from a DMS when fetching a list of Correspondents.
    """
    engine:str
    correspondents : list[CorrespondentBase] = []
    currentPage: int
    nextPage: int | None = None
    previousPage: int | None = None
    overallCount: int | None = None
    pageLength: int | None = None
    lastPage: int | None = None
