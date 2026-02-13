# Multi-Article Workflow Documentation

## Overview

The Stock News API now supports **intelligent multi-article processing**. When you add a news site like MarketWatch, Bloomberg, or Yahoo Finance, the system automatically:

1. **Detects** if the URL is a listing page (multiple articles) or a single article
2. **Extracts** article links using LLM analysis of the HTML structure
3. **Fetches** each individual article
4. **Analyzes** each article separately with stock sentiment
5. **Saves** all articles to the database

This means a single data source URL like `https://www.marketwatch.com/` can fetch and process dozens of articles in one run!

## Workflow Architecture

### New Workflow Diagram

```
┌─────────────┐
│   Scraper   │ ← Fetch main page (listing page or single article)
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│ Article Link        │ ← LLM analyzes HTML to find article links
│ Extractor           │
└──────┬──────────────┘
       │
       ├─────────────┐
       │             │
       │             ▼
       │      ┌─────────────┐
       │      │ Single      │ → Continue with existing analysis
       │      │ Article     │
       │      └─────────────┘
       │
       ▼
┌─────────────┐
│ Listing     │
│ Page        │
└──────┬──────┘
       │
       ▼
   ╔═══════════════════════════════════╗
   ║  FOR EACH ARTICLE LINK:           ║
   ║                                   ║
   ║  ┌──────────────┐                ║
   ║  │ Article      │ ← Fetch article║
   ║  │ Fetcher      │                ║
   ║  └──────┬───────┘                ║
   ║         │                        ║
   ║         ▼                        ║
   ║  ┌──────────────┐                ║
   ║  │ Analyzer     │ ← LLM analysis ║
   ║  └──────┬───────┘                ║
   ║         │                        ║
   ║         ▼                        ║
   ║  ┌──────────────┐                ║
   ║  │ NER/Stocks   │ ← Extract      ║
   ║  └──────┬───────┘    stocks      ║
   ║         │                        ║
   ║         ▼                        ║
   ║  ┌──────────────┐                ║
   ║  │ Finalizer    │ ← Save to DB   ║
   ║  └──────┬───────┘                ║
   ║         │                        ║
   ║         └─────► Next Article     ║
   ╚═══════════════════════════════════╝
```

## New Agents

### 1. Article Link Extractor Agent
**File:** `backend/app/agents/article_link_extractor.py`

**Purpose:** Intelligently identifies article links from listing pages using LLM.

**How it works:**
1. Parses HTML to extract all links
2. Filters to same-domain links only
3. Sends link data to LLM for intelligent classification
4. LLM identifies which links are actual article links (not nav, categories, etc.)
5. Returns clean list of article URLs

**LLM Prompt Strategy:**
```
The LLM receives:
- Website URL for context
- List of links with: URL, link text, surrounding context
- Criteria for what makes an article link

The LLM responds with:
- JSON array of link IDs that are articles
- Example: [0, 3, 5, 12, 15]
```

### 2. Article Fetcher Agent
**File:** `backend/app/agents/article_fetcher.py`

**Purpose:** Fetches individual articles from the extracted links.

**How it works:**
1. Gets current article index from state
2. Fetches that specific article URL
3. Extracts content using existing scraper service
4. Updates state with article content
5. Resets analysis fields for the new article

**Looping Logic:**
- After an article is saved, increments `current_article_index`
- Router checks if more articles exist
- If yes → fetch next article
- If no → workflow ends

## Enhanced State

### New State Fields

```python
class NewsProcessingState(TypedDict):
    # ... existing fields ...

    # NEW: Multi-article support
    is_listing_page: bool           # True if this is a listing page
    article_links: List[str]         # Extracted article URLs
    current_article_index: int       # Current article being processed (0-based)
    processed_articles: List[Dict]   # Results of all processed articles
```

### State Flow Example

**Initial State:**
```python
{
    'source_url': 'https://www.marketwatch.com/',
    'is_listing_page': False,
    'article_links': [],
    'current_article_index': 0,
    'processed_articles': []
}
```

**After Link Extraction:**
```python
{
    'source_url': 'https://www.marketwatch.com/',
    'is_listing_page': True,
    'article_links': [
        'https://www.marketwatch.com/story/article-1',
        'https://www.marketwatch.com/story/article-2',
        'https://www.marketwatch.com/story/article-3'
    ],
    'current_article_index': 0,
    'processed_articles': []
}
```

**After First Article Saved:**
```python
{
    'source_url': 'https://www.marketwatch.com/',
    'is_listing_page': True,
    'article_links': [...],
    'current_article_index': 1,  # ← Incremented
    'processed_articles': [
        {
            'url': 'https://www.marketwatch.com/story/article-1',
            'status': 'success',
            'article_id': 42,
            'stocks_found': 3
        }
    ]
}
```

## Testing the New Workflow

### Prerequisites

1. Start Docker services:
```bash
docker-compose up -d
```

2. Verify Ollama is running:
```bash
docker exec -it newsapi-ollama-1 ollama list
```

3. Ensure models are pulled:
```bash
docker exec -it newsapi-ollama-1 ollama pull llama3.1
```

### Test with MarketWatch

**Using the API:**

