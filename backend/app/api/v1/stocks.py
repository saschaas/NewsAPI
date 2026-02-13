from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List
from datetime import datetime, timedelta

from app.database import get_db
from app.models import StockMention, NewsArticle
from app.schemas import StockInfo, StockDetailResponse, StockSentimentTrend, NewsArticleResponse

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/", response_model=List[StockInfo])
async def list_stocks(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    List all stocks mentioned in articles

    Returns stocks sorted by mention count
    """
    stocks = db.query(
        StockMention.ticker_symbol,
        StockMention.company_name,
        func.count(StockMention.id).label('mention_count'),
        func.avg(StockMention.sentiment_score).label('avg_sentiment'),
        func.max(NewsArticle.fetched_at).label('latest_mention')
    ).join(
        NewsArticle, StockMention.article_id == NewsArticle.id
    ).group_by(
        StockMention.ticker_symbol,
        StockMention.company_name
    ).order_by(
        desc('mention_count')
    ).limit(limit).all()

    return [
        StockInfo(
            ticker_symbol=s.ticker_symbol,
            company_name=s.company_name,
            mention_count=s.mention_count,
            avg_sentiment=round(s.avg_sentiment, 3),
            latest_mention=s.latest_mention
        )
        for s in stocks
    ]


@router.get("/{ticker}", response_model=StockDetailResponse)
async def get_stock_details(
    ticker: str,
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific stock"""
    ticker = ticker.upper()

    # Get basic info
    stock = db.query(
        StockMention.ticker_symbol,
        StockMention.company_name,
        func.count(StockMention.id).label('total_mentions'),
        func.avg(StockMention.sentiment_score).label('avg_sentiment')
    ).filter(
        StockMention.ticker_symbol == ticker
    ).group_by(
        StockMention.ticker_symbol,
        StockMention.company_name
    ).first()

    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")

    # Get sentiment trend (last 30 days, grouped by day)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    trend = db.query(
        func.date(NewsArticle.fetched_at).label('date'),
        func.avg(StockMention.sentiment_score).label('avg_sentiment'),
        func.count(StockMention.id).label('mention_count')
    ).join(
        NewsArticle, StockMention.article_id == NewsArticle.id
    ).filter(
        StockMention.ticker_symbol == ticker,
        NewsArticle.fetched_at >= thirty_days_ago
    ).group_by(
        func.date(NewsArticle.fetched_at)
    ).order_by(
        func.date(NewsArticle.fetched_at)
    ).all()

    sentiment_trend = [
        StockSentimentTrend(
            date=datetime.strptime(str(t.date), '%Y-%m-%d'),
            avg_sentiment=round(t.avg_sentiment, 3),
            mention_count=t.mention_count
        )
        for t in trend
    ]

    return StockDetailResponse(
        ticker_symbol=stock.ticker_symbol,
        company_name=stock.company_name,
        total_mentions=stock.total_mentions,
        avg_sentiment=round(stock.avg_sentiment, 3),
        sentiment_trend=sentiment_trend
    )


@router.get("/{ticker}/articles", response_model=List[NewsArticleResponse])
async def get_stock_articles(
    ticker: str,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get articles mentioning a specific stock"""
    ticker = ticker.upper()

    articles = db.query(NewsArticle).join(
        StockMention, NewsArticle.id == StockMention.article_id
    ).filter(
        StockMention.ticker_symbol == ticker
    ).order_by(
        desc(NewsArticle.fetched_at)
    ).limit(limit).all()

    return articles


@router.get("/{ticker}/sentiment")
async def get_stock_sentiment_trend(
    ticker: str,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """
    Get sentiment trend for a stock over time

    Parameters:
    - ticker: Stock ticker symbol
    - days: Number of days to look back (default: 30)
    """
    ticker = ticker.upper()
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    trend = db.query(
        func.date(NewsArticle.fetched_at).label('date'),
        func.avg(StockMention.sentiment_score).label('avg_sentiment'),
        func.count(StockMention.id).label('mention_count')
    ).join(
        NewsArticle, StockMention.article_id == NewsArticle.id
    ).filter(
        StockMention.ticker_symbol == ticker,
        NewsArticle.fetched_at >= cutoff_date
    ).group_by(
        func.date(NewsArticle.fetched_at)
    ).order_by(
        func.date(NewsArticle.fetched_at)
    ).all()

    return {
        "ticker": ticker,
        "period_days": days,
        "data": [
            {
                "date": str(t.date),
                "avg_sentiment": round(t.avg_sentiment, 3),
                "mention_count": t.mention_count
            }
            for t in trend
        ]
    }
