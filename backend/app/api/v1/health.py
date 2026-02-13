from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
import httpx

from app.database import get_db
from app.config import settings
from app.models import DataSource, NewsArticle
from app.schemas import HealthCheckResponse, SystemStatusResponse

router = APIRouter(tags=["health"])


async def check_ollama_health() -> str:
    """Check if Ollama is accessible"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.OLLAMA_HOST}/api/tags")
            if response.status_code == 200:
                return "healthy"
            return "error"
    except Exception:
        return "unavailable"


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    # Check database
    try:
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception:
        db_status = "error"

    # Check Ollama
    ollama_status = await check_ollama_health()

    overall_status = "healthy" if db_status == "healthy" and ollama_status == "healthy" else "degraded"

    return HealthCheckResponse(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat(),
        database=db_status,
        ollama=ollama_status
    )


@router.get("/status", response_model=SystemStatusResponse)
async def system_status(db: Session = Depends(get_db)):
    """Get system status"""
    active_sources = db.query(DataSource).filter(DataSource.status == 'active').count()
    paused_sources = db.query(DataSource).filter(DataSource.status == 'paused').count()
    total_articles = db.query(NewsArticle).count()

    # Check Ollama
    ollama_status = await check_ollama_health()

    return SystemStatusResponse(
        active_sources=active_sources,
        paused_sources=paused_sources,
        total_articles=total_articles,
        processing_queue_size=0,  # TODO: Get actual queue size from scheduler
        global_pause=settings.GLOBAL_PAUSE,
        ollama_status=ollama_status
    )
