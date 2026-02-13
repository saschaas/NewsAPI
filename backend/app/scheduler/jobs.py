import asyncio
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import DataSource, NewsArticle, SystemConfig
from app.agents import process_news_article
from app.services import ollama_service


# Semaphore for concurrent fetch limiting
fetch_semaphore = None


def init_fetch_semaphore(max_concurrent: int):
    """Initialize the fetch semaphore"""
    global fetch_semaphore
    fetch_semaphore = asyncio.Semaphore(max_concurrent)
    logger.info(f"Fetch semaphore initialized with max_concurrent={max_concurrent}")


def get_config_value(key: str, default: any, db: Session) -> any:
    """Get configuration value from database"""
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if not config:
        return default

    # Parse based on data type
    if config.data_type == 'integer':
        return int(config.value)
    elif config.data_type == 'float':
        return float(config.value)
    elif config.data_type == 'boolean':
        return config.value.lower() in ('true', '1', 'yes')
    else:
        return config.value


async def fetch_source_job(source_id: int):
    """
    Job to fetch and process a single data source

    Args:
        source_id: ID of the data source to process
    """
    # Use semaphore to limit concurrent fetches
    async with fetch_semaphore:
        db = SessionLocal()
        try:
            # Get the source
            source = db.query(DataSource).filter(DataSource.id == source_id).first()
            if not source:
                logger.warning(f"Source {source_id} not found, skipping")
                return

            # Check if source is active
            if source.status != 'active':
                logger.info(f"Source {source_id} is {source.status}, skipping")
                return

            # Check global pause
            global_pause = get_config_value('global_pause', False, db)
            if global_pause:
                logger.info(f"Global pause is active, skipping source {source_id}")
                return

            # Check Ollama health before starting
            is_healthy = await ollama_service.check_health()
            if not is_healthy:
                logger.error(f"Ollama is unavailable, skipping source {source_id}")
                # Increment error count
                source.error_count += 1
                source.last_fetch_status = 'error'
                source.error_message = 'Ollama unavailable'
                db.commit()
                return

            logger.info(f"Starting scheduled fetch for source {source_id}: {source.name}")

            # Store source data before closing DB session
            source_url = source.url
            source_type = source.source_type
            extraction_instructions = source.extraction_instructions

        finally:
            db.close()

        # Run the workflow (outside of db session to avoid conflicts)
        result = await process_news_article(
            source_id=source_id,
            source_url=source_url,
            source_type=source_type,
            extraction_instructions=extraction_instructions
        )

        # Handle auto-disable
        db = SessionLocal()
        try:
            source = db.query(DataSource).filter(DataSource.id == source_id).first()
            if not source:
                return

            if result['status'] == 'success' or result['status'] == 'skipped':
                logger.info(f"Source {source_id} processed successfully: {result['stage']}")
            else:
                # Check if we should auto-disable
                auto_disable_threshold = get_config_value('auto_disable_threshold', 5, db)

                if source.error_count >= auto_disable_threshold:
                    logger.warning(
                        f"Source {source_id} reached error threshold ({source.error_count}), "
                        f"auto-disabling"
                    )
                    source.status = 'paused'
                    db.commit()

                    # TODO: Send WebSocket notification about auto-disable

        finally:
            db.close()


async def cleanup_old_articles_job():
    """
    Job to clean up old articles based on retention policy
    """
    logger.info("Starting article cleanup job")

    db = SessionLocal()
    try:
        # Get retention days from config
        retention_days = get_config_value('data_retention_days', 30, db)
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        # Find old articles
        old_articles = db.query(NewsArticle).filter(
            NewsArticle.fetched_at < cutoff_date
        ).all()

        if not old_articles:
            logger.info("No articles to clean up")
            return

        # Delete them (cascade will handle stock_mentions and processing_logs)
        count = len(old_articles)
        for article in old_articles:
            db.delete(article)

        db.commit()

        logger.info(f"Cleaned up {count} articles older than {retention_days} days")

    except Exception as e:
        logger.error(f"Error in cleanup job: {e}")
        db.rollback()
    finally:
        db.close()


async def cleanup_old_cache_job():
    """
    Job to clean up old LLM cache entries
    """
    logger.info("Starting cache cleanup job")

    db = SessionLocal()
    try:
        from app.models import LLMCache

        # Get retention days from config
        retention_days = get_config_value('data_retention_days', 30, db)
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        # Find old cache entries
        old_cache = db.query(LLMCache).filter(
            LLMCache.created_at < cutoff_date
        ).all()

        if not old_cache:
            logger.info("No cache entries to clean up")
            return

        count = len(old_cache)
        for cache in old_cache:
            db.delete(cache)

        db.commit()

        logger.info(f"Cleaned up {count} cache entries older than {retention_days} days")

    except Exception as e:
        logger.error(f"Error in cache cleanup job: {e}")
        db.rollback()
    finally:
        db.close()


def sync_fetch_source_job(source_id: int):
    """
    Synchronous wrapper for fetch_source_job
    APScheduler needs synchronous functions
    """
    asyncio.run(fetch_source_job(source_id))


def sync_cleanup_articles_job():
    """Synchronous wrapper for cleanup job"""
    asyncio.run(cleanup_old_articles_job())


def sync_cleanup_cache_job():
    """Synchronous wrapper for cache cleanup job"""
    asyncio.run(cleanup_old_cache_job())
