# YouTube Playwright Transcript Fallback — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Playwright-based transcript extraction fallback to YouTubeService that activates when API methods are rate-limited or fail.

**Architecture:** The existing `_get_transcript_sync` method is refactored into an async `_get_transcript_async` that interleaves sync yt-dlp calls (via executor) with an async Playwright fallback. The Playwright method lazy-imports `web_scraper` to avoid circular imports, opens a YouTube watch page, clicks "Show transcript", and extracts text from the DOM panel.

**Tech Stack:** Python, Playwright (already installed), existing WebScraperService infrastructure

**Spec:** `docs/superpowers/specs/2026-03-25-youtube-playwright-fallback-design.md`

---

### Task 1: Add config setting

**Files:**
- Modify: `backend/app/config.py` (add setting after `YOUTUBE_MAX_VIDEO_AGE_DAYS`)
- Modify: `backend/.env.example` (document new setting)

- [ ] **Step 1: Add `YOUTUBE_PLAYWRIGHT_FALLBACK` to Settings**

In `backend/app/config.py`, add after the `YOUTUBE_MAX_VIDEO_AGE_DAYS` line:

```python
YOUTUBE_PLAYWRIGHT_FALLBACK: bool = True
```

- [ ] **Step 2: Add setting to .env.example**

In `backend/.env.example`, add after the `YOUTUBE_MAX_VIDEO_AGE_DAYS` line:

```
YOUTUBE_PLAYWRIGHT_FALLBACK=true
```

- [ ] **Step 3: Verify config loads**

Run: `cd /d/Docs/Coding/NewsAPI/backend && python -c "from app.config import settings; print(settings.YOUTUBE_PLAYWRIGHT_FALLBACK)"`
Expected: `True`

- [ ] **Step 4: Commit**

```bash
cd /d/Docs/Coding/NewsAPI
git add backend/app/config.py backend/.env.example
git commit -m "feat: add YOUTUBE_PLAYWRIGHT_FALLBACK config setting"
```

---

### Task 2: Extract sync helpers from `_get_transcript_sync`

**Files:**
- Modify: `backend/app/services/youtube.py` (add two methods before the `_get_transcript_sync` method)

The existing `_get_transcript_sync` does both metadata extraction and subtitle fetching in one sync method. We split it into two sync helpers so the new async orchestrator can call them individually via executor and interleave with the async Playwright fallback.

- [ ] **Step 1: Add `_extract_metadata_sync` method**

Add this method to the `YouTubeService` class, immediately before the `_get_transcript_sync` method:

```python
    def _extract_metadata_sync(self, url: str) -> Optional[tuple]:
        """Extract video metadata via yt-dlp (sync). Returns (info_dict, metadata) or None."""
        ydl_opts_meta = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts_meta) as ydl:
                info = ydl.extract_info(url, download=False)

            metadata = {
                'title': info.get('title', ''),
                'author': info.get('uploader', '') or info.get('channel', ''),
                'duration': info.get('duration', 0),
                'description': info.get('description', ''),
                'upload_date': info.get('upload_date', ''),
                'view_count': info.get('view_count', 0),
            }
            return (info, metadata)
        except Exception as e:
            logger.error(f"Error extracting metadata from {url}: {e}")
            return None
```

- [ ] **Step 2: Add `_try_api_methods_sync` method**

Add this method right after `_extract_metadata_sync`:

```python
    def _try_api_methods_sync(self, url: str, video_id: str, info: dict) -> Optional[str]:
        """Try all API-based subtitle extraction methods (sync). Returns transcript text or None."""
        transcript = None

        # Method A: youtube_transcript_api
        try:
            transcript = self._fetch_via_transcript_api(video_id)
            if transcript:
                logger.debug(f"Got transcript via youtube_transcript_api for {video_id}")
        except Exception as e:
            logger.debug(f"youtube_transcript_api failed for {video_id}: {e}")

        # Method B: yt-dlp built-in subtitle download
        if not transcript or len(transcript.strip()) <= 50:
            try:
                transcript = self._download_subtitles_via_ytdlp(url, video_id)
            except Exception as e:
                logger.debug(f"yt-dlp subtitle download failed for {video_id}: {e}")

        # Method C: Manual subtitle URL fetching
        if not transcript or len(transcript.strip()) <= 50:
            transcript = self._extract_subtitles(info)

        if transcript and len(transcript.strip()) > 50:
            return transcript

        return None
```

- [ ] **Step 3: Verify syntax**

Run: `cd /d/Docs/Coding/NewsAPI/backend && python -c "from app.services.youtube import YouTubeService; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd /d/Docs/Coding/NewsAPI
git add backend/app/services/youtube.py
git commit -m "refactor: extract metadata and API subtitle helpers from _get_transcript_sync"
```

---

### Task 3: Replace `_get_transcript_sync` with async orchestrator

**Files:**
- Modify: `backend/app/services/youtube.py` (replace the `_get_transcript_sync` method, update `get_video_transcript` and `process_youtube_url`)

- [ ] **Step 1: Replace `_get_transcript_sync` with `_get_transcript_async`**

Delete the entire `_get_transcript_sync` method and replace it with:

```python
    async def _get_transcript_async(self, url: str) -> Dict[str, Any]:
        """Extract transcript from a single YouTube video (async).

        Two-phase approach:
        1. Extract metadata via yt-dlp (sync, in executor)
        2. Try subtitle methods — API-based or Playwright fallback

        When rate-limited, skips API methods and goes straight to Playwright.
        """
        loop = asyncio.get_running_loop()

        # Phase 1: Get metadata (sync yt-dlp → run in executor)
        result = await loop.run_in_executor(
            self.executor, self._extract_metadata_sync, url
        )
        if result is None:
            return {'status': 'error', 'error': 'Metadata extraction failed'}

        info, metadata = result
        video_id = info.get('id', '')
        transcript = None
        from_api = False

        # Phase 2: Try to get subtitles
        rl_status = self.get_rate_limit_status()

        if rl_status['is_rate_limited']:
            logger.info(
                f"Rate limited ({rl_status.get('seconds_remaining', '?')}s remaining) — "
                f"using Playwright fallback for '{metadata['title'][:60]}'"
            )
            # Skip API methods, go straight to Playwright
            transcript = await self._fetch_via_playwright(video_id)
        else:
            # Try API methods A/B/C (sync → run in executor)
            transcript = await loop.run_in_executor(
                self.executor, self._try_api_methods_sync, url, video_id, info
            )

            if transcript:
                from_api = True
            else:
                # API methods failed → try Playwright fallback
                logger.info(f"API methods failed for {video_id}, trying Playwright fallback")
                transcript = await self._fetch_via_playwright(video_id)

        if transcript and len(transcript.strip()) > 50:
            # Only record subtitle success on API success — Playwright success
            # must NOT clear the rate-limit flag (spec requirement)
            if from_api:
                self._record_subtitle_success()
            logger.info(
                f"Extracted transcript for '{metadata['title'][:60]}': "
                f"{len(transcript)} chars"
            )
            return {
                'status': 'success',
                'url': url,
                'transcript': transcript,
                'raw_content': transcript,
                'metadata': metadata,
                'fetched_at': datetime.utcnow().isoformat(),
            }

        # No transcript available — skip video
        title = metadata.get('title', '')
        logger.warning(
            f"No subtitles for '{title[:60]}', skipping video (will retry next run)"
        )
        return {
            'status': 'error',
            'error': 'No subtitles available',
            'metadata': metadata,
        }
```

- [ ] **Step 2: Update public API methods to call the async method directly**

Replace the `get_video_transcript` and `process_youtube_url` methods with:

```python
    async def get_video_transcript(self, url: str) -> Dict[str, Any]:
        """Get transcript for a single YouTube video."""
        return await self._get_transcript_async(url)

    async def process_youtube_url(self, url: str) -> Dict[str, Any]:
        """Process a single YouTube video URL — main entry point for the workflow."""
        return await self.get_video_transcript(url)
```

- [ ] **Step 3: Verify syntax and imports**

Run: `cd /d/Docs/Coding/NewsAPI/backend && python -c "from app.services.youtube import YouTubeService; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd /d/Docs/Coding/NewsAPI
git add backend/app/services/youtube.py
git commit -m "feat: replace sync transcript method with async orchestrator"
```

---

### Task 4: Add `_fetch_via_playwright` method

**Files:**
- Modify: `backend/app/services/youtube.py` (add new async method after `_clean_description`, before the `# Public async API` section)

- [ ] **Step 1: Add the Playwright transcript extraction method**

Add the following method to the `YouTubeService` class, after the `_clean_description` method and before the `# Public async API` comment:

```python
    # --- Playwright-based transcript fallback ----------------------------

    async def _fetch_via_playwright(self, video_id: str) -> Optional[str]:
        """Fetch transcript by opening YouTube in a browser and clicking 'Show transcript'.

        Uses the existing WebScraperService's Playwright browser context for
        stealth injection, UA rotation, and proxy support.

        Returns transcript text or None on any failure.
        """
        if not settings.YOUTUBE_PLAYWRIGHT_FALLBACK:
            logger.debug("Playwright fallback disabled by config")
            return None

        if not video_id:
            return None

        # Lazy import to avoid circular dependency (both modules are imported
        # side-by-side in services/__init__.py)
        from app.services.scraping import web_scraper

        url = f"https://www.youtube.com/watch?v={video_id}"
        page = None

        try:
            # Ensure browser is initialized
            await web_scraper.initialize()

            if not web_scraper.context:
                logger.warning("Playwright fallback: no browser context available")
                return None

            page = await web_scraper.context.new_page()

            # Navigate to the video page
            logger.info(f"Playwright fallback: loading {url}")
            await page.goto(url, timeout=30000, wait_until='domcontentloaded')

            # Dismiss cookie consent if present (reuse existing handler)
            await web_scraper.handle_cookie_banner(page)

            # Wait for the page content to settle
            await page.wait_for_timeout(2000)

            # Expand description if collapsed (transcript button may be hidden)
            try:
                more_btn = page.locator('tp-yt-paper-button#expand')
                if await more_btn.count() > 0 and await more_btn.first.is_visible(timeout=2000):
                    await more_btn.first.click()
                    await page.wait_for_timeout(1000)
            except Exception:
                pass

            # Try to find and click the "Show transcript" button
            # It lives inside ytd-video-description-transcript-section-renderer
            transcript_btn = None

            # Primary selector: the button in the transcript section
            try:
                transcript_section = page.locator('ytd-video-description-transcript-section-renderer button')
                if await transcript_section.count() > 0:
                    transcript_btn = transcript_section.first
            except Exception:
                pass

            # Fallback selector: look for button with "transcript" text
            if transcript_btn is None:
                try:
                    transcript_btn = page.locator('button:has-text("Show transcript")').first
                    if not await transcript_btn.is_visible(timeout=3000):
                        transcript_btn = None
                except Exception:
                    transcript_btn = None

            if transcript_btn is None:
                logger.info(f"Playwright fallback: no transcript button found for {video_id}")
                return None

            # Click the transcript button
            await transcript_btn.click()
            logger.debug(f"Playwright fallback: clicked 'Show transcript' for {video_id}")

            # Wait for transcript segments to load
            try:
                await page.wait_for_selector(
                    'ytd-transcript-segment-renderer',
                    timeout=10000
                )
            except Exception:
                logger.info(f"Playwright fallback: transcript panel empty/timeout for {video_id}")
                return None

            # Extract text from all transcript segments
            segments = await page.locator(
                'ytd-transcript-segment-renderer .segment-text'
            ).all_text_contents()

            if not segments:
                # Try alternative selector
                segments = await page.locator(
                    'ytd-transcript-segment-renderer yt-formatted-string'
                ).all_text_contents()

            if not segments:
                logger.info(f"Playwright fallback: no transcript text found for {video_id}")
                return None

            # Clean and join segments
            cleaned = []
            seen = set()
            for seg in segments:
                text = seg.strip()
                if text and text not in seen:
                    seen.add(text)
                    cleaned.append(text)

            transcript = ' '.join(cleaned)

            if len(transcript.strip()) > 50:
                logger.info(
                    f"Playwright fallback: extracted {len(transcript)} chars for {video_id}"
                )
                return transcript

            logger.info(f"Playwright fallback: transcript too short ({len(transcript)} chars) for {video_id}")
            return None

        except Exception as e:
            logger.warning(f"Playwright fallback error for {video_id}: {type(e).__name__}: {e}")
            return None

        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
```

- [ ] **Step 2: Verify syntax**

Run: `cd /d/Docs/Coding/NewsAPI/backend && python -c "from app.services.youtube import YouTubeService; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /d/Docs/Coding/NewsAPI
git add backend/app/services/youtube.py
git commit -m "feat: add Playwright-based transcript fallback method"
```

---

### Task 5: Test with real YouTube videos

**Files:**
- No file changes — manual testing via Python scripts

- [ ] **Step 1: Test normal API path (not rate-limited)**

Run: `cd /d/Docs/Coding/NewsAPI/backend && python -c "
import asyncio
from app.services.youtube import youtube_service

async def test():
    # Use a well-known video that has auto-generated captions
    result = await youtube_service.get_video_transcript('https://www.youtube.com/watch?v=dQw4w9WgXcQ')
    print(f'Status: {result[\"status\"]}')
    if result['status'] == 'success':
        print(f'Transcript length: {len(result[\"transcript\"])} chars')
        print(f'First 200 chars: {result[\"transcript\"][:200]}')
    else:
        print(f'Error: {result.get(\"error\", \"unknown\")}')

asyncio.run(test())
"`

Expected: `Status: success` with transcript content (API methods should work when not rate-limited).

- [ ] **Step 2: Test Playwright fallback by simulating rate limit**

Run: `cd /d/Docs/Coding/NewsAPI/backend && python -c "
import asyncio
from datetime import datetime
from app.services.youtube import youtube_service

async def test_playwright():
    # Force rate-limit state so Playwright path is taken
    youtube_service._rate_limit_hit_at = datetime.utcnow()
    youtube_service._total_rate_limit_hits = 1

    rl = youtube_service.get_rate_limit_status()
    print(f'Rate limited: {rl[\"is_rate_limited\"]}')

    result = await youtube_service.get_video_transcript('https://www.youtube.com/watch?v=dQw4w9WgXcQ')
    print(f'Status: {result[\"status\"]}')
    if result['status'] == 'success':
        print(f'Transcript length: {len(result[\"transcript\"])} chars')
        print(f'First 200 chars: {result[\"transcript\"][:200]}')
    else:
        print(f'Error: {result.get(\"error\", \"unknown\")}')

    # Verify rate-limit flag was NOT cleared by Playwright
    rl2 = youtube_service.get_rate_limit_status()
    print(f'Still rate limited: {rl2[\"is_rate_limited\"]}')

asyncio.run(test_playwright())
"`

Expected:
- `Rate limited: True`
- `Status: success` (via Playwright)
- `Still rate limited: True` (Playwright does NOT clear the flag)

- [ ] **Step 3: Test with Playwright fallback disabled**

Run: `cd /d/Docs/Coding/NewsAPI/backend && python -c "
import asyncio
from datetime import datetime
from app.services.youtube import youtube_service
from app.config import settings

async def test_disabled():
    # Disable Playwright fallback
    settings.YOUTUBE_PLAYWRIGHT_FALLBACK = False
    # Force rate-limit
    youtube_service._rate_limit_hit_at = datetime.utcnow()

    result = await youtube_service.get_video_transcript('https://www.youtube.com/watch?v=dQw4w9WgXcQ')
    print(f'Status: {result[\"status\"]}')
    print(f'Error: {result.get(\"error\", \"none\")}')

    # Reset
    settings.YOUTUBE_PLAYWRIGHT_FALLBACK = True
    youtube_service._rate_limit_hit_at = None

asyncio.run(test_disabled())
"`

Expected: `Status: error` (Playwright disabled, API skipped due to rate limit)

- [ ] **Step 4: Test with invalid video ID**

Run: `cd /d/Docs/Coding/NewsAPI/backend && python -c "
import asyncio
from datetime import datetime
from app.services.youtube import youtube_service

async def test_invalid():
    # Force rate-limit so Playwright path is taken
    youtube_service._rate_limit_hit_at = datetime.utcnow()

    result = await youtube_service.get_video_transcript('https://www.youtube.com/watch?v=INVALID_ID_123')
    print(f'Status: {result[\"status\"]}')
    print(f'Error: {result.get(\"error\", \"none\")}')

    # Reset
    youtube_service._rate_limit_hit_at = None

asyncio.run(test_invalid())
"`

Expected: `Status: error` (graceful failure, no crash)

- [ ] **Step 5: Commit (final)**

```bash
cd /d/Docs/Coding/NewsAPI
git add -A
git commit -m "feat: YouTube Playwright transcript fallback — complete implementation

Add Playwright-based fallback for YouTube transcript extraction that
activates when subtitle API methods are rate-limited or fail. Uses
existing WebScraperService browser context for stealth/proxy support.

- When rate-limited: skips API, goes straight to Playwright
- When API fails: falls back to Playwright automatically
- Playwright success does NOT clear rate-limit flag
- Configurable via YOUTUBE_PLAYWRIGHT_FALLBACK setting"
```
