# Task Scheduling Guide

## Overview

The Stock News API uses APScheduler to automatically fetch news from configured data sources on customizable schedules.

## Features

### 1. Dynamic Job Management
- Jobs created automatically when data sources are added
- Jobs updated when fetch frequency changes
- Jobs removed when sources are deleted/paused
- Real-time job management without restart

### 2. Flexible Scheduling

**Interval-Based (Simple):**
```json
{
  "fetch_frequency_minutes": 60
}
```
Fetches every N minutes.

**Cron-Based (Advanced):**
```json
{
  "cron_expression": "0 */6 * * *"
}
```
Use cron syntax for complex schedules:
- `0 9 * * *` - Every day at 9 AM
- `0 */6 * * *` - Every 6 hours
- `0 9 * * 1-5` - Weekdays at 9 AM
- `*/30 9-17 * * *` - Every 30 min, 9 AM - 5 PM

### 3. Concurrent Fetch Limiting

Maximum concurrent fetches controlled by:
```env
MAX_CONCURRENT_FETCHES=3
```

Uses semaphore to prevent:
- Overwhelming Ollama
- Too many browser instances
- Database connection exhaustion

### 4. Global Pause

Pause ALL scheduled fetching:
```bash
POST /api/v1/scheduler/pause
{
  "paused": true
}
```

Jobs remain scheduled but won't execute.

### 5. Auto-Disable Failed Sources

After N consecutive failures (default: 5):
- Source status → `paused`
- Job removed from scheduler
- User notification (future: WebSocket)
- Manual re-enable required

Prevents:
- Wasting resources on broken sources
- Accumulating errors
- Ollama overload

### 6. Automatic Cleanup Jobs

**Daily Article Cleanup (2 AM UTC):**
- Deletes articles older than retention period
- Default: 30 days
- Cascades to stock_mentions and processing_logs

**Daily Cache Cleanup (3 AM UTC):**
- Deletes old LLM cache entries
- Frees disk space
- Improves cache hit rate

## Usage Examples

### Create Source with Interval Schedule

```bash
POST /api/v1/sources
{
  "name": "Bloomberg - Tech News",
  "url": "https://bloomberg.com/tech",
  "source_type": "website",
  "fetch_frequency_minutes": 120
}
```

Job runs every 2 hours.

### Create Source with Cron Schedule

```bash
POST /api/v1/sources
{
  "name": "CNBC - Market Open",
  "url": "https://cnbc.com/markets",
  "source_type": "website",
  "cron_expression": "0 9,16 * * 1-5"
}
```

Job runs weekdays at 9 AM and 4 PM (market open/close).

### Update Schedule

```bash
PUT /api/v1/sources/5
{
  "fetch_frequency_minutes": 30
}
```

Job automatically updated to run every 30 minutes.

### Pause a Source

```bash
PATCH /api/v1/sources/5/status
{
  "status": "paused"
}
```

Job removed from scheduler.

### Resume a Source

```bash
PATCH /api/v1/sources/5/status
{
  "status": "active"
}
```

Job re-added to scheduler.

### Trigger Immediate Run

```bash
POST /api/v1/scheduler/trigger/5
```

Runs immediately WITHOUT affecting scheduled times.

### Pause All Fetching

```bash
POST /api/v1/scheduler/pause
{
  "paused": true
}
```

All jobs skip execution (checked at runtime).

### Resume All Fetching

```bash
POST /api/v1/scheduler/pause
{
  "paused": false
}
```

### Get Scheduler Status

```bash
GET /api/v1/scheduler/status
```

Response:
```json
{
  "is_running": true,
  "total_jobs": 12,
  "active_jobs": 10,
  "paused_jobs": 0,
  "global_pause": false
}
```

### List All Jobs

```bash
GET /api/v1/scheduler/jobs
```

Response:
```json
{
  "jobs": [
    {
      "id": "source_1",
      "name": "Fetch: Bloomberg Tech",
      "next_run_time": "2025-02-13T14:30:00",
      "trigger": "interval[0:02:00]"
    },
    {
      "id": "cleanup_articles",
      "name": "Cleanup Old Articles",
      "next_run_time": "2025-02-14T02:00:00",
      "trigger": "cron[hour='2', minute='0']"
    }
  ]
}
```

## Job Lifecycle

### 1. Source Created
```
User creates source
  ↓
Database insert
  ↓
Scheduler adds job
  ↓
Job scheduled based on frequency/cron
```

### 2. Job Execution
```
Scheduled time reached
  ↓
Check: Is source active?
  ↓
Check: Is global pause enabled?
  ↓
Check: Is Ollama healthy?
  ↓
Acquire semaphore (limit concurrency)
  ↓
Run LangGraph workflow
  ↓
Release semaphore
  ↓
Update source health/errors
  ↓
Auto-disable if threshold reached
```

### 3. Source Updated
```
User updates schedule
  ↓
Database update
  ↓
Scheduler removes old job
  ↓
Scheduler adds new job with updated schedule
```

### 4. Source Deleted/Paused
```
User pauses/deletes source
  ↓
Database update (status='paused'/'deleted')
  ↓
Scheduler removes job
  ↓
No more automatic fetches
```

## Configuration

### Environment Variables

```env
# Maximum concurrent fetches
MAX_CONCURRENT_FETCHES=3

# Data retention (days)
DATA_RETENTION_DAYS=30

# Auto-disable threshold
AUTO_DISABLE_THRESHOLD=5

# Global pause (can be changed via API)
GLOBAL_PAUSE=false

# Scheduler database
SCHEDULER_DB_URL=sqlite:///./data/scheduler.db
```

