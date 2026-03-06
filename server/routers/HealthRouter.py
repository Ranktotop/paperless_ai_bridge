"""Health check router — no authentication required."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str


class DeepHealthResponse(BaseModel):
    status: str
    backends: dict[str, str]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Shallow health check — always returns 200 if the server is up.

    No authentication required. Intended for load balancers and Docker HEALTHCHECK.

    Returns:
        HealthResponse: {"status": "ok"}
    """
    return HealthResponse(status="ok")


@router.get("/health/deep", response_model=DeepHealthResponse)
async def health_deep(request: Request) -> DeepHealthResponse:
    """Deep health check — probes all configured backends.

    No authentication required.

    Returns:
        DeepHealthResponse: {"status": "ok"|"degraded", "backends": {name: "ok"|"error"}}
    """
    backends: dict[str, str] = {}
    overall = "ok"

    clients = [
        *request.app.state.dms_clients,
        *request.app.state.rag_clients,
        request.app.state.llm_client,
        request.app.state.cache_client,
    ]
    for client in clients:
        name = client.get_engine_name()
        try:
            result = await client.do_healthcheck()
            backends[name] = "ok" if result.is_success else "error"
            if not result.is_success:
                overall = "degraded"
        except Exception:
            backends[name] = "error"
            overall = "degraded"

    return DeepHealthResponse(status=overall, backends=backends)
