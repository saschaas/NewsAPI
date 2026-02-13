import time
from typing import Dict, Any
from loguru import logger
from datetime import datetime
from sqlalchemy.orm import Session

from app.agents.state import NewsProcessingState
from app.models import ProcessingLog, DataSource
from app.database import SessionLocal


async def error_handler_node(state: NewsProcessingState) -> NewsProcessingState:
    """
    Error Handler Node

    Logs errors and updates data source status

    Args:
        state: Current workflow state

    Returns:
        Updated state
    """
    logger.error(f"Error handler: Processing failed at stage '{state['stage']}'")
    logger.error(f"Errors: {', '.join(state['errors'])}")

    db = SessionLocal()

    try:
        # Log all errors
        for error in state['errors']:
            error_log = ProcessingLog(
                data_source_id=state['source_id'],
                stage=state['stage'],
                status='error',
                error_message=error
            )
            db.add(error_log)

        # Update data source
        source = db.query(DataSource).filter(DataSource.id == state['source_id']).first()
        if source:
            source.last_fetch_timestamp = datetime.utcnow()
            source.last_fetch_status = 'error'
            source.health_status = 'error'
            source.error_message = '; '.join(state['errors'][:3])  # Keep it concise
            source.error_count += 1  # Increment error count

        db.commit()

        logger.info(f"Error logged for source {state['source_id']}")

    except Exception as e:
        logger.error(f"Error handler failed: {e}")
        db.rollback()

    finally:
        db.close()

    state['stage'] = 'error_handled'
    return state
