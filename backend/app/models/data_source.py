from sqlalchemy import Column, Integer, String, DateTime, Text, CheckConstraint
from sqlalchemy.sql import func
from app.database import Base


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False, unique=True)
    source_type = Column(String, nullable=False)
    status = Column(String, nullable=False, default='active')
    health_status = Column(String, default='pending')
    fetch_frequency_minutes = Column(Integer, nullable=False, default=60)
    cron_expression = Column(String, nullable=True)
    last_fetch_timestamp = Column(DateTime, nullable=True)
    last_fetch_status = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    error_count = Column(Integer, default=0)
    config_json = Column(Text, nullable=True)
    extraction_instructions = Column(Text, nullable=True)
    max_articles = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("source_type IN ('website', 'youtube', 'rss')", name='check_source_type'),
        CheckConstraint("status IN ('active', 'paused', 'deleted')", name='check_status'),
        CheckConstraint("health_status IN ('healthy', 'pending', 'error')", name='check_health_status'),
        CheckConstraint("last_fetch_status IN ('success', 'error', 'captcha', 'timeout')", name='check_fetch_status'),
    )
