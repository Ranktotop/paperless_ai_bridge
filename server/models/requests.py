from pydantic import BaseModel


class WebhookRequest(BaseModel):
    document_id: int


class SearchRequest(BaseModel):
    query: str
    owner_id: int
    limit: int = 5
