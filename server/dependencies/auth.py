from fastapi import Header, HTTPException, Request


async def verify_api_key(request: Request, x_api_key: str = Header(...)) -> None:
    """Verify the X-Api-Key header against the configured API key.

    Args:
        request (Request): The FastAPI request object (provides app.state).
        x_api_key (str): The value of the X-Api-Key header.

    Raises:
        HTTPException: 401 if the key is missing or does not match.
    """
    helper_config = request.app.state.helper_config
    expected_key = helper_config.get_string_val("API_SERVER_API_KEY")
    if x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
