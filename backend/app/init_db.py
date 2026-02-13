"""
Database initialization script
Creates all tables and inserts default configuration
"""
from app.database import engine, Base, SessionLocal
from app.models import DataSource, NewsArticle, StockMention, ProcessingLog, SystemConfig, LLMCache
from loguru import logger


def init_database():
    """Initialize database with tables and default config"""
    logger.info("Creating database tables...")

    # Create all tables
    Base.metadata.create_all(bind=engine)

    logger.info("Database tables created successfully")

    # Insert default system configuration
    db = SessionLocal()
    try:
        # Check if config already exists
        existing_config = db.query(SystemConfig).first()
        if existing_config:
            logger.info("System configuration already exists, skipping initialization")
            return

        logger.info("Inserting default system configuration...")

        default_configs = [
            SystemConfig(
                key='data_retention_days',
                value='30',
                data_type='integer',
                description='Number of days to keep articles before deletion'
            ),
            SystemConfig(
                key='ollama_host',
                value='http://ollama:11434',
                data_type='string',
                description='Ollama API endpoint'
            ),
            SystemConfig(
                key='ollama_model_analysis',
                value='llama3.1',
                data_type='string',
                description='Model for content analysis'
            ),
            SystemConfig(
                key='ollama_model_ner',
                value='llama3.1',
                data_type='string',
                description='Model for named entity recognition'
            ),
            SystemConfig(
                key='ollama_model_whisper',
                value='whisper',
                data_type='string',
                description='Model for transcription'
            ),
            SystemConfig(
                key='max_concurrent_fetches',
                value='3',
                data_type='integer',
                description='Maximum parallel scraping tasks'
            ),
            SystemConfig(
                key='global_pause',
                value='false',
                data_type='boolean',
                description='Pause all scheduled fetches'
            ),
            SystemConfig(
                key='auto_disable_threshold',
                value='5',
                data_type='integer',
                description='Consecutive failures before auto-disabling source'
            ),
        ]

        for config in default_configs:
            db.add(config)

        db.commit()
        logger.info("Default system configuration inserted successfully")

    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
    logger.info("Database initialization complete!")
