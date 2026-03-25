import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, not_
from typing import List, Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.models import StockMention, NewsArticle
from app.schemas import StockInfo, StockDetailResponse, StockSentimentTrend, NewsArticleResponse

router = APIRouter(prefix="/stocks", tags=["stocks"])

# ---------------------------------------------------------------------------
# Category classification
# ---------------------------------------------------------------------------

_INDICES = {'DAX', 'DOW', 'SPX', 'NDX', 'FTSE', 'CAC', 'MDAX', 'SDAX', 'STOXX', 'NIKKEI'}
_CRYPTO = {'BTC', 'ETH', 'XRP', 'SOL', 'DOGE', 'ADA', 'USDT', 'USDC', 'BNB', 'AVAX'}
_CURRENCIES = {'USD', 'EUR', 'GBP', 'JPY', 'CNY', 'CAD', 'CHF', 'AUD', 'RUB', 'INR'}
_COMMODITIES_TICKERS = {'OIL', 'GAS', 'GOLD', 'BRENT'}
_CENTRAL_BANKS = {'FED', 'ECB', 'BOJ', 'BOE', 'PBC'}
_ORGS = {'NATO', 'OPEC', 'EU', 'UN', 'IMF', 'WTO', 'WHO'}

_COMMODITIES_NAME_PATTERNS = ['crude oil', 'brent', 'natural gas', 'gold', 'silver', 'copper', 'oil price']
_CENTRAL_BANKS_NAME_PATTERNS = ['federal reserve', 'notenbank', 'central bank', 'zentralbank', 'ecb', 'ezb']
_COUNTRY_NAME_PATTERNS = ['country', 'republic', 'kingdom']
_PLACEHOLDER_TICKERS = {'NONE', 'NA', 'N/A', 'NULL', 'UNKNOWN', 'OTHER', 'TBD', 'NONE MENTIONED'}


def _classify_entity(ticker: str, company_name: str) -> str | None:
    """Classify a mention into a market category. Returns None for junk entries that should be excluded."""
    t = ticker.strip().upper()
    cn = company_name.lower()

    # Skip obvious placeholders — these are never useful
    if t in _PLACEHOLDER_TICKERS or 'none mentioned' in cn or 'no specific' in cn:
        return None
    if cn == 'n/a' or cn.startswith('n/a ') or cn.startswith('n/a('):
        return None

    if t in _INDICES or 'aktienindex' in cn or 'index' in cn:
        return 'indices'
    if t in _CRYPTO or 'bitcoin' in cn or 'crypto' in cn or 'ethereum' in cn:
        return 'crypto'
    if t in _CURRENCIES:
        return 'currencies'
    if t in _COMMODITIES_TICKERS or any(p in cn for p in _COMMODITIES_NAME_PATTERNS):
        return 'commodities'
    if t in _CENTRAL_BANKS or any(p in cn for p in _CENTRAL_BANKS_NAME_PATTERNS):
        return 'central_banks'
    if t in _ORGS:
        return 'organisations'

    # Heuristics for entries with long/invalid tickers or descriptive company names
    if '(' in t or ' ' in t or '-' in t or '/' in t:
        # Tickers like "EUROPEAN UNION (NO SPECIFIC...)" or "US-NOTENBANK (FED)"
        if any(p in cn for p in _CENTRAL_BANKS_NAME_PATTERNS):
            return 'central_banks'
        if any(p in cn for p in _COUNTRY_NAME_PATTERNS) or 'union' in cn:
            return 'countries'
        # Check if the long ticker itself looks like a country/org name
        t_lower = t.lower()
        country_names = ['ukraine', 'hungary', 'russia', 'china', 'iran', 'israel', 'turkey']
        if any(c in t_lower for c in country_names):
            return 'countries'
        org_names = ['commission', 'parliament', 'congress']
        if any(o in t_lower for o in org_names):
            return 'organisations'
        return 'other'

    # Name-based heuristics for entries that slipped past ticker checks
    if any(p in cn for p in _COUNTRY_NAME_PATTERNS):
        return 'countries'
    # People — check before stock validation so person names with valid-looking tickers are caught
    person_words = ['person', 'donald', 'president', 'kevin', 'politician', 'minister', 'chancellor']
    if any(w in cn for w in person_words):
        return 'people'
    if 'newspaper' in cn or 'messaging' in cn or 'messenger' in cn or 'not a company' in cn:
        return None
    if cn.startswith('n/a') or cn == 'n/a':
        return None

    # If ticker looks like a valid stock ticker (1-5 uppercase alpha, optional .X)
    if re.match(r'^[A-Z]{1,5}(\.[A-Z]{1,2})?$', t) and len(t) <= 6:
        # Final company_name sanity checks — reject junk entries
        reject_words = ['law', 'act ', 'state-owned', 'newspaper', 'oil company']
        if any(w in cn for w in reject_words):
            return None
        return 'stocks'

    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=List[StockInfo])
async def list_stocks(
    limit: int = 50,
    category: Optional[str] = Query(None, description="Filter by category: stocks, indices, crypto, commodities, central_banks, countries, organisations, people, currencies, other. Omit for all."),
    from_date: Optional[datetime] = Query(None, description="Filter articles published after this date"),
    db: Session = Depends(get_db)
):
    """
    List all market entities mentioned in articles.

    Returns entities sorted by mention count, each with a `category` field.
    Use the `category` query parameter to filter by a specific category.
    Use `from_date` to only include mentions from articles published after that date.
    """
    from sqlalchemy import case

    # Base query: all non-empty ticker symbols
    base = db.query(
        StockMention.ticker_symbol,
        StockMention.company_name,
        func.count(StockMention.id).label('mention_count'),
        func.avg(StockMention.sentiment_score).label('avg_sentiment'),
        func.max(NewsArticle.fetched_at).label('latest_mention')
    ).join(
        NewsArticle, StockMention.article_id == NewsArticle.id
    ).filter(
        StockMention.ticker_symbol != None,  # noqa: E711
        StockMention.ticker_symbol != '',
    )

    if from_date:
        base = base.filter(
            case(
                (NewsArticle.published_date.isnot(None), NewsArticle.published_date),
                else_=NewsArticle.fetched_at
            ) >= from_date
        )

    base = base.group_by(
        StockMention.ticker_symbol,
        StockMention.company_name
    ).order_by(
        desc('mention_count')
    ).limit(500).all()  # fetch more so we can classify in Python

    results = []
    for s in base:
        cat = _classify_entity(s.ticker_symbol, s.company_name)
        if cat is None:
            continue  # junk entry — skip entirely
        if category and cat != category:
            continue
        results.append(StockInfo(
            ticker_symbol=s.ticker_symbol,
            company_name=s.company_name,
            mention_count=s.mention_count,
            avg_sentiment=round(s.avg_sentiment, 3),
            latest_mention=s.latest_mention,
            category=cat,
        ))

    return results[:limit]


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
