# Getting Started with Stock News API

This guide will walk you through setting up and using the Stock News API for the first time.

## Prerequisites

Before you begin, ensure you have:
- **Docker Desktop** installed and running
- **At least 8GB of RAM** available (for Ollama LLM)
- **Ports available**: 3000 (frontend), 8000 (backend), 11434 (ollama)

## Step 1: Start the Application

1. Open a terminal in the project directory
2. Start all services:

```bash
docker-compose up -d
```

This will start three services:
- **Backend**: FastAPI application with task scheduler
- **Frontend**: React web interface
- **Ollama**: Local LLM inference engine

3. Check that all services are running:

```bash
docker-compose ps
```

You should see all three services with status "Up".

## Step 2: Pull LLM Models

The application requires two Ollama models:

```bash
# Pull the main analysis model (llama3.1)
docker exec -it newsapi-ollama-1 ollama pull llama3.1

# Pull the transcription model (whisper)
docker exec -it newsapi-ollama-1 ollama pull whisper
```

**Note**: The first pull will take several minutes as models are ~4-7GB each.

## Step 3: Access the Application

Open your web browser and navigate to:

**http://localhost:3000**

You should see the Stock News API dashboard with an empty news feed.

## Step 4: Add Your First Data Source

### Option A: Using the Web Interface (Recommended)

1. Click on **"Sources"** in the sidebar
2. Click the **"Add Source"** button
3. Fill in the form:
   - **Name**: "Yahoo Finance - Markets"
   - **URL**: `https://finance.yahoo.com/topic/stock-market-news/`
   - **Source Type**: Website
   - **Fetch Frequency**: 60 (minutes)
4. Click **"Create Source"**

The source will be automatically scheduled and start fetching within a minute.

### Option B: Using the API

```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Yahoo Finance - Markets",
    "url": "https://finance.yahoo.com/topic/stock-market-news/",
    "source_type": "website",
    "fetch_frequency_minutes": 60
  }'
```

## Step 5: Test Your Source

Instead of waiting for the scheduled fetch, you can trigger an immediate test:

1. On the Sources page, find your newly created source
2. Click the **"Test Now"** button
3. Watch the health status change as it processes

The test will:
- Scrape the webpage
- Extract article content
- Analyze with LLM
- Extract stock mentions
- Calculate sentiment
- Store in database

This typically takes 30-60 seconds depending on the page content.

## Step 6: View Results

### Dashboard
Navigate to the **Dashboard** to see all articles. Each article shows:
- Title and summary
- Stock mentions with color-coded sentiment:
  - 🟢 Green: Positive sentiment (> 0.3)
  - 🔴 Red: Negative sentiment (< -0.3)
  - ⚪ Gray: Neutral sentiment
- Author and publish date
- Link to original source

### Stocks Page
Navigate to **Stocks** to see aggregated analysis:
- List of all mentioned ticker symbols
- Average sentiment score per stock
- Total number of mentions
- Latest mention timestamp

## Step 7: Add More Sources

### Popular News Sources

**Websites:**
```json
{
  "name": "MarketWatch",
  "url": "https://www.marketwatch.com/latest-news",
  "source_type": "website",
  "fetch_frequency_minutes": 120
}
```

```json
{
  "name": "Seeking Alpha",
  "url": "https://seekingalpha.com/market-news",
  "source_type": "website",
  "fetch_frequency_minutes": 90
}
```

**YouTube Channels:**
```json
{
  "name": "CNBC Television",
  "url": "https://www.youtube.com/@CNBCtelevision",
  "source_type": "youtube",
  "fetch_frequency_minutes": 180
}
```

### Tips for Adding Sources

1. **Start with longer intervals**: Begin with 60-120 minute intervals to avoid overwhelming the system
2. **Test first**: Always use "Test Now" to verify a source works before relying on scheduled fetches
3. **Monitor errors**: Check the error count on the Sources page regularly
4. **YouTube considerations**:
   - Channel URLs work better than individual videos
   - Transcription takes longer (2-5 minutes per video)
   - More resource-intensive than websites

## Step 8: Understanding Status Indicators

### Health Status
- **🟢 Healthy**: Last fetch was successful
- **🟠 Pending**: Source hasn't been fetched yet
- **🔴 Error**: Last fetch failed (check error message)

### Source Status
- **Active**: Source is being fetched on schedule
- **Paused**: Source is disabled (can be resumed)

**Auto-pause**: Sources automatically pause after 5 consecutive failures to prevent wasted resources.

## Monitoring and Management

### Pause/Resume a Source
On the Sources page, click the **Pause** or **Resume** button on any source.

### Delete a Source
Click the **Delete** button (red). This will:
- Remove the source from the database
- Cancel its scheduled jobs
- **Keep** all previously fetched articles

### Check System Health
Visit: http://localhost:8000/api/v1/health

### View API Documentation
Visit: http://localhost:8000/docs

## Advanced Usage

### Custom Scheduling with Cron

Instead of a simple frequency, you can use cron expressions for advanced scheduling:

```json
{
  "name": "Morning Brief",
  "url": "https://example.com/morning-brief",
  "source_type": "website",
  "cron_expression": "0 9 * * 1-5"
}
```

This example runs every weekday at 9:00 AM.

**Cron Format**: `minute hour day month weekday`

Common examples:
- `0 */4 * * *` - Every 4 hours
- `0 9,12,15,18 * * *` - At 9am, 12pm, 3pm, 6pm
- `0 0 * * 0` - Every Sunday at midnight

### Filtering Articles

Use the API to filter articles by:
- **Ticker symbol**: `/api/v1/articles?ticker=AAPL`
- **Date range**: `/api/v1/articles?from_date=2024-01-01&to_date=2024-01-31`
- **High impact**: `/api/v1/articles?high_impact=true`
- **Sentiment**: `/api/v1/articles?sentiment=positive`

See full API docs at http://localhost:8000/docs

## Troubleshooting

### No articles appearing after test?

1. Check the backend logs:
```bash
docker logs newsapi-backend-1
```

2. Verify Ollama is running:
```bash
docker exec -it newsapi-ollama-1 ollama list
```

3. Check if models are loaded:
```bash
docker exec -it newsapi-ollama-1 ollama ps
```

### Source showing errors?

Common causes:
- **Cookie banners**: Some sites require manual verification
- **Rate limiting**: Site is blocking automated requests
- **Paywall**: Content is behind a subscription wall
- **Invalid URL**: URL format is incorrect

### Application running slowly?

1. Reduce concurrent fetches in `.env`:
```env
MAX_CONCURRENT_FETCHES=2
```

2. Increase fetch intervals (e.g., 180+ minutes)

3. Check available RAM:
```bash
docker stats
```

### Fresh start needed?

To completely reset:
```bash
# Stop all services
docker-compose down

# Remove data and downloads
rm -rf data/ downloads/

# Restart
docker-compose up -d

# Reinitialize (backend will auto-create DB)
```

## Next Steps

- Explore the **Stocks** page to track sentiment trends
- Set up multiple sources for comprehensive coverage
- Use the API to integrate with your own tools
- Check the main README.md for advanced configuration options

## Getting Help

- **API Documentation**: http://localhost:8000/docs
- **Backend Logs**: `docker logs newsapi-backend-1`
- **Frontend Logs**: `docker logs newsapi-frontend-1`
- **Ollama Logs**: `docker logs newsapi-ollama-1`

For issues or questions, please open an issue on GitHub.

---

**Happy news tracking!** 📈📰
