from typing import TypedDict, List, Optional, Dict, Any
from datetime import datetime


class NewsProcessingState(TypedDict):
    """
    State object for the news processing workflow
    Passed between all agent nodes
    """
    # Input
    source_id: int
    source_url: str
    source_type: str  # 'website' or 'youtube'
    extraction_instructions: Optional[str]  # Optional user instructions for extraction

    # Scraper output
    raw_content: Optional[str]
    raw_html: Optional[str]
    screenshot: Optional[str]  # Base64-encoded screenshot for vision models
    video_path: Optional[str]
    transcript: Optional[str]
    metadata: Dict[str, Any]

    # Article link extraction (for listing pages)
    is_listing_page: bool  # Whether this is a listing page with multiple articles
    article_links: List[str]  # Extracted article URLs from listing page
    current_article_index: int  # Current article being processed
    processed_articles: List[Dict[str, Any]]  # Results of processed articles

    # Analyzer output
    title: str
    content: str
    summary: Optional[str]
    main_topic: Optional[str]
    author: Optional[str]
    published_date: Optional[datetime]
    is_high_impact: bool

    # NER output
    stock_mentions: List[Dict[str, Any]]  # List of stock mention dicts

    # Hashing
    content_hash: str

    # Control flow
    stage: str  # Current processing stage
    errors: List[str]
    status: str  # 'success', 'error', 'skipped'

    # Performance tracking
    start_time: float
    stage_timings: Dict[str, float]
