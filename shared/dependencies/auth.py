"""FastAPI authentication dependency."""

from fastapi import HTTPException, Request


async def verify_api_key(request: Request) -> None:
    """Verify the API key provided in the request header.

    Args:
        request (Request): The incoming FastAPI request.

    Raises:
        HTTPException: If the API key is missing or invalid (401).
    """
    config = request.app.state.config
    expected_key = config.get_string_val("APP_API_KEY")
    provided_key = request.headers.get("X-API-Key")
    if not provided_key or provided_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
