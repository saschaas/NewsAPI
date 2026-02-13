# Testing Guide: Multi-Article Workflow with MarketWatch

## Overview

This guide shows you how to test the enhanced multi-article workflow that intelligently detects listing pages and processes multiple articles.

## Why Playwright is Required

**MarketWatch blocks simple HTTP requests** (returns HTTP 401), which is why the system uses:
- **Playwright**: Simulates a real browser with cookies, JavaScript execution
- **Cookie Banner Handling**: Automatically clicks "Accept" buttons
- **Dynamic Content Loading**: Waits for JavaScript to render content

Simple HTTP clients like `requests` or `httpx` won't work with modern news sites.

## Prerequisites

1. **Docker Desktop** must be running
2. **Minimum 8GB RAM** available for Ollama
3. **Ports 3000, 8000, 11434** available

## Step-by-Step Testing Instructions

### 1. Remove Obsolete Docker Compose Version

First, fix the warning in docker-compose.yml:

```bash
# Open docker-compose.yml and remove the first line:
# version: '3.8'
```

### 2. Start Docker Services

```bash
cd /c/Users/sseidel/Coding/ClaudeCode/NewsAPI

# Start all services (backend, frontend, ollama)
docker-compose up -d
```

**Expected output:**
```
[+] Running 4/4
 ✔ Network newsapi_app-network    Created
 ✔ Container newsapi-ollama-1     Started
 ✔ Container newsapi-backend-1    Started
 ✔ Container newsapi-frontend-1   Started
```

### 3. Verify Services are Running

```bash
docker-compose ps
```

**Expected output:**
```
NAME                    STATUS          PORTS
newsapi-backend-1       Up              0.0.0.0:8000->8000/tcp
newsapi-frontend-1      Up              0.0.0.0:3000->80/tcp
newsapi-ollama-1        Up              0.0.0.0:11434->11434/tcp
```

### 4. Pull Required LLM Models

```bash
# Pull llama3.1 for article analysis and link extraction
docker exec -it newsapi-ollama-1 ollama pull llama3.1

# Pull whisper for YouTube transcription
docker exec -it newsapi-ollama-1 ollama pull whisper
```

**This will take 5-10 minutes** as models are several GB each.

Verify models are loaded:
```bash
docker exec -it newsapi-ollama-1 ollama list
```

### 5. Initialize the Database

The backend automatically initializes the database on first run, but you can verify:

```bash
# Check backend logs
docker logs newsapi-backend-1

# You should see:
# INFO: Creating database tables...
# INFO: Database initialized successfully
# INFO: Application startup complete
```

### 6. Test with MarketWatch

#### Option A: Using the API (Recommended for Testing)

**Create a MarketWatch data source:**

```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MarketWatch - Latest News",
    "url": "https://www.marketwatch.com/latest-news",
    "source_type": "website",
    "fetch_frequency_minutes": 120
  }'
```

**Response:**
```json
{
  "id": 1,
  "name": "MarketWatch - Latest News",
  "url": "https://www.marketwatch.com/latest-news",
  "status": "active",
  "health_status": "pending"
}
```

