from datetime import datetime
"""Generic DMS Owner model — backend-independent."""

from pydantic import BaseModel

class OwnerBase(BaseModel):
    """
    Represents a single Owner with all its metadata, as returned by a DMS client.
    """
    engine:str
    id: int

class OwnerDetails(OwnerBase):
    """
    Represents a single Owner with all its metadata, as returned by a DMS client.
    """
    username: str | None = None
    email: str | None = None
    firstname : str | None = None
    lastname : str | None = None

class OwnersListResponse(BaseModel):
    """
    Represents the response from a DMS when fetching a list of Owners.
    """
    engine:str
    owners : list[OwnerBase] = []
    currentPage: int
    nextPage: int | None = None
    previousPage: int | None = None
    overallCount: int | None = None
    pageLength: int | None = None
    lastPage: int | None = None
