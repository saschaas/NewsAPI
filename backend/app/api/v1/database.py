from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Dict

from app.database import get_db
from app.models import NewsArticle, StockMention, DataSource

router = APIRouter(prefix="/database", tags=["database"])


@router.get("/stats")
async def get_database_stats(db: Session = Depends(get_db)):
    """
    Get database statistics including article count, stock count, etc.
    """
    # Count total articles
    total_articles = db.query(NewsArticle).count()

    # Count articles by source
    articles_by_source = db.query(
        DataSource.name,
        func.count(NewsArticle.id).label('count')
    ).join(
        NewsArticle, DataSource.id == NewsArticle.data_source_id
    ).group_by(
        DataSource.name
    ).all()

    # Count unique stocks mentioned
    unique_stocks = db.query(
        func.count(func.distinct(StockMention.ticker_symbol))
    ).scalar()

    # Count total stock mentions
    total_stock_mentions = db.query(StockMention).count()

    # Get top 10 stocks by mention count
    top_stocks = db.query(
        StockMention.ticker_symbol,
        StockMention.company_name,
        func.count(StockMention.id).label('mention_count'),
        func.avg(StockMention.sentiment_score).label('avg_sentiment')
    ).group_by(
        StockMention.ticker_symbol,
        StockMention.company_name
    ).order_by(
        desc('mention_count')
    ).limit(10).all()

    # Format top stocks
    top_stocks_formatted = [
        {
            'ticker_symbol': stock.ticker_symbol,
            'company_name': stock.company_name,
            'mention_count': stock.mention_count,
            'avg_sentiment': round(stock.avg_sentiment, 3) if stock.avg_sentiment else 0
        }
        for stock in top_stocks
    ]

    return {
        'total_articles': total_articles,
        'unique_stocks': unique_stocks,
        'total_stock_mentions': total_stock_mentions,
        'articles_by_source': [
            {'source_name': source_name, 'count': count}
            for source_name, count in articles_by_source
        ],
        'top_stocks': top_stocks_formatted
    }


@router.delete("/articles")
async def delete_all_articles(db: Session = Depends(get_db)):
    """
    Delete all articles from the database
    WARNING: This is a destructive operation!
    """
    try:
        # Delete all stock mentions first (due to foreign key constraints)
        stock_mentions_deleted = db.query(StockMention).delete()

        # Delete all articles
        articles_deleted = db.query(NewsArticle).delete()

        db.commit()

        return {
            'message': 'All articles deleted successfully',
            'articles_deleted': articles_deleted,
            'stock_mentions_deleted': stock_mentions_deleted
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting articles: {str(e)}"
        )