### System Config (Database)

```sql
SELECT * FROM system_config WHERE key IN (
  'global_pause',
  'data_retention_days',
  'auto_disable_threshold',
  'max_concurrent_fetches'
);
```

Can be updated via API (future endpoint).

## Monitoring

### Check Job Status

```bash
GET /api/v1/scheduler/jobs/5
```

```json
{
  "id": "source_5",
  "name": "Fetch: Bloomberg",
  "next_run_time": "2025-02-13T15:00:00",
  "trigger": "interval[1:00:00]"
}
```

### Check Source Health

```bash
GET /api/v1/sources/5/health
```

```json
{
  "source_id": 5,
  "health_status": "healthy",
  "last_fetch_status": "success",
  "last_fetch_timestamp": "2025-02-13T14:00:00",
  "error_count": 0,
  "error_message": null
}
```

### Processing Logs

```sql
SELECT
  ds.name,
  COUNT(*) as total_runs,
  SUM(CASE WHEN pl.status = 'success' THEN 1 ELSE 0 END) as successes,
  SUM(CASE WHEN pl.status = 'error' THEN 1 ELSE 0 END) as errors
FROM processing_logs pl
JOIN data_sources ds ON pl.data_source_id = ds.id
WHERE pl.stage = 'overall'
  AND pl.created_at > datetime('now', '-7 days')
GROUP BY ds.name;
```

## Best Practices

### 1. Choose Appropriate Frequencies

**High-frequency sources (15-30 min):**
- Breaking news sites
- Market-moving announcements
- Time-sensitive content

**Medium-frequency sources (1-4 hours):**
- General news sites
- Analysis articles
- Opinion pieces

**Low-frequency sources (daily):**
- Research reports
- Weekly summaries
- In-depth analysis

### 2. Use Cron for Business Hours

```json
{
  "cron_expression": "*/30 9-17 * * 1-5"
}
```

Only fetch during market hours (9 AM - 5 PM, Mon-Fri).

### 3. Stagger Start Times

When adding multiple sources, stagger them:
- Source 1: Every hour at :00
- Source 2: Every hour at :15
- Source 3: Every hour at :30
- Source 4: Every hour at :45

Prevents all sources from hitting Ollama simultaneously.

### 4. Monitor Error Counts

```sql
SELECT name, error_count, error_message
FROM data_sources
WHERE error_count > 0
ORDER BY error_count DESC;
```

Investigate sources with high error counts.

### 5. Adjust Concurrent Limits

If experiencing:
- **Ollama timeouts:** Reduce MAX_CONCURRENT_FETCHES
- **Slow processing:** Increase MAX_CONCURRENT_FETCHES (if hardware allows)

## Troubleshooting

### Jobs Not Running

**Check scheduler status:**
```bash
GET /api/v1/scheduler/status
```

**Verify job exists:**
```bash
GET /api/v1/scheduler/jobs/5
```

**Check source status:**
```bash
GET /api/v1/sources/5
```
Must be `active`.

**Check global pause:**
```bash
GET /api/v1/scheduler/status
```
`global_pause` must be `false`.

### Source Auto-Disabled

1. Check error message:
   ```bash
   GET /api/v1/sources/5/health
   ```

2. Fix underlying issue (captcha, URL changed, etc.)

3. Re-enable:
   ```bash
   PATCH /api/v1/sources/5/status
   {
     "status": "active"
   }
   ```

### High Concurrent Load

Reduce concurrent fetches:
```bash
# Update .env
MAX_CONCURRENT_FETCHES=2

# Restart API
```

Or pause non-critical sources.

### Ollama Overload

- Reduce concurrent fetches
- Increase Ollama timeout
- Upgrade hardware
- Use faster models

## Advanced Usage

### Custom Cron Schedules

**Market Open (9:30 AM ET):**
```
30 9 * * 1-5
```

**Every 15 minutes during trading hours:**
```
*/15 9-16 * * 1-5
```

**Beginning of month:**
```
0 0 1 * *
```

**Quarterly:**
```
0 0 1 1,4,7,10 *
```

### Manual Override

Trigger any source immediately:
```bash
POST /api/v1/scheduler/trigger/5
```

Useful for:
- Testing new sources
- Breaking news
- Manual updates

### Maintenance Windows

Pause all fetching during maintenance:
```bash
POST /api/v1/scheduler/pause
{"paused": true}
```

Resume after:
```bash
POST /api/v1/scheduler/pause
{"paused": false}
```

## Performance

### Typical Job Duration

- **Scraping:** 2-5 seconds
- **LLM Analysis (uncached):** 2-4 seconds
- **LLM Analysis (cached):** 0.1 seconds
- **Database save:** 0.3-0.5 seconds

**Total (uncached):** 5-10 seconds
**Total (cached):** 3-6 seconds

### Cache Hit Rate

Expected 30-50% for news aggregators.

Higher for:
- Duplicate content across sources
- Repeated articles
- Similar content

### Scaling Considerations

**100 sources, hourly fetching:**
- Average: 1.67 sources/minute
- With 3 concurrent: Easily handled
- Ollama utilization: ~20-30%

**500 sources, hourly fetching:**
- Average: 8.3 sources/minute
- With 3 concurrent: May queue
- Consider: Increase concurrent limit or reduce frequencies
