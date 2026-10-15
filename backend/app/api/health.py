from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness check + which providers are configured (never the keys themselves)."""
    return {
        "status": "ok",
        "environment": settings.environment,
        "openai_configured": bool(settings.openai_api_key),
        "openrouter_configured": bool(settings.openrouter_api_key),
    }
