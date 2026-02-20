"""
Database initialization script
Creates all tables and inserts default configuration
"""
from app.database import engine, Base, SessionLocal
from app.models import DataSource, NewsArticle, StockMention, ProcessingLog, SystemConfig, LLMCache
from loguru import logger


def migrate_source_type_constraint():
    """Migrate data_sources table to add 'rss' to source_type check constraint
    and fix any column misalignment from previous migrations.

    Background: extraction_instructions was added via ALTER TABLE ADD COLUMN,
    which puts it at the END in SQLite (after created_at, updated_at). A prior
    migration used SELECT * which copied data positionally into a new table
    where extraction_instructions was BEFORE created_at/updated_at, scrambling
    those three columns. This migration fixes both issues.
    """
    from sqlalchemy import text, inspect

    inspector = inspect(engine)
    if 'data_sources' not in inspector.get_table_names():
        return  # Table will be created fresh by create_all()

    with engine.connect() as conn:
        # Detect if columns are scrambled: if updated_at contains non-datetime text,
        # the previous migration caused misalignment
        needs_data_repair = False
        try:
            result = conn.execute(text(
                "SELECT updated_at FROM data_sources LIMIT 1"
            ))
            row = result.fetchone()
            if row and row[0]:
                val = str(row[0])
                # If updated_at holds a long text string, it's actually extraction_instructions
                if len(val) > 30 and not val[:4].isdigit():
                    needs_data_repair = True
                    logger.warning("Detected column misalignment in data_sources, will repair")
        except Exception:
            pass

        # Check if constraint migration is needed
        needs_constraint = False
        result = conn.execute(text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='data_sources'"
        ))
        ddl = result.scalar() or ""
        if "'rss'" not in ddl:
            needs_constraint = True

        if not needs_constraint and not needs_data_repair:
            logger.info("data_sources table is up to date, skipping migration")
            return

        logger.info(f"Migrating data_sources (constraint={needs_constraint}, repair={needs_data_repair})...")

        conn.execute(text("PRAGMA foreign_keys=OFF"))

        conn.execute(text("""
            CREATE TABLE data_sources_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR NOT NULL,
                url VARCHAR NOT NULL UNIQUE,
                source_type VARCHAR NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'active',
                health_status VARCHAR DEFAULT 'pending',
                fetch_frequency_minutes INTEGER NOT NULL DEFAULT 60,
                cron_expression VARCHAR,
                last_fetch_timestamp DATETIME,
                last_fetch_status VARCHAR,
                error_message TEXT,
                error_count INTEGER DEFAULT 0,
                config_json TEXT,
                extraction_instructions TEXT,
                created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
                updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
                CONSTRAINT check_source_type CHECK (source_type IN ('website', 'youtube', 'rss')),
                CONSTRAINT check_status CHECK (status IN ('active', 'paused', 'deleted')),
                CONSTRAINT check_health_status CHECK (health_status IN ('healthy', 'pending', 'error')),
                CONSTRAINT check_fetch_status CHECK (last_fetch_status IN ('success', 'error', 'captcha', 'timeout'))
            )
        """))

        if needs_data_repair:
            # Columns are scrambled: extraction_instructions holds created_at,
            # created_at holds updated_at, updated_at holds extraction_instructions.
            # Swap them back to correct positions.
            conn.execute(text("""
                INSERT INTO data_sources_new (
                    id, name, url, source_type, status, health_status,
                    fetch_frequency_minutes, cron_expression,
                    last_fetch_timestamp, last_fetch_status,
                    error_message, error_count, config_json,
                    extraction_instructions, created_at, updated_at
                )
                SELECT
                    id, name, url, source_type, status, health_status,
                    fetch_frequency_minutes, cron_expression,
                    last_fetch_timestamp, last_fetch_status,
                    error_message, error_count, config_json,
                    updated_at, extraction_instructions, created_at
                FROM data_sources
            """))
        else:
            # Columns are fine, just copy with explicit names
            conn.execute(text("""
                INSERT INTO data_sources_new (
                    id, name, url, source_type, status, health_status,
                    fetch_frequency_minutes, cron_expression,
                    last_fetch_timestamp, last_fetch_status,
                    error_message, error_count, config_json,
                    extraction_instructions, created_at, updated_at
                )
                SELECT
                    id, name, url, source_type, status, health_status,
                    fetch_frequency_minutes, cron_expression,
                    last_fetch_timestamp, last_fetch_status,
                    error_message, error_count, config_json,
                    extraction_instructions, created_at, updated_at
                FROM data_sources
            """))

        conn.execute(text("DROP TABLE data_sources"))
        conn.execute(text("ALTER TABLE data_sources_new RENAME TO data_sources"))
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.commit()

        logger.info("data_sources migration complete")


def migrate_add_max_articles():
    """Add max_articles column to data_sources table if it doesn't exist."""
    from sqlalchemy import text, inspect

    inspector = inspect(engine)
    if 'data_sources' not in inspector.get_table_names():
        return  # Table will be created fresh by create_all()

    columns = [col['name'] for col in inspector.get_columns('data_sources')]
    if 'max_articles' in columns:
        logger.info("max_articles column already exists, skipping migration")
        return

    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE data_sources ADD COLUMN max_articles INTEGER"))
        conn.commit()
        logger.info("Added max_articles column to data_sources")


def init_database():
    """Initialize database with tables and default config"""
    logger.info("Creating database tables...")

    # Run migrations before create_all
    migrate_source_type_constraint()
    migrate_add_max_articles()

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
