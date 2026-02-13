from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class StockMentionResponse(BaseModel):
    """Schema for stock mention response"""
    id: int
    ticker_symbol: str
    company_name: str
    stock_exchange: Optional[str] = None
    market_segment: Optional[str] = None
    sentiment_score: float
    sentiment_label: Optional[Literal['very_negative', 'negative', 'neutral', 'positive', 'very_positive']] = None
    confidence_score: Optional[float] = None
    context_snippet: Optional[str] = None

    class Config:
        from_attributes = True


class NewsArticleResponse(BaseModel):
    """Schema for news article response"""
    id: int
    data_source_id: int
    url: str
    title: str
    content: str
    summary: Optional[str] = None
    main_topic: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[datetime] = None
    fetched_at: datetime
    is_high_impact: bool
    stock_mentions: list[StockMentionResponse] = []

    class Config:
        from_attributes = True


class NewsArticleListResponse(BaseModel):
    """Schema for list of news articles"""
    articles: list[NewsArticleResponse]
    total: int


class ArticleFilters(BaseModel):
    """Schema for article filtering"""
    page: int = 1
    limit: int = 20
    source_id: Optional[int] = None
    ticker: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    sentiment: Optional[Literal['positive', 'negative', 'neutral']] = None
    high_impact: Optional[bool] = None
    sort: str = 'fetched_at'
    order: Literal['asc', 'desc'] = 'desc'
