from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import SystemConfig
from app.scheduler import scheduler_service

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


class GlobalPauseRequest(BaseModel):
    """Request to pause/resume all fetching"""
    paused: bool


class SchedulerStatusResponse(BaseModel):
    """Scheduler status response"""
    is_running: bool
    total_jobs: int
    active_jobs: int
    paused_jobs: int
    global_pause: bool


@router.get("/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status(db: Session = Depends(get_db)):
    """Get scheduler status"""
    all_jobs = scheduler_service.get_all_jobs()

    # Get global pause setting
    config = db.query(SystemConfig).filter(SystemConfig.key == 'global_pause').first()
    global_pause = config.value.lower() in ('true', '1', 'yes') if config else False

    # Count active jobs (source jobs only)
    source_jobs = [j for j in all_jobs if j['id'].startswith('source_')]

    return SchedulerStatusResponse(
        is_running=scheduler_service.is_running,
        total_jobs=len(all_jobs),
        active_jobs=len(source_jobs),
        paused_jobs=0,  # APScheduler doesn't track paused state easily
        global_pause=global_pause
    )


@router.get("/jobs")
async def list_all_jobs():
    """List all scheduled jobs"""
    return {
        "jobs": scheduler_service.get_all_jobs()
    }


@router.get("/jobs/{source_id}")
async def get_job_info(source_id: int):
    """Get information about a specific source's job"""
    info = scheduler_service.get_job_info(source_id)

    if not info:
        raise HTTPException(status_code=404, detail=f"Job for source {source_id} not found")

    return info


@router.post("/pause")
async def pause_all(request: GlobalPauseRequest, db: Session = Depends(get_db)):
    """
    Pause or resume all scheduled fetching

    When paused, scheduled jobs will still exist but won't execute
    (checked at runtime in the job function)
    """
    # Update config
    config = db.query(SystemConfig).filter(SystemConfig.key == 'global_pause').first()

    if config:
        config.value = 'true' if request.paused else 'false'
    else:
        config = SystemConfig(
            key='global_pause',
            value='true' if request.paused else 'false',
            data_type='boolean',
            description='Pause all scheduled fetches'
        )
        db.add(config)

    db.commit()

    action = "paused" if request.paused else "resumed"
    return {
        "message": f"All scheduled fetching {action}",
        "global_pause": request.paused
    }


@router.post("/trigger/{source_id}")
async def trigger_job_now(source_id: int):
    """Trigger a job to run immediately (doesn't affect schedule)"""
    scheduler_service.trigger_source_job_now(source_id)

    return {
        "message": f"Job for source {source_id} triggered",
        "source_id": source_id
    }
