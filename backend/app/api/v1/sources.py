from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import json
import asyncio

from app.database import get_db
from app.models import DataSource
from app.schemas import (
    DataSourceCreate,
    DataSourceUpdate,
    DataSourceStatusUpdate,
    DataSourceResponse,
    DataSourceListResponse,
)

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("/", response_model=DataSourceListResponse)
async def list_sources(
    skip: int = 0,
    limit: int = 100,
    status_filter: str = None,
    db: Session = Depends(get_db)
):
    """List all data sources"""
    query = db.query(DataSource)

    # Filter out deleted sources by default
    query = query.filter(DataSource.status != 'deleted')

    if status_filter:
        query = query.filter(DataSource.status == status_filter)

    total = query.count()
    sources = query.offset(skip).limit(limit).all()

    return DataSourceListResponse(
        sources=sources,
        total=total
    )


@router.post("/", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    source: DataSourceCreate,
    db: Session = Depends(get_db)
):
    """Create a new data source"""
    # Check if URL already exists
    existing = db.query(DataSource).filter(DataSource.url == source.url).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Data source with URL {source.url} already exists"
        )

    # Create new source
    db_source = DataSource(
        **source.model_dump(),
        status='active',
        health_status='pending',
        error_count=0
    )

    db.add(db_source)
    db.commit()
    db.refresh(db_source)

    # Add to scheduler
    from app.scheduler import scheduler_service
    scheduler_service.add_source_job(db_source)

    return db_source


