# LangGraph Workflow Guide

## Overview

The Stock News API uses a LangGraph-based agent workflow to process news articles through multiple AI-powered stages.

## Workflow Architecture

```
┌─────────────┐
│   Scraper   │ ──► Fetch content (web or YouTube)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Analyzer   │ ──► Extract structured info with LLM
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  NER/Stock  │ ──► Extract stock mentions & sentiment
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Finalizer  │ ──► Save to database
└─────────────┘
```

## Agents

### 1. Scraper Agent
**Purpose:** Fetch raw content from URLs

**Capabilities:**
- Website scraping with Playwright
- Cookie banner auto-handling
- YouTube video download and transcription
- Metadata extraction

**Output:**
- `raw_content`: Extracted text
- `metadata`: Title, author, date, etc.
- `content_hash`: SHA-256 hash for duplicates

### 2. Analyzer Agent
**Purpose:** Extract structured information using LLM

**Features:**
- LLM-powered content analysis (Ollama)
- Response caching by content hash
- Metadata enrichment

**Extracted Fields:**
- Title
- Summary (2-3 sentences)
- Main topic
- Author
- Published date
- High impact flag

**Caching:**
- Results cached by content hash
- Avoids reprocessing duplicates
- Significant performance improvement

### 3. NER/Stock Agent
**Purpose:** Extract stock mentions with sentiment

**Critical Feature - Stock Separation:**
This agent is designed to keep sentiment analysis COMPLETELY SEPARATE for each stock mentioned in the article.

**Example:**
```
Article: "Apple exceeded expectations but Microsoft disappointed investors"

Output:
[
  {
    ticker: "AAPL",
    sentiment_score: 0.8,
    sentiment_label: "positive"
  },
  {
    ticker: "MSFT",
    sentiment_score: -0.6,
    sentiment_label: "negative"
  }
]
```

**Extracted Per Stock:**
- Ticker symbol
- Company name
- Stock exchange (NYSE, NASDAQ, etc.)
- Market segment (Technology, Healthcare, etc.)
- Sentiment score (-1.0 to 1.0)
- Sentiment label (very_negative to very_positive)
- Confidence score (0.0 to 1.0)
- Context snippet (relevant quote)

### 4. Supervisor Agent
**Purpose:** Route workflow based on state

**Routes:**
- `init` → Scraper
- `scraped` → Analyzer
- `analyzed` → NER
- `ner_complete` → Finalizer
- `error` → Error Handler

### 5. Finalizer Agent
**Purpose:** Persist to database

**Actions:**
- Check for duplicates (by content hash)
- Create article record
- Create stock mention records
- Log processing metrics
- Update data source health

### 6. Error Handler Agent
**Purpose:** Handle failures gracefully

**Actions:**
- Log errors to processing_logs
- Update data source error count
- Set health status to 'error'
- Increment error count for auto-disable

## Usage Examples

### Process a Single URL

```bash
POST /api/v1/process/url
Content-Type: application/json

{
  "url": "https://www.cnbc.com/2024/01/15/apple-stock-news.html",
  "source_type": "website",
  "source_name": "CNBC - Apple News"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Successfully processed article: Apple Exceeds Q4 Expectations...",
  "article_id": 123,
  "stage": "finalized",
  "errors": [],
  "timings": {
    "scraper": 2.3,
    "analyzer": 1.8,
    "ner": 2.1,
    "finalizer": 0.4
  }
}
```

### Process a YouTube Video

```bash
POST /api/v1/process/url
Content-Type: application/json

{
  "url": "https://www.youtube.com/watch?v=ABC123",
  "source_type": "youtube",
  "source_name": "Tech Review - Market Analysis"
}
```

### Trigger Processing for a Data Source

```bash
POST /api/v1/process/trigger/5
```

## Performance Optimizations

### 1. LLM Response Caching
- Cache keyed by content hash
- Avoids reprocessing identical content
- Stored in `llm_cache` table
- Tracks usage count and last used time

### 2. Duplicate Detection
- Content normalized before hashing
- SHA-256 hash stored in `content_hash` field
- Articles with same hash skipped

### 3. Stage Timings
- Each stage duration tracked
- Stored in processing_logs
- Useful for performance analysis

## Error Handling

### Error Types

1. **Scraping Errors**
   - Network timeouts
   - Captchas
   - Cookie banners failed
   - HTTP errors

2. **LLM Errors**
   - Ollama unavailable
   - Invalid JSON response
   - Timeout

3. **Database Errors**
   - Duplicate content
   - Constraint violations
   - Connection issues

### Auto-Disable Feature

After N consecutive failures (default: 5):
- Data source status → `paused`
- User must manually re-enable
- Prevents wasting resources

## Monitoring

### Processing Logs

All stages logged to `processing_logs` table:

```sql
SELECT
  stage,
  status,
  COUNT(*) as count,
  AVG(duration_ms) as avg_duration
FROM processing_logs
WHERE created_at > NOW() - INTERVAL '1 day'
GROUP BY stage, status;
```

### Success Rates

```sql
SELECT
  ds.name,
  COUNT(CASE WHEN pl.status = 'success' THEN 1 END) as successes,
  COUNT(CASE WHEN pl.status = 'error' THEN 1 END) as errors
FROM processing_logs pl
JOIN data_sources ds ON pl.data_source_id = ds.id
WHERE pl.stage = 'overall'
GROUP BY ds.name;
```

## Configuration

Key settings in `.env`:

```env
# Ollama Models
OLLAMA_MODEL_ANALYSIS=llama3.1
OLLAMA_MODEL_NER=llama3.1
OLLAMA_MODEL_WHISPER=whisper

# Auto-disable threshold
AUTO_DISABLE_THRESHOLD=5

# Timeouts
OLLAMA_TIMEOUT=300
```

## Best Practices

1. **Test with sample URLs first** using `/api/v1/process/url`
2. **Monitor processing logs** for errors
3. **Check LLM cache hit rate** for performance
4. **Review stock extractions** to ensure proper separation
5. **Set appropriate timeouts** based on content length

## Troubleshooting

### LLM Returns Invalid JSON
- Check prompt formatting
- Verify model supports JSON mode
- Increase temperature for more flexible parsing

### Stocks Not Extracted
- Article may not mention specific stocks
- LLM may need better prompting
- Check confidence scores

### High Duplicate Rate
- Normal for news aggregators
- Cache is working correctly
- Consider different sources

### Slow Processing
- Check Ollama response times
- Verify network latency for scraping
- Consider caching strategies
