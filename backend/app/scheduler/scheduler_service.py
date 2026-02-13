from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.executors.pool import ThreadPoolExecutor
from loguru import logger
from typing import Optional
from datetime import datetime

from app.config import settings
from app.database import SessionLocal
from app.models import DataSource
from app.scheduler.jobs import (
    sync_fetch_source_job,
    sync_cleanup_articles_job,
    sync_cleanup_cache_job,
    init_fetch_semaphore
)


class SchedulerService:
    """Service for managing the APScheduler instance and jobs"""

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.is_running = False

    def initialize(self):
        """Initialize the scheduler"""
        if self.scheduler:
            logger.warning("Scheduler already initialized")
            return

        logger.info("Initializing APScheduler...")

        # Configure jobstores
        jobstores = {
            'default': SQLAlchemyJobStore(url=settings.SCHEDULER_DB_URL)
        }

        # Configure executors
        executors = {
            'default': ThreadPoolExecutor(max_workers=settings.MAX_CONCURRENT_FETCHES * 2)
        }

        # Job defaults
        job_defaults = {
            'coalesce': True,  # Combine multiple pending executions into one
            'max_instances': 1,  # Only one instance of a job at a time
            'misfire_grace_time': 300  # 5 minutes grace period
        }

        # Create scheduler
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )

        # Initialize fetch semaphore
        init_fetch_semaphore(settings.MAX_CONCURRENT_FETCHES)

        logger.info("Scheduler initialized successfully")

    def start(self):
        """Start the scheduler"""
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized. Call initialize() first.")

        if self.is_running:
            logger.warning("Scheduler already running")
            return

        logger.info("Starting scheduler...")
        self.scheduler.start()
        self.is_running = True

        # Add system jobs
        self._add_system_jobs()

        # Load all active data sources and create jobs
        self._load_data_source_jobs()

        logger.info("Scheduler started successfully")

    def shutdown(self):
        """Shutdown the scheduler"""
        if not self.scheduler or not self.is_running:
            return

        logger.info("Shutting down scheduler...")
        self.scheduler.shutdown(wait=True)
        self.is_running = False
        logger.info("Scheduler shut down successfully")

    def _add_system_jobs(self):
        """Add system maintenance jobs"""
        # Daily cleanup job at 2 AM UTC
        self.scheduler.add_job(
            sync_cleanup_articles_job,
            trigger=CronTrigger(hour=2, minute=0),
            id='cleanup_articles',
            name='Cleanup Old Articles',
            replace_existing=True
        )

        # Daily cache cleanup at 3 AM UTC
        self.scheduler.add_job(
            sync_cleanup_cache_job,
            trigger=CronTrigger(hour=3, minute=0),
            id='cleanup_cache',
            name='Cleanup Old Cache',
            replace_existing=True
        )

        logger.info("System jobs added")

    def _load_data_source_jobs(self):
        """Load all active data sources and create scheduled jobs"""
        db = SessionLocal()
        try:
            sources = db.query(DataSource).filter(
                DataSource.status == 'active'
            ).all()

            for source in sources:
                self.add_source_job(source)

            logger.info(f"Loaded {len(sources)} data source jobs")

        finally:
            db.close()

    def add_source_job(self, source: DataSource):
        """
        Add or update a scheduled job for a data source

        Args:
            source: DataSource model instance
        """
        job_id = f"source_{source.id}"

        # Remove existing job if present
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        # Skip if not active
        if source.status != 'active':
            logger.info(f"Source {source.id} is not active, skipping job creation")
            return

        # Determine trigger
        if source.cron_expression:
            try:
                trigger = CronTrigger.from_crontab(source.cron_expression)
                trigger_desc = f"cron: {source.cron_expression}"
            except Exception as e:
                logger.error(f"Invalid cron expression for source {source.id}: {e}")
                return
        else:
            trigger = IntervalTrigger(minutes=source.fetch_frequency_minutes)
            trigger_desc = f"every {source.fetch_frequency_minutes} minutes"

        # Add job
        self.scheduler.add_job(
            sync_fetch_source_job,
            trigger=trigger,
            args=[source.id],
            id=job_id,
            name=f"Fetch: {source.name}",
            replace_existing=True
        )

        logger.info(f"Added job for source {source.id} ({source.name}): {trigger_desc}")

    def remove_source_job(self, source_id: int):
        """
        Remove a scheduled job for a data source

        Args:
            source_id: Data source ID
        """
        job_id = f"source_{source_id}"

        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job for source {source_id}")
        else:
            logger.warning(f"Job for source {source_id} not found")

    def pause_source_job(self, source_id: int):
        """
        Pause a scheduled job

        Args:
            source_id: Data source ID
        """
        job_id = f"source_{source_id}"
        job = self.scheduler.get_job(job_id)

        if job:
            self.scheduler.pause_job(job_id)
            logger.info(f"Paused job for source {source_id}")
        else:
            logger.warning(f"Job for source {source_id} not found")

    def resume_source_job(self, source_id: int):
        """
        Resume a paused job

        Args:
            source_id: Data source ID
        """
        job_id = f"source_{source_id}"
        job = self.scheduler.get_job(job_id)

        if job:
            self.scheduler.resume_job(job_id)
            logger.info(f"Resumed job for source {source_id}")
        else:
            logger.warning(f"Job for source {source_id} not found")

    def trigger_source_job_now(self, source_id: int):
        """
        Trigger a job to run immediately (in addition to scheduled runs)

        Args:
            source_id: Data source ID
        """
        job_id = f"source_{source_id}"
        job = self.scheduler.get_job(job_id)

        if job:
            # Modify the job to run immediately once
            job.modify(next_run_time=datetime.utcnow())
            logger.info(f"Triggered immediate run for source {source_id}")
        else:
            logger.warning(f"Job for source {source_id} not found")

    def get_job_info(self, source_id: int) -> Optional[dict]:
        """
        Get information about a scheduled job

        Args:
            source_id: Data source ID

        Returns:
            Job info dict or None
        """
        job_id = f"source_{source_id}"
        job = self.scheduler.get_job(job_id)

        if not job:
            return None

        return {
            'id': job.id,
            'name': job.name,
            'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
            'trigger': str(job.trigger),
        }

    def get_all_jobs(self) -> list[dict]:
        """
        Get information about all scheduled jobs

        Returns:
            List of job info dicts
        """
        jobs = self.scheduler.get_jobs()

        return [
            {
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger),
            }
            for job in jobs
        ]


# Singleton instance
scheduler_service = SchedulerService()
