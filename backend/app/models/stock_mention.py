from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class StockMention(Base):
    __tablename__ = "stock_mentions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey('news_articles.id', ondelete='CASCADE'), nullable=False, index=True)
    ticker_symbol = Column(String, nullable=False, index=True)
    company_name = Column(String, nullable=False)
    stock_exchange = Column(String, nullable=True)
    market_segment = Column(String, nullable=True)
    sentiment_score = Column(Float, nullable=False, index=True)
    sentiment_label = Column(String, nullable=True)
    confidence_score = Column(Float, nullable=True)
    context_snippet = Column(Text, nullable=True)

    # Relationships
    article = relationship("NewsArticle", back_populates="stock_mentions")

    __table_args__ = (
        CheckConstraint(
            "sentiment_label IN ('very_negative', 'negative', 'neutral', 'positive', 'very_positive')",
            name='check_sentiment_label'
        ),
    )
