from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    data_source_id = Column(Integer, ForeignKey('data_sources.id', ondelete='CASCADE'), nullable=False, index=True)
    url = Column(String, nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    main_topic = Column(String, nullable=True)
    author = Column(String, nullable=True)
    published_date = Column(DateTime, nullable=True, index=True)
    fetched_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    content_hash = Column(String, nullable=False, unique=True)
    is_high_impact = Column(Boolean, default=False)
    raw_metadata_json = Column(Text, nullable=True)

    # Relationships
    stock_mentions = relationship("StockMention", back_populates="article", cascade="all, delete-orphan")
    processing_logs = relationship("ProcessingLog", back_populates="article", cascade="all, delete-orphan")
