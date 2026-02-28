from datetime import datetime
"""Generic DMS Tag model — backend-independent."""

from pydantic import BaseModel

class TagBase(BaseModel):
    """
    Represents a single Tag with all its metadata, as returned by a DMS client.
    """
    engine:str
    id: int

class TagDetails(TagBase):
    """
    Represents a single Tag with all its metadata, as returned by a DMS client.
    """
    name: str | None = None
    slug: str | None = None
    owner_id : int | None = None
    documents: int | None = None

class TagsListResponse(BaseModel):
    """
    Represents the response from a DMS when fetching a list of Tags.
    """
    engine:str
    tags : list[TagBase] = []
    currentPage: int
    nextPage: int | None = None
    previousPage: int | None = None
    overallCount: int | None = None
    pageLength: int | None = None
    lastPage: int | None = None
