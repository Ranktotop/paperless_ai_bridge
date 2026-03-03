from pydantic import BaseModel


class WebhookRequest(BaseModel):
    document_id: int


class SearchRequest(BaseModel):
    query: str
    user_id: str
    limit: int = 10
    chat_history: list[dict] = []