**Trigger immediate processing (don't wait for schedule):**

```bash
curl -X POST http://localhost:8000/api/v1/sources/1/test
```

#### Option B: Using the Frontend

1. Open browser: **http://localhost:3000**
2. Click **"Sources"** in sidebar
3. Click **"Add Source"** button
4. Fill in the form:
   - **Name**: MarketWatch - Latest News
   - **URL**: https://www.marketwatch.com/latest-news
   - **Source Type**: Website
   - **Fetch Frequency**: 120 minutes
5. Click **"Create Source"**
6. Click **"Test Now"** to trigger processing

### 7. Monitor the Processing

**Watch the backend logs in real-time:**

```bash
docker logs -f newsapi-backend-1
```

**Expected log output:**

```
INFO: Starting workflow for source 1: https://www.marketwatch.com/latest-news
INFO: Scraper node: Processing website - https://www.marketwatch.com/latest-news
INFO: Navigating to https://www.marketwatch.com/latest-news
INFO: Clicked cookie banner with selector: button:has-text("Accept")
INFO: Scraper node: Successfully scraped 45231 characters

INFO: Article Link Extractor: Analyzing https://www.marketwatch.com/latest-news
INFO: Found 73 total links on page
INFO: LLM identified 15 article links
INFO: Identified as listing page with 15 articles

INFO: Article Fetcher: Fetching article 1/15: https://www.marketwatch.com/story/...
INFO: Article Fetcher: Successfully fetched 3421 characters

INFO: Analyzer node: Processing article content (3421 chars)
INFO: NER node: Analyzing for stock mentions
INFO: NER node: Found 3 stock mentions

INFO: Finalizer node: Saving article 'Tesla Stock Surges on Earnings Beat'
INFO: Created article ID: 1
INFO: Created 3 stock mentions
INFO: Finalizer node: Successfully saved article 1 with 3 stocks
INFO: Moving to article 2/15

INFO: Article Fetcher: Fetching article 2/15: https://www.marketwatch.com/story/...
...
INFO: All 15 articles processed from listing page
INFO: Workflow completed: status=success, time=245.32s
```

### 8. Verify Results

**Check the dashboard:**

1. Open **http://localhost:3000**
2. View the **Dashboard** page
3. You should see **15 new articles** with:
   - Full article titles
   - Summaries
   - Stock mentions with sentiment (green/red badges)
   - Links to original articles

**Check via API:**

```bash
# Get all articles
curl http://localhost:8000/api/v1/articles

# Get stock analysis
curl http://localhost:8000/api/v1/stocks

# Get specific stock details
curl http://localhost:8000/api/v1/stocks/TSLA
```

## What the Workflow Does

For `https://www.marketwatch.com/latest-news`:

1. **Scraper Agent** (5-10s):
   - Uses Playwright to load page in headless Chrome
   - Handles cookie banners automatically
   - Waits for dynamic content to load
   - Extracts HTML

2. **Article Link Extractor Agent** (10-20s):
   - Parses HTML for all links
   - Sends link data to LLM with criteria
   - LLM identifies 10-20 article links
   - Filters out navigation, categories, ads

3. **For Each Article** (~30-40s per article):
   - **Article Fetcher**: Fetches full article with Playwright
   - **Analyzer**: LLM extracts title, summary, topics, high-impact flag
   - **NER**: LLM finds stocks with individual sentiment scores
   - **Finalizer**: Saves to database with deduplication

4. **Total Time**: 5-10 minutes for 15 articles

## Troubleshooting

### Services Won't Start

```bash
# Check Docker Desktop is running
docker info

# If error, start Docker Desktop manually

# Check logs for specific service
docker logs newsapi-backend-1
docker logs newsapi-ollama-1
```

### Playwright Errors

```bash
# Install Playwright browsers inside container
docker exec -it newsapi-backend-1 playwright install chromium

# Restart backend
docker-compose restart backend
```

### Ollama Connection Errors

```bash
# Check Ollama is accessible
curl http://localhost:11434/api/tags

# Pull models if missing
docker exec -it newsapi-ollama-1 ollama pull llama3.1

# Check Ollama logs
docker logs newsapi-ollama-1
```

### No Articles Found

If the workflow completes but no articles saved:

1. **Check if LLM identified articles**:
   - Look for "LLM identified X article links" in logs
   - If 0, the LLM might have misclassified the page

2. **Check for duplicates**:
   - If all articles are duplicates, they'll be skipped
   - Check "duplicate_skipped" in logs

3. **Check Ollama is working**:
   ```bash
   docker exec -it newsapi-ollama-1 ollama run llama3.1 "Say hello"
   ```

### Processing is Slow

Expected timings:
- Scraping: 3-5s per page
- LLM calls: 10-15s each
- Per article: ~30-40s total

For 15 articles: **7-10 minutes** is normal.

To speed up:
- Reduce number of articles by limiting to top 5
- Increase concurrent processing (see Configuration below)

## Configuration

### Limit Number of Articles

Edit `backend/app/agents/article_link_extractor.py`:

```python
# Line 95: Limit links sent to LLM
links_sample = links[:20]  # Change to :10 for fewer articles
```

### Adjust Processing Limits

Edit `backend/app/config.py` or `.env`:

```env
MAX_CONCURRENT_FETCHES=3  # Process 3 sources in parallel
```

**Note**: Each source processes articles sequentially to maintain state.

## Alternative Test Sites

If MarketWatch is problematic, try these sites:

### Yahoo Finance
```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Yahoo Finance - Stock News",
    "url": "https://finance.yahoo.com/topic/stock-market-news/",
    "source_type": "website",
    "fetch_frequency_minutes": 180
  }'
```

### Seeking Alpha
```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Seeking Alpha - Market News",
    "url": "https://seekingalpha.com/market-news",
    "source_type": "website",
    "fetch_frequency_minutes": 120
  }'
```

### Bloomberg
```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Bloomberg - Markets",
    "url": "https://www.bloomberg.com/markets",
    "source_type": "website",
    "fetch_frequency_minutes": 90
  }'
```

## Expected Results

After successful processing of MarketWatch, you should have:

- ✅ **15-20 articles** saved to database
- ✅ **30-50 stock mentions** with individual sentiment scores
- ✅ Articles visible on Dashboard page
- ✅ Stock analysis on Stocks page
- ✅ Processing logs showing each stage
- ✅ Data source marked as "healthy"

## Next Steps

1. **Add more sources** to aggregate from multiple sites
2. **Set up scheduling** to automatically fetch every N hours
3. **Monitor the dashboard** for new articles and stock trends
4. **Use the API** to integrate with your own tools

## API Examples

```bash
# Get articles mentioning Tesla
curl "http://localhost:8000/api/v1/articles?ticker=TSLA"

# Get high-impact articles
curl "http://localhost:8000/api/v1/articles?high_impact=true"

# Get sentiment trend for a stock
curl "http://localhost:8000/api/v1/stocks/AAPL/sentiment?days=30"

# Get recent articles from specific source
curl "http://localhost:8000/api/v1/articles?source_id=1&limit=10"
```

---

## Summary

The multi-article workflow allows you to:
- Add **one URL** (e.g., MarketWatch homepage)
- Get **10-50 articles** automatically extracted and analyzed
- Each article processed individually with **dedicated stock sentiment**
- Works intelligently across **different website structures**

All powered by LLM-based intelligent link extraction and Playwright browser automation! 🚀