```bash
# Create a MarketWatch source
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MarketWatch - Latest News",
    "url": "https://www.marketwatch.com/latest-news",
    "source_type": "website",
    "fetch_frequency_minutes": 120
  }'

# Trigger immediate processing
curl -X POST http://localhost:8000/api/v1/sources/1/test
```

**Using the Frontend:**

1. Navigate to http://localhost:3000
2. Go to "Sources" page
3. Click "Add Source"
4. Fill in:
   - Name: "MarketWatch - Latest News"
   - URL: https://www.marketwatch.com/latest-news
   - Type: Website
   - Frequency: 120 minutes
5. Click "Create Source"
6. Click "Test Now" to trigger immediate fetch

### Watch the Logs

```bash
# Watch backend logs in real-time
docker logs -f newsapi-backend-1

# You'll see output like:
# INFO: Scraper node: Processing website - https://www.marketwatch.com/latest-news
# INFO: Article Link Extractor: Analyzing https://www.marketwatch.com/latest-news
# INFO: Found 47 total links on page
# INFO: LLM identified 12 article links
# INFO: Identified as listing page with 12 articles
# INFO: Article Fetcher: Fetching article 1/12: https://www.marketwatch.com/story/...
# INFO: Analyzer node: Processing article content (1234 chars)
# INFO: NER node: Analyzing for stock mentions
# INFO: Finalizer node: Saving article '...'
# INFO: Moving to article 2/12
# ...
# INFO: All 12 articles processed from listing page
```

## Example Use Cases

### Use Case 1: News Aggregator
**URL:** `https://www.marketwatch.com/latest-news`
- System detects listing page
- Extracts 15 article links
- Fetches and analyzes each article
- Saves 15 articles with individual stock sentiment

### Use Case 2: Category Page
**URL:** `https://finance.yahoo.com/topic/stock-market-news/`
- System detects listing page
- Extracts 20 article links
- Processes each article
- Deduplicates based on content hash

### Use Case 3: Single Article
**URL:** `https://www.marketwatch.com/story/tesla-stock-surges-2024-02-13`
- System detects single article
- Skips link extraction
- Analyzes article directly
- Saves 1 article

## Performance Considerations

### Timing Estimates

For a listing page with 10 articles:
- **Scraping main page:** ~3-5 seconds
- **Link extraction (LLM):** ~5-10 seconds
- **Per article:**
  - Fetch: ~2-3 seconds
  - Analyze (LLM): ~10-15 seconds
  - NER (LLM): ~8-12 seconds
  - Save: ~0.5 seconds
  - **Total per article:** ~25-35 seconds

**Total for 10 articles:** ~5-7 minutes

### Optimization

Current settings limit concurrent processing, but you can adjust:

```python
# In backend/app/config.py or .env
MAX_CONCURRENT_FETCHES=3  # Process multiple sources in parallel

# Note: Each source processes its articles sequentially
# to maintain proper state management
```

### Resource Usage

- **Memory:** ~500MB per concurrent fetch (LLM processing)
- **Ollama:** ~4-6GB (consistent)
- **Database:** ~50-100KB per article

## Error Handling

### Failed Article Fetch

If an individual article fails to fetch:
1. Error is logged
2. Article is skipped
3. `current_article_index` is incremented
4. Processing continues with next article

### Partial Success

Listing page result example:
```json
{
  "processed_articles": [
    {"url": "...", "status": "success", "article_id": 42},
    {"url": "...", "status": "duplicate", "article_id": 38},
    {"url": "...", "status": "success", "article_id": 43},
    // ... etc
  ]
}
```

### LLM Unavailable

If Ollama is unavailable:
- Link extraction falls back to treating as single article
- Existing error handling applies
- Source is marked as errored

## Database Changes

### Articles Table

Articles now store the **specific article URL**, not just the source URL:

```sql
-- Old behavior (single article source)
url: "https://www.marketwatch.com/"

-- New behavior (from listing page)
url: "https://www.marketwatch.com/story/article-title-123"
```

This allows:
- Proper deduplication per article
- Direct links to original content
- Better tracking of what was processed

### Processing Logs

Each article gets its own processing logs:
- `article_id` links to specific article
- Stage timings tracked per article
- Overall workflow time includes all articles

## Benefits

1. **Efficiency:** One source URL → Many articles
2. **Flexibility:** Works with any news site structure
3. **Intelligence:** LLM-powered link detection adapts to different sites
4. **Reliability:** Failed articles don't block others
5. **Traceability:** Full logging per article

## Comparison: Old vs New

### Old Workflow
```
Source URL → Scrape → Analyze → Extract Stocks → Save
Result: 1 article per source
```

### New Workflow
```
Source URL → Scrape → Extract Links → For Each Article → Analyze → Extract Stocks → Save
Result: 1-50+ articles per source
```

## Future Enhancements

Potential improvements:
- [ ] Parallel article fetching (with rate limiting)
- [ ] Smart pagination detection
- [ ] Historical article discovery (go back in time)
- [ ] Incremental fetching (only new articles)
- [ ] Domain-specific link patterns (learn from history)

---

**The system is now ready to handle real-world news aggregation at scale!** 🚀
