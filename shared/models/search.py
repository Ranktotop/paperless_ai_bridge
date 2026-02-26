"""Pydantic models for search requests and responses."""

from pydantic import BaseModel


class SearchRequest(BaseModel):
    """Incoming natural language search query from the frontend."""

    query: str
    owner_id: int
    limit: int = 5


class SearchResultItem(BaseModel):
    """A single document result returned from the Qdrant index."""

    paperless_id: int
    title: str
    score: float
    chunk_text: str | None = None


class SearchResponse(BaseModel):
    """Response payload returned to the frontend after a search."""

    query: str
    results: list[SearchResultItem]
    total: int
