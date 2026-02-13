from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models import DataSource
from app.agents import process_news_article
from app.schemas import NewsArticleResponse

router = APIRouter(prefix="/process", tags=["processing"])


class ProcessRequest(BaseModel):
    """Request to process a URL"""
    url: str
    source_type: str  # 'website' or 'youtube'
    source_name: Optional[str] = None


class ProcessResponse(BaseModel):
    """Response from processing"""
    status: str
    message: str
    article_id: Optional[int] = None
    stage: str
    errors: list[str]
    timings: dict


@router.post("/url", response_model=ProcessResponse)
async def process_url(
    request: ProcessRequest,
    db: Session = Depends(get_db)
):
    """
    Process a URL through the full LangGraph workflow

    This endpoint will:
    1. Create or find a data source
    2. Scrape the content
    3. Analyze with LLM
    4. Extract stock mentions
    5. Save to database

    This is primarily for testing but can also be used for one-off article processing.
    """
    # Create temporary data source if needed
    source = db.query(DataSource).filter(DataSource.url == request.url).first()

    if not source:
        source = DataSource(
            name=request.source_name or f"Manual: {request.url[:50]}",
            url=request.url,
            source_type=request.source_type,
            status='active',
            health_status='pending'
        )
        db.add(source)
        db.commit()
        db.refresh(source)

    # Run the workflow
    result = await process_news_article(
        source_id=source.id,
        source_url=request.url,
        source_type=request.source_type
    )

    # Build response
    if result['status'] == 'success':
        # Find the article we just created
        from app.models import NewsArticle
        article = db.query(NewsArticle).filter(
            NewsArticle.content_hash == result['content_hash']
        ).first()

        return ProcessResponse(
            status='success',
            message=f"Successfully processed article: {result['title'][:100]}",
            article_id=article.id if article else None,
            stage=result['stage'],
            errors=result['errors'],
            timings=result['stage_timings']
        )
    elif result['status'] == 'skipped':
        return ProcessResponse(
            status='skipped',
            message="Article already exists (duplicate)",
            article_id=None,
            stage=result['stage'],
            errors=result['errors'],
            timings=result['stage_timings']
        )
    else:
        return ProcessResponse(
            status='error',
            message=f"Processing failed: {'; '.join(result['errors'])}",
            article_id=None,
            stage=result['stage'],
            errors=result['errors'],
            timings=result['stage_timings']
        )


@router.post("/trigger/{source_id}")
async def trigger_source_processing(
    source_id: int,
    db: Session = Depends(get_db)
):
    """
    Manually trigger processing for a data source

    This will fetch and process the content from the data source URL.
    """
    source = db.query(DataSource).filter(DataSource.id == source_id).first()

    if not source:
        raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")

    # Run the workflow
    result = await process_news_article(
        source_id=source.id,
        source_url=source.url,
        source_type=source.source_type
    )

    return {
        "source_id": source_id,
        "status": result['status'],
        "stage": result['stage'],
        "title": result.get('title', 'N/A'),
        "stock_count": len(result.get('stock_mentions', [])),
        "errors": result['errors'],
        "timings": result['stage_timings']
    }
