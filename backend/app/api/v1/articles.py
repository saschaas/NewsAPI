from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, case, func
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app.models import NewsArticle, StockMention
from app.schemas import NewsArticleResponse, StockMentionResponse

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("/", response_model=List[NewsArticleResponse])
async def list_articles(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    source_id: Optional[int] = None,
    ticker: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    sentiment: Optional[str] = None,
    high_impact: Optional[bool] = None,
    sort: str = Query("fetched_at", regex="^(fetched_at|published_date|title)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    """
    List articles with filtering and pagination

    Query Parameters:
    - page: Page number (default: 1)
    - limit: Items per page (default: 20, max: 100)
    - source_id: Filter by data source ID
    - ticker: Filter by stock ticker
    - from_date: Filter articles after this date
    - to_date: Filter articles before this date
    - sentiment: Filter by sentiment (positive/negative/neutral)
    - high_impact: Filter by high impact flag
    - sort: Sort field (fetched_at, published_date, title)
    - order: Sort order (asc, desc)
    """
    query = db.query(NewsArticle)

    # Apply filters
    if source_id:
        query = query.filter(NewsArticle.data_source_id == source_id)

    if ticker:
        # Join with stock_mentions to filter by ticker
        query = query.join(StockMention).filter(
            StockMention.ticker_symbol == ticker.upper()
        )

    if from_date:
        query = query.filter(NewsArticle.fetched_at >= from_date)

    if to_date:
        query = query.filter(NewsArticle.fetched_at <= to_date)

    if high_impact is not None:
        query = query.filter(NewsArticle.is_high_impact == high_impact)

    if sentiment:
        # Filter by stock sentiment
        sentiment_map = {
            'positive': ['positive', 'very_positive'],
            'negative': ['negative', 'very_negative'],
            'neutral': ['neutral']
        }
        labels = sentiment_map.get(sentiment.lower(), [])
        if labels:
            query = query.join(StockMention).filter(
                StockMention.sentiment_label.in_(labels)
            )

    # Apply sorting with special handling for published_date
    if sort == "published_date":
        # Use COALESCE to fall back to fetched_at when published_date is NULL
        # This ensures articles without published_date still appear in the list
        sort_expression = case(
            (NewsArticle.published_date.isnot(None), NewsArticle.published_date),
            else_=NewsArticle.fetched_at
        )
        if order == "desc":
            query = query.order_by(desc(sort_expression))
        else:
            query = query.order_by(asc(sort_expression))
    else:
        sort_field = getattr(NewsArticle, sort)
        if order == "desc":
            query = query.order_by(desc(sort_field))
        else:
            query = query.order_by(asc(sort_field))

    # Apply pagination
    offset = (page - 1) * limit
    articles = query.distinct().offset(offset).limit(limit).all()

    return articles


@router.get("/{article_id}", response_model=NewsArticleResponse)
async def get_article(
    article_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific article by ID"""
    article = db.query(NewsArticle).filter(NewsArticle.id == article_id).first()

    if not article:
        raise HTTPException(status_code=404, detail=f"Article {article_id} not found")

    return article


@router.get("/{article_id}/stocks", response_model=List[StockMentionResponse])
async def get_article_stocks(
    article_id: int,
    db: Session = Depends(get_db)
):
    """Get all stock mentions for a specific article"""
    article = db.query(NewsArticle).filter(NewsArticle.id == article_id).first()

    if not article:
        raise HTTPException(status_code=404, detail=f"Article {article_id} not found")

    stocks = db.query(StockMention).filter(
        StockMention.article_id == article_id
    ).all()

    return stocks


@router.delete("/{article_id}", status_code=204)
async def delete_article(
    article_id: int,
    db: Session = Depends(get_db)
):
    """Delete an article"""
    article = db.query(NewsArticle).filter(NewsArticle.id == article_id).first()

    if not article:
        raise HTTPException(status_code=404, detail=f"Article {article_id} not found")

    db.delete(article)
    db.commit()
