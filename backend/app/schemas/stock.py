from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class StockInfo(BaseModel):
    """Schema for stock information"""
    ticker_symbol: str
    company_name: str
    mention_count: int
    avg_sentiment: float
    latest_mention: datetime


class StockSentimentTrend(BaseModel):
    """Schema for stock sentiment trend"""
    date: datetime
    avg_sentiment: float
    mention_count: int


class StockDetailResponse(BaseModel):
    """Schema for stock detail response"""
    ticker_symbol: str
    company_name: str
    total_mentions: int
    avg_sentiment: float
    sentiment_trend: list[StockSentimentTrend]
