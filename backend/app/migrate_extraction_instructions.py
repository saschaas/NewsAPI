"""
Migration script to add extraction_instructions column to data_sources table
"""
from sqlalchemy import text
from app.database import engine, SessionLocal
from loguru import logger


def migrate():
    """Add extraction_instructions column to data_sources table"""
    db = SessionLocal()

    try:
        # Check if column already exists
        result = db.execute(text("PRAGMA table_info(data_sources)"))
        columns = [row[1] for row in result.fetchall()]

        if 'extraction_instructions' in columns:
            logger.info("Column 'extraction_instructions' already exists, skipping migration")
            return

        logger.info("Adding 'extraction_instructions' column to data_sources table...")

        # Add the column
        db.execute(text(
            "ALTER TABLE data_sources ADD COLUMN extraction_instructions TEXT"
        ))
        db.commit()

        logger.info("Migration completed successfully!")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
