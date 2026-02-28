
from pydantic import BaseModel
class ScrollResult(BaseModel):
    """Structured output of the scroll request."""
    result: list[dict]
    status: str
    time: float