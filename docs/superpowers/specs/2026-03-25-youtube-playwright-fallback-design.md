# YouTube Playwright Transcript Fallback — Design Spec

**Date:** 2026-03-25
**Status:** Approved

## Problem

YouTube rate-limits subtitle/caption API requests (HTTP 429). The current `YouTubeService` has 3 subtitle extraction methods — `youtube_transcript_api`, `yt-dlp` subtitle download, and manual subtitle URL fetching — all of which hit the same YouTube subtitle API surface. When rate-limited, all 3 fail and videos are skipped entirely until the 60-minute rate limit window expires.

## Solution

Add a Playwright-based transcript extraction fallback that opens the YouTube watch page in a real browser, clicks the "Show transcript" UI button, and scrapes the transcript text from the DOM. This uses a completely different code path (browser UI interaction) than the subtitle API methods.

## Architecture

### Extraction Flow

```
Rate-limited? ──yes──► Playwright transcript extraction
     │                         │
     no                    success? ──no──► skip video (retry next run)
     │                         ▼
     ▼                    return transcript
API methods (A/B/C)
     │
  success? ──no──► Playwright fallback
     │                │
    yes            success? ──no──► skip video
     │                │
     ▼               yes
  return              │
  transcript          ▼
                   return transcript
```

### Key Decisions

1. **Reuse existing `WebScraperService`** — the Playwright fallback uses the existing scraper's browser context, getting stealth injection, UA rotation, and proxy support for free.
2. **Skip API when rate-limited, go straight to Playwright** — avoids making requests that extend the YouTube ban. Playwright becomes the primary method during rate-limit windows.
3. **Skip video when Playwright also fails** — maintain quality bar. No description-only fallback. Videos are retried on the next scheduled run.
4. **Lazy import to avoid circular dependency** — `web_scraper` is imported inside the method body, not at module level, since both `youtube.py` and `scraping.py` are imported side-by-side in `services/__init__.py`.
5. **Rate-limit flag is NOT cleared by Playwright success** — the rate-limit window stays active for its full duration. This prevents the system from immediately reverting to API methods (which would hit the rate limit again). Only a successful API-based subtitle fetch clears the flag.

## Playwright Transcript Extraction Method

### `async _fetch_via_playwright(video_id: str) -> Optional[str]`

Steps:

1. **Lazy-import `web_scraper`** from `app.services.scraping` inside the method body.
2. **Initialize browser** via `await web_scraper.initialize()` (idempotent — returns early if already initialized).
3. **Open a new page** via `await web_scraper.context.new_page()`. This creates an isolated page within the shared browser context.
4. **Navigate** to `https://www.youtube.com/watch?v={video_id}` with a 30-second timeout.
5. **Dismiss cookie consent** — reuse `await web_scraper.handle_cookie_banner(page)` which already handles YouTube's "Accept All" variants. Non-blocking (3s timeout, continues if no banner).
6. **Click "Show transcript"** — the button inside `ytd-video-description-transcript-section-renderer`. Note: this button is accessible without expanding the description; the transcript section is a separate engagement panel element.
7. **Wait for transcript segments** to appear: `page.wait_for_selector('ytd-transcript-segment-renderer', timeout=10000)`.
8. **Extract text** from all `ytd-transcript-segment-renderer .segment-text` elements.
9. **Clean and join** segments into a single transcript string (strip whitespace, deduplicate, join with spaces).
10. **Close the page** in a `finally` block and return the transcript (or `None` on any failure).

### Selector Strategy

| Element | Selector | Notes |
|---------|----------|-------|
| Cookie consent | Reuse `web_scraper.handle_cookie_banner()` | Already handles "Accept All", "Akzeptieren", etc. |
| Show transcript button | `ytd-video-description-transcript-section-renderer button` | Accessible without expanding description |
| Transcript segments | `ytd-transcript-segment-renderer .segment-text` | Contains the actual caption text |

### Timeouts

- Page load: 30 seconds
- Cookie consent: handled by `handle_cookie_banner()` (2s per selector)
- Transcript panel: 10 seconds wait_for_selector after click (segments load lazily)

### Edge Cases

- **No transcript available:** Some videos have transcripts disabled or are live streams. The "Show transcript" button won't exist — `wait_for_selector` on the button times out, method returns `None`.
- **Age-restricted videos:** Require sign-in. The page will show a login wall. Not supported — method returns `None`, video is skipped.
- **Concurrent access:** Multiple videos may be processed simultaneously (scheduler semaphore allows `MAX_CONCURRENT_FETCHES=3`). Each gets its own page in the shared browser context. This is intentional — Playwright contexts support multiple concurrent pages.

### Failure Logging

The method logs which specific failure mode occurred to aid debugging:
- "No transcript button found" — button selector not found
- "Transcript panel empty" — panel opened but no segments loaded
- "Page load failed" — navigation timeout or error
- "Playwright fallback disabled" — config switch is off

## Integration Changes

### YouTubeService Refactor

The current `_get_transcript_sync` runs entirely in a `ThreadPoolExecutor`. Since Playwright is async, the main method becomes `_get_transcript_async` with careful interleaving of sync-in-executor and async-native calls:

```python
async def _get_transcript_async(self, url: str) -> Dict[str, Any]:
    # Phase 1: Metadata via yt-dlp (sync → run in executor)
    loop = asyncio.get_event_loop()
    metadata_result = await loop.run_in_executor(
        self.executor, self._extract_metadata_sync, url
    )
    if metadata_result is None:
        return {'status': 'error', ...}

    info, metadata = metadata_result

    # Phase 2: Subtitles
    video_id = info.get('id', '')
    rl_status = self.get_rate_limit_status()

    if rl_status['is_rate_limited']:
        # Skip API methods → Playwright directly (async, no executor)
        transcript = await self._fetch_via_playwright(video_id)
    else:
        # Try API methods A/B/C (sync → run in executor)
        transcript = await loop.run_in_executor(
            self.executor, self._try_api_methods_sync, url, video_id, info
        )
        if not transcript:
            # API failed → Playwright fallback (async, no executor)
            transcript = await self._fetch_via_playwright(video_id)

    if transcript and len(transcript.strip()) > 50:
        self._record_subtitle_success()
        return {'status': 'success', 'transcript': transcript, ...}

    return {'status': 'error', 'error': 'No subtitles available', ...}
```

Key execution model:
- `_extract_metadata_sync` — sync yt-dlp call, runs in ThreadPoolExecutor
- `_try_api_methods_sync` — sync subtitle methods A/B/C, runs in ThreadPoolExecutor
- `_fetch_via_playwright` — async Playwright call, runs on event loop directly

### Public API

`get_video_transcript()` and `process_youtube_url()` are already async. They now call `_get_transcript_async()` directly instead of using `run_in_executor` with the old sync method.

### Config Addition

```python
YOUTUBE_PLAYWRIGHT_FALLBACK: bool = True  # master switch to enable/disable
```

### Files Changed

| File | Change |
|------|--------|
| `backend/app/services/youtube.py` | Add `_fetch_via_playwright()`, refactor to async, add `_extract_metadata_sync` and `_try_api_methods_sync` helper methods |
| `backend/app/config.py` | Add `YOUTUBE_PLAYWRIGHT_FALLBACK` setting |
| `backend/app/.env.example` | Document new setting |

### Files NOT Changed

- `agents/scraper.py` — calls same `youtube_service` API, same return shape
- `agents/article_fetcher.py` — calls same `youtube_service` API
- `agents/workflow.py` — no changes
- `services/__init__.py` — no changes

## Error Handling

- Playwright fallback catches all exceptions and returns `None` (never crashes the pipeline).
- If the transcript panel doesn't appear (no transcript available), returns `None`.
- Browser is initialized via `web_scraper.initialize()` (the existing idempotent init method).
- Page is always closed in a `finally` block.
- If `YOUTUBE_PLAYWRIGHT_FALLBACK` is `False`, the method returns `None` immediately.

## Testing

- Test with a real YouTube video URL to verify end-to-end transcript extraction via Playwright.
- Test rate-limit scenario: manually set `_rate_limit_hit_at` and verify Playwright path is taken.
- Test failure scenario: use an invalid video ID and verify graceful `None` return.
- Test config switch: set `YOUTUBE_PLAYWRIGHT_FALLBACK=False` and verify Playwright is not attempted.