@router.get("/{source_id}", response_model=DataSourceResponse)
async def get_source(
    source_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific data source by ID"""
    source = db.query(DataSource).filter(DataSource.id == source_id).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source {source_id} not found"
        )

    return source


@router.put("/{source_id}", response_model=DataSourceResponse)
async def update_source(
    source_id: int,
    source_update: DataSourceUpdate,
    db: Session = Depends(get_db)
):
    """Update a data source"""
    source = db.query(DataSource).filter(DataSource.id == source_id).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source {source_id} not found"
        )

    # Update fields
    update_data = source_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(source, field, value)

    source.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(source)

    # Update scheduler job if schedule changed
    if 'fetch_frequency_minutes' in update_data or 'cron_expression' in update_data:
        from app.scheduler import scheduler_service
        scheduler_service.add_source_job(source)  # This replaces existing job

    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: int,
    db: Session = Depends(get_db)
):
    """Delete a data source (soft delete)"""
    source = db.query(DataSource).filter(DataSource.id == source_id).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source {source_id} not found"
        )

    # Soft delete
    source.status = 'deleted'
    source.updated_at = datetime.utcnow()

    db.commit()

    # Remove from scheduler
    from app.scheduler import scheduler_service
    scheduler_service.remove_source_job(source_id)


@router.patch("/{source_id}/status", response_model=DataSourceResponse)
async def update_source_status(
    source_id: int,
    status_update: DataSourceStatusUpdate,
    db: Session = Depends(get_db)
):
    """Update data source status (active/paused)"""
    source = db.query(DataSource).filter(DataSource.id == source_id).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source {source_id} not found"
        )

    source.status = status_update.status
    source.updated_at = datetime.utcnow()

    # Reset error count when re-activating
    if status_update.status == 'active':
        source.error_count = 0

    db.commit()
    db.refresh(source)

    # Update scheduler
    from app.scheduler import scheduler_service
    if status_update.status == 'active':
        scheduler_service.add_source_job(source)
    else:
        scheduler_service.remove_source_job(source_id)

    return source


@router.get("/{source_id}/test")
async def test_source(
    source_id: int,
    db: Session = Depends(get_db)
):
    """Test a data source with Server-Sent Events (SSE) for progress updates"""
    source = db.query(DataSource).filter(DataSource.id == source_id).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source {source_id} not found"
        )

    async def event_generator():
        """Generate Server-Sent Events with progress updates"""
        try:
            # Import here to avoid circular dependency
            from app.agents.workflow import app as workflow_app
            from app.agents.state import NewsProcessingState
            import time

            # Send initial event
            yield f"data: {json.dumps({'type': 'init', 'message': 'Initializing workflow...'})}\n\n"

            # Initialize state
            initial_state: NewsProcessingState = {
                'source_id': source.id,
                'source_url': source.url,
                'source_type': source.source_type,
                'extraction_instructions': source.extraction_instructions,
                'raw_content': None,
                'raw_html': None,
                'video_path': None,
                'transcript': None,
                'metadata': {},
                'is_listing_page': False,
                'article_links': [],
                'current_article_index': 0,
                'processed_articles': [],
                'title': '',
                'content': '',
                'summary': None,
                'main_topic': None,
                'author': None,
                'published_date': None,
                'is_high_impact': False,
                'stock_mentions': [],
                'content_hash': '',
                'stage': 'init',
                'errors': [],
                'status': '',
                'start_time': time.time(),
                'stage_timings': {}
            }

            # Stream workflow events
            last_stage = ''
            total_articles = 0
            current_article = 0
            final_state = None

            async for event in workflow_app.astream(initial_state):
                # Extract node name and state from event
                for node_name, node_state in event.items():
                    final_state = node_state  # Keep updating with latest state
                    stage = node_state.get('stage', '')

                    # Update article counts
                    if node_state.get('is_listing_page'):
                        total_articles = len(node_state.get('article_links', []))
                        current_article = node_state.get('current_article_index', 0)

                    # Only send update if stage changed
                    if stage != last_stage:
                        last_stage = stage

                        # Map stages to user-friendly messages
                        stage_messages = {
                            'scraped': 'Loading page...',
                            'link_extraction_complete': 'Extracting article links...',
                            'article_fetched': f'Fetching article {current_article + 1} of {total_articles}...' if total_articles > 0 else 'Scraping content...',
                            'analyzed': 'Analyzing content with AI...',
                            'ner_complete': 'Extracting stock mentions...',
                            'article_saved_continue': f'Processing article {current_article + 1} of {total_articles}...',
                            'finalized': 'Saving to database...',
                            'duplicate_skipped': 'Duplicate detected, skipping...',
                            'all_articles_finalized': 'All articles processed!',
                        }

                        message = stage_messages.get(stage, f'Stage: {stage}')

                        progress_event = {
                            'type': 'progress',
                            'stage': stage,
                            'message': message,
                            'total_articles': total_articles,
                            'current_article': current_article,
                            'progress': round((current_article / total_articles * 100) if total_articles > 0 else 0, 1)
                        }

                        yield f"data: {json.dumps(progress_event)}\n\n"

            # Send completion event with final state
            if final_state:
                completion_event = {
                    'type': 'complete',
                    'message': 'Processing completed',
                    'source_id': source_id,
                    'url': source.url,
                    'status': final_state['status'],
                    'stage': final_state['stage'],
                    'title': final_state.get('title', 'N/A'),
                    'stock_count': len(final_state.get('stock_mentions', [])),
                    'errors': final_state['errors'],
                    'total_articles': len(final_state.get('processed_articles', [])) if final_state.get('is_listing_page') else 1
                }

                yield f"data: {json.dumps(completion_event)}\n\n"

        except Exception as e:
            error_event = {
                'type': 'error',
                'message': f'Error: {str(e)}'
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.get("/{source_id}/health")
async def get_source_health(
    source_id: int,
    db: Session = Depends(get_db)
):
    """Get health status of a data source"""
    source = db.query(DataSource).filter(DataSource.id == source_id).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source {source_id} not found"
        )

    return {
        "source_id": source_id,
        "health_status": source.health_status,
        "last_fetch_status": source.last_fetch_status,
        "last_fetch_timestamp": source.last_fetch_timestamp,
        "error_count": source.error_count,
        "error_message": source.error_message
    }
