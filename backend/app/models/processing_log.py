from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class ProcessingLog(Base):
    __tablename__ = "processing_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey('news_articles.id', ondelete='CASCADE'), nullable=True)
    data_source_id = Column(Integer, ForeignKey('data_sources.id', ondelete='CASCADE'), nullable=True)
    stage = Column(String, nullable=False)
    status = Column(String, nullable=False)
    duration_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

    # Relationships
    article = relationship("NewsArticle", back_populates="processing_logs")

    __table_args__ = (
        CheckConstraint(
            "status IN ('started', 'success', 'error', 'skipped')",
            name='check_processing_status'
        ),
    )
