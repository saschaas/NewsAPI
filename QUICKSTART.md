# Quick Start: Test MarketWatch Multi-Article Workflow

## What's New

✅ The system now **intelligently processes listing pages**
✅ One URL (e.g., MarketWatch) → **10-50 articles automatically**
✅ **LLM extracts article links** from any website structure
✅ **Follows each link** to get full article content
✅ Each article analyzed separately with **dedicated stock sentiment**

## Prerequisites

- Docker Desktop installed and **running**
- 8GB+ RAM available
- Ports 3000, 8000, 11434 free

## 5-Minute Setup

### 1. Start Services

```bash
cd C:\Users\sseidel\Coding\ClaudeCode\NewsAPI
docker-compose up -d
```

Wait ~30 seconds for containers to start.

### 2. Pull LLM Models

```bash
# Pull llama3.1 (required for article link extraction)
docker exec -it newsapi-ollama-1 ollama pull llama3.1
```

This takes 5-10 minutes (one-time download).

### 3. Create MarketWatch Source

```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"MarketWatch Latest\", \"url\": \"https://www.marketwatch.com/latest-news\", \"source_type\": \"website\", \"fetch_frequency_minutes\": 120}"
```

### 4. Trigger Processing

```bash
curl -X POST http://localhost:8000/api/v1/sources/1/test
```

### 5. Watch the Magic

```bash
docker logs -f newsapi-backend-1
```

**Expected output:**
```
INFO: Scraper node: Processing website - https://www.marketwatch.com/latest-news
INFO: Article Link Extractor: Analyzing https://www.marketwatch.com/latest-news
INFO: Found 73 total links on page
INFO: LLM identified 15 article links
INFO: Identified as listing page with 15 articles
INFO: Article Fetcher: Fetching article 1/15: https://www.marketwatch.com/story/...
INFO: Analyzer node: Processing article content
INFO: NER node: Found 3 stock mentions
INFO: Finalizer node: Successfully saved article 1 with 3 stocks
INFO: Moving to article 2/15
...
INFO: All 15 articles processed from listing page
```

### 6. View Results

Open browser: **http://localhost:3000**

- **Dashboard:** See all 15 articles with stock mentions
- **Stocks:** View aggregated sentiment per ticker
- **Sources:** Monitor processing status

## What Just Happened

1. **Playwright** fetched MarketWatch listing page (handles cookie banners, JavaScript)
2. **LLM** analyzed HTML and identified 15 article links
3. **Playwright** fetched each article individually
4. **LLM** extracted metadata, title, summary for each article
5. **LLM** found stock mentions with sentiment for each article
6. **Database** saved 15 complete articles with stock analysis

**Total time:** ~7-10 minutes for 15 articles

## Troubleshooting

**Docker not running:**
```bash
# Start Docker Desktop manually
# Then run: docker-compose up -d
```

**Ollama errors:**
```bash
# Verify Ollama is running
curl http://localhost:11434/api/tags

# Re-pull model if needed
docker exec -it newsapi-ollama-1 ollama pull llama3.1
```

**No articles found:**
```bash
# Check backend logs
docker logs newsapi-backend-1

# Look for "LLM identified X article links"
# If 0, try a different news site
```

## Alternative Test Sites

If MarketWatch doesn't work:

**Yahoo Finance:**
```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"Yahoo Finance\", \"url\": \"https://finance.yahoo.com/topic/stock-market-news/\", \"source_type\": \"website\", \"fetch_frequency_minutes\": 120}"
```

**Bloomberg:**
```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"Bloomberg Markets\", \"url\": \"https://www.bloomberg.com/markets\", \"source_type\": \"website\", \"fetch_frequency_minutes\": 120}"
```

## Documentation

- **TESTING_GUIDE.md** - Detailed step-by-step testing
- **IMPLEMENTATION_SUMMARY.md** - Technical architecture details
- **MULTI_ARTICLE_WORKFLOW.md** - Workflow diagrams and agent details
- **README.md** - Full project documentation

## Next Steps

1. Add more sources to aggregate from multiple sites
2. Set up automated scheduling (sources auto-fetch every N hours)
3. Monitor dashboard for stock sentiment trends
4. Use API to integrate with your own tools

---

**Need help?** Check `TESTING_GUIDE.md` for detailed troubleshooting.
