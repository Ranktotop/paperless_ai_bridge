from pydantic import BaseModel


class ScrollResult(BaseModel):
    """Structured output of a single scroll page or a fully-collected scroll.

    Attributes:
        result:           List of point dicts returned by the scroll.
        status:           Backend status string (e.g. "ok").
        time:             Time taken by the backend to execute the request.
        next_page_offset: Cursor for the next page, or None when all pages
                          have been consumed. Always None on results returned
                          by do_scroll_all().
    """

    result: list[dict]
    status: str
    time: float
    next_page_offset: str | None = None