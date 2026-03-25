import yt_dlp
import os
import re
import json
import glob
import time
import httpx
import threading
from typing import Optional, Dict, Any, List
from loguru import logger
from datetime import datetime, timedelta
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.config import settings


class RateLimitError(Exception):
    """Raised when YouTube returns HTTP 429."""


class YouTubeService:
    """Service for downloading and processing YouTube videos.

    Extracts transcripts from subtitles (auto-generated or manual) rather than
    downloading audio, which is much faster and more reliable.  Supports both
    single video URLs and channel/playlist URLs (treated as listing pages).
    """

    CHANNEL_PATTERNS = [
        r'youtube\.com/@[\w.-]+',
        r'youtube\.com/c/[\w.-]+',
        r'youtube\.com/channel/[\w-]+',
        r'youtube\.com/user/[\w.-]+',
    ]
    PLAYLIST_PATTERN = r'youtube\.com/playlist\?list='
    VIDEO_PATTERN = r'(?:youtube\.com/watch\?v=|youtu\.be/)'

    # Default estimate for how long YouTube rate limits last (seconds)
    RATE_LIMIT_WINDOW_SECONDS = 60 * 60  # 60 minutes (conservative)

    def __init__(self):
        self.downloads_dir = settings.DOWNLOADS_DIR
        self._sub_dir = os.path.join(self.downloads_dir, 'subs')
        os.makedirs(self._sub_dir, exist_ok=True)
        self.executor = ThreadPoolExecutor(max_workers=2)

        # Rate limit tracking
        self._rate_limit_hit_at: Optional[datetime] = None
        self._rate_limit_cleared_at: Optional[datetime] = None
        self._last_successful_subtitle_at: Optional[datetime] = None
        self._total_rate_limit_hits: int = 0
        self._rl_lock = threading.Lock()

    def _record_rate_limit(self):
        """Record that a rate limit was hit. Resets the window each time."""
        with self._rl_lock:
            now = datetime.utcnow()
            # Always reset the timer — each new 429 means YouTube is still blocking
            self._rate_limit_hit_at = now
            self._total_rate_limit_hits += 1

    def _record_subtitle_success(self):
        """Record that subtitles were fetched successfully (rate limit cleared)."""
        with self._rl_lock:
            self._rate_limit_hit_at = None
            self._rate_limit_cleared_at = datetime.utcnow()
            self._last_successful_subtitle_at = datetime.utcnow()

    def get_rate_limit_status(self) -> dict:
        """Return current rate limit status for the API."""
        with self._rl_lock:
            now = datetime.utcnow()

            if self._rate_limit_hit_at is None:
                return {
                    'is_rate_limited': False,
                    'since': None,
                    'estimated_reset': None,
                    'last_success': self._last_successful_subtitle_at.isoformat() if self._last_successful_subtitle_at else None,
                    'total_hits': self._total_rate_limit_hits,
                }

            elapsed = (now - self._rate_limit_hit_at).total_seconds()
            estimated_reset = self._rate_limit_hit_at + timedelta(seconds=self.RATE_LIMIT_WINDOW_SECONDS)

            # Auto-clear if the window has passed
            if elapsed >= self.RATE_LIMIT_WINDOW_SECONDS:
                self._rate_limit_hit_at = None
                return {
                    'is_rate_limited': False,
                    'since': None,
                    'estimated_reset': None,
                    'last_success': self._last_successful_subtitle_at.isoformat() if self._last_successful_subtitle_at else None,
                    'total_hits': self._total_rate_limit_hits,
                }

            return {
                'is_rate_limited': True,
                'since': self._rate_limit_hit_at.isoformat(),
                'estimated_reset': estimated_reset.isoformat(),
                'seconds_remaining': int(self.RATE_LIMIT_WINDOW_SECONDS - elapsed),
                'last_success': self._last_successful_subtitle_at.isoformat() if self._last_successful_subtitle_at else None,
                'total_hits': self._total_rate_limit_hits,
            }

    # ------------------------------------------------------------------
    # URL type detection
    # ------------------------------------------------------------------

    def is_channel_or_playlist_url(self, url: str) -> bool:
        """Check if URL points to a YouTube channel or playlist (not a single video)."""
        if re.search(self.VIDEO_PATTERN, url):
            return False
        for pattern in self.CHANNEL_PATTERNS:
            if re.search(pattern, url):
                return True
        if re.search(self.PLAYLIST_PATTERN, url):
            return True
        return False

    def is_video_url(self, url: str) -> bool:
        """Check if URL is a single YouTube video."""
        return bool(re.search(self.VIDEO_PATTERN, url))

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """Extract video ID from a YouTube URL."""
        match = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
        return match.group(1) if match else None

    # ------------------------------------------------------------------
    # Channel / playlist video listing
    # ------------------------------------------------------------------

    def _get_channel_videos_sync(self, url: str, max_results: int = 20) -> Dict[str, Any]:
        """List recent videos from a YouTube channel/playlist (sync)."""
        if re.search(r'youtube\.com/(@[\w.-]+|c/[\w.-]+|channel/[\w-]+|user/[\w.-]+)/?$', url):
            url = url.rstrip('/') + '/videos'

        ydl_opts = {
            'extract_flat': 'in_playlist',
            'playlistend': max_results,
            'quiet': True,
            'no_warnings': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                entries = info.get('entries', [])
                videos: List[Dict[str, Any]] = []
                for entry in entries:
                    if not entry:
                        continue
                    video_id = entry.get('id', '')
                    video_url = entry.get('url') or f"https://www.youtube.com/watch?v={video_id}"
                    videos.append({
                        'url': video_url,
                        'title': entry.get('title', ''),
                        'id': video_id,
                        'duration': entry.get('duration'),
                        'upload_date': entry.get('upload_date'),
                        'timestamp': entry.get('timestamp'),
                    })

                logger.info(f"Listed {len(videos)} videos from channel (requested max {max_results})")
                return {
                    'status': 'success',
                    'channel_title': info.get('title', ''),
                    'videos': videos[:max_results],
                }

        except Exception as e:
            logger.error(f"Error listing channel videos: {e}")
            return {'status': 'error', 'error': str(e)}

    async def get_channel_videos(self, url: str, max_results: int = 20) -> Dict[str, Any]:
        """List recent videos from a YouTube channel (async wrapper)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._get_channel_videos_sync,
            url,
            max_results,
        )

    # ------------------------------------------------------------------
    # Transcript extraction (subtitles-based)
    # ------------------------------------------------------------------

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

    def _try_api_methods_sync(self, url: str, video_id: str, info: dict) -> Optional[str]:
        """Try all API-based subtitle extraction methods (sync). Returns transcript text or None."""
        transcript = None

        # Method A: youtube_transcript_api
        transcript = self._fetch_via_transcript_api(video_id)
        if transcript:
            logger.debug(f"Got transcript via youtube_transcript_api for {video_id}")

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

    async def _get_transcript_async(self, url: str) -> Dict[str, Any]:
        """Extract transcript from a single YouTube video (async).

        Two-phase approach:
        1. Extract metadata via yt-dlp (sync, in executor)
        2. Try subtitle methods — API-based or Playwright fallback

        When rate-limited, skips API methods and goes straight to Playwright.
        """
        loop = asyncio.get_running_loop()

        # Extract video_id from URL directly (reliable even when yt-dlp fails)
        video_id = self.extract_video_id(url)
        if not video_id:
            return {'status': 'error', 'error': f'Cannot extract video ID from URL: {url}'}

        # Phase 1: Get metadata (sync yt-dlp → run in executor)
        metadata_result = await loop.run_in_executor(
            self.executor, self._extract_metadata_sync, url
        )

        info = None
        metadata = {}
        if metadata_result is not None:
            info, metadata = metadata_result
        else:
            logger.warning(f"Metadata extraction failed for {video_id}, will try Playwright only")

        transcript = None
        from_api = False

        # Phase 2: Try to get subtitles
        rl_status = self.get_rate_limit_status()

        if rl_status['is_rate_limited'] or info is None:
            reason = "rate limited" if rl_status['is_rate_limited'] else "metadata extraction failed"
            logger.info(
                f"Skipping API methods ({reason}) — "
                f"using Playwright fallback for {video_id}"
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
                f"Extracted transcript for '{metadata.get('title', video_id)[:60]}': "
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

        # No transcript available — return clear error
        title = metadata.get('title', video_id)
        error_msg = (
            f"Failed to extract transcript for '{title[:60]}'. "
            f"API methods {'skipped (rate limited)' if rl_status['is_rate_limited'] else 'failed'}. "
            f"Playwright fallback {'disabled' if not settings.YOUTUBE_PLAYWRIGHT_FALLBACK else 'failed'}."
        )
        logger.warning(error_msg)
        return {
            'status': 'error',
            'error': error_msg,
            'metadata': metadata,
        }

    def _download_subtitles_via_ytdlp(self, url: str, video_id: str) -> Optional[str]:
        """Try to download subtitles using yt-dlp's built-in downloader.

        Returns parsed subtitle text or None.
        """
        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'en-orig', 'de'],
            'subtitlesformat': 'json3/vtt/srt/best',
            'outtmpl': os.path.join(self._sub_dir, '%(id)s'),
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,  # Don't crash on subtitle download errors
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Read whatever subtitle files were written
            transcript = self._read_subtitle_files(video_id)
            return transcript

        except Exception as e:
            logger.debug(f"yt-dlp subtitle download error: {e}")
            return None

        finally:
            self._cleanup_subtitle_files(video_id)

    def _fetch_via_transcript_api(self, video_id: str) -> Optional[str]:
        """Fetch transcript via youtube_transcript_api (uses a different API endpoint)."""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            from youtube_transcript_api._errors import (
                TranscriptsDisabled, NoTranscriptFound,
                NoTranscriptAvailable,
            )
        except ImportError:
            return None

        try:
            ytt = YouTubeTranscriptApi()
            transcript = ytt.fetch(video_id, languages=['en', 'en-US', 'de'])
            text = ' '.join(entry.text for entry in transcript)
            if text and len(text.strip()) > 50:
                return text
            return None
        except (TranscriptsDisabled, NoTranscriptFound, NoTranscriptAvailable):
            logger.debug(f"No transcript available via API for {video_id}")
            return None
        except Exception as e:
            # IpBlocked, RequestBlocked etc. indicate rate limiting
            if 'block' in type(e).__name__.lower() or 'block' in str(e).lower():
                self._record_rate_limit()
            logger.debug(f"youtube_transcript_api error for {video_id}: {type(e).__name__}")
            return None

    # --- subtitle file helpers -------------------------------------------

    def _read_subtitle_files(self, video_id: str) -> Optional[str]:
        """Read subtitle files downloaded by yt-dlp and return parsed text."""
        if not video_id:
            return None

        pattern = os.path.join(self._sub_dir, f"{video_id}.*")
        sub_files = glob.glob(pattern)

        if not sub_files:
            return None

        # Prefer json3, then vtt, then srt
        sorted_files = sorted(sub_files, key=lambda f: (
            0 if f.endswith('.json3') else
            1 if f.endswith('.vtt') else
            2 if f.endswith('.srt') else 3
        ))

        for filepath in sorted_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    raw = f.read()

                if filepath.endswith('.json3'):
                    text = self._parse_json3_subtitles(raw)
                elif filepath.endswith('.vtt') or filepath.endswith('.srt'):
                    text = self._parse_vtt_srt_subtitles(raw)
                else:
                    continue

                if text and len(text.strip()) > 50:
                    logger.debug(f"Read subtitle file: {os.path.basename(filepath)}")
                    return text

            except Exception as e:
                logger.warning(f"Error reading subtitle file {filepath}: {e}")
                continue

        return None

    def _cleanup_subtitle_files(self, video_id: str):
        """Remove downloaded subtitle files for a video."""
        pattern = os.path.join(self._sub_dir, f"{video_id}.*")
        for filepath in glob.glob(pattern):
            try:
                os.remove(filepath)
            except OSError:
                pass

    # --- manual subtitle URL fetching (fallback) -------------------------

    def _extract_subtitles(self, info: dict) -> Optional[str]:
        """Try to extract subtitle text by manually fetching subtitle URLs."""
        for source_key, limit_langs in [('subtitles', False), ('automatic_captions', True)]:
            source_dict = info.get(source_key, {})
            if not source_dict:
                continue

            ordered_langs: List[str] = []
            for prefix in ['en', 'de']:
                for lang_key in source_dict:
                    if lang_key.startswith(prefix) and lang_key not in ordered_langs:
                        ordered_langs.append(lang_key)

            if not limit_langs:
                for lang_key in source_dict:
                    if lang_key not in ordered_langs:
                        ordered_langs.append(lang_key)

            try:
                for lang in ordered_langs:
                    formats = source_dict[lang]
                    for preferred_ext in ['json3', 'vtt', 'srt']:
                        for fmt in formats:
                            if fmt.get('ext') == preferred_ext:
                                sub_url = fmt.get('url')
                                if sub_url:
                                    text = self._fetch_subtitle_content(sub_url, preferred_ext)
                                    if text and len(text.strip()) > 50:
                                        return text
            except RateLimitError:
                logger.warning("YouTube rate-limited subtitle requests, stopping manual fetch")
                return None

        return None

    def _fetch_subtitle_content(self, url: str, ext: str) -> Optional[str]:
        """Fetch raw subtitle file and convert to plain text.

        Retries once after a short delay on HTTP 429.
        """
        for attempt in range(2):
            try:
                with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                    response = client.get(url)
                    if response.status_code == 429:
                        self._record_rate_limit()
                        if attempt == 0:
                            logger.debug("Subtitle 429, waiting 5s before retry...")
                            time.sleep(5)
                            continue
                        raise RateLimitError("YouTube subtitle rate limit (429)")
                    if response.status_code != 200:
                        logger.warning(f"Subtitle fetch failed: HTTP {response.status_code}")
                        return None
                    raw_text = response.text

                if ext == 'json3':
                    return self._parse_json3_subtitles(raw_text)
                return self._parse_vtt_srt_subtitles(raw_text)

            except RateLimitError:
                raise
            except Exception as e:
                logger.error(f"Error fetching subtitle content: {e}")
                return None

        return None

    @staticmethod
    def _parse_json3_subtitles(raw: str) -> Optional[str]:
        """Parse YouTube json3 subtitle format into plain text."""
        try:
            data = json.loads(raw)
            events = data.get('events', [])
            segments: List[str] = []
            for event in events:
                for seg in event.get('segs', []):
                    text = seg.get('utf8', '').strip()
                    if text and text != '\n':
                        segments.append(text)
            return ' '.join(segments)
        except Exception as e:
            logger.error(f"Error parsing json3 subtitles: {e}")
            return None

    @staticmethod
    def _parse_vtt_srt_subtitles(raw: str) -> str:
        """Parse VTT/SRT subtitle content into deduplicated plain text."""
        lines = raw.split('\n')
        text_lines: List[str] = []
        seen: set = set()

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:'):
                continue
            if '-->' in line:
                continue
            if re.match(r'^\d+$', line):
                continue
            line = re.sub(r'<[^>]+>', '', line)
            line = re.sub(r'\{[^}]+\}', '', line).strip()
            if line and line not in seen:
                seen.add(line)
                text_lines.append(line)

        return ' '.join(text_lines)

    # --- description cleaning -------------------------------------------

    @staticmethod
    def _clean_description(description: str) -> str:
        """Extract useful financial content from a YouTube video description.

        Keeps: lines mentioning stock tickers, company names, timestamps/topics.
        Removes: boilerplate disclaimers, affiliate disclosures, generic warnings.
        """
        if not description:
            return ''

        # Patterns indicating boilerplate to skip
        skip_patterns = [
            'not financial advice', 'financial advisor', 'at your own risk',
            'affiliate disclosure', 'affiliate link', 'full terms of service',
            'full disclaimer', 'see full disclosures', 'most traders',
            'most small businesses fail', 'do not partake', 'past performance',
            'not indicative of future', 'consult with a qualified',
            'use at your own risk', 'by using ziptrader', 'not suitable for all',
            'do your own due diligence', 'all content you agree',
            'additional cost to you', 'the stock market is risky',
            'results are not guaranteed', 'trading is risky',
            'we do not provide personalized',
        ]

        # Patterns indicating useful financial content to keep
        ticker_pattern = re.compile(
            r'\((?:NASDAQ|NYSE|NYSEAMERICAN|AMEX|OTC)[:\s]+[A-Z]{1,6}\)'
            r'|\$[A-Z]{1,6}\b'
            r'|(?:NASDAQ|NYSE):\s*[A-Z]{1,6}'
        )

        kept_lines: List[str] = []
        lines = description.split('\n')

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            lower = stripped.lower()

            # Skip URL lines (including "Learn More: https://..." style)
            if stripped.startswith('http://') or stripped.startswith('https://'):
                continue
            if re.match(r'^(learn more|sign up|click here|join)\s*[:\-➤►→]?\s*http', lower):
                continue

            # Skip separator lines
            if re.match(r'^[-=_]{5,}$', stripped):
                continue

            # Skip promotional/social media lines with URLs
            if ('http://' in stripped or 'https://' in stripped) and not ticker_pattern.search(stripped):
                continue

            # Skip boilerplate
            if any(pat in lower for pat in skip_patterns):
                continue

            # Skip very long legal/disclaimer paragraphs (> 200 chars without tickers)
            if len(stripped) > 200 and not ticker_pattern.search(stripped):
                continue

            # Keep lines with stock tickers (high value for NER)
            if ticker_pattern.search(stripped):
                kept_lines.append(stripped)
                continue

            # Keep timestamp lines (indicate video topics)
            if re.match(r'^\d{1,2}:\d{2}', stripped):
                kept_lines.append(stripped)
                continue

            # Keep short descriptive lines (likely topic descriptions)
            if 5 < len(stripped) < 150:
                # Skip lines that are just hashtags, social media handles, or emails
                if stripped.startswith('#') or stripped.startswith('@'):
                    continue
                if '@' in stripped and '.' in stripped and len(stripped) < 60:
                    continue
                kept_lines.append(stripped)

        return '\n'.join(kept_lines)

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

            # Wait for YouTube's JS to render the page (consent dialogs, UI elements)
            # domcontentloaded fires before YouTube's heavy JS finishes loading
            await page.wait_for_timeout(3000)

            # Dismiss cookie consent if present (reuse existing handler)
            await web_scraper.handle_cookie_banner(page)

            # Wait for the page content to settle after consent dismissal
            await page.wait_for_timeout(2000)

            # Scroll down to the description area so elements are in view
            await page.evaluate('window.scrollBy(0, 400)')
            await page.wait_for_timeout(500)

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
                    btn = transcript_section.first
                    if await btn.is_visible(timeout=3000):
                        transcript_btn = btn
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
            # YouTube uses transcript-segment-view-model (current) or
            # ytd-transcript-segment-renderer (legacy) for segments
            segment_selector = None
            for sel in ['transcript-segment-view-model', 'ytd-transcript-segment-renderer']:
                try:
                    await page.wait_for_selector(sel, timeout=10000)
                    segment_selector = sel
                    break
                except Exception:
                    continue

            if not segment_selector:
                logger.info(f"Playwright fallback: transcript panel empty/timeout for {video_id}")
                return None

            # Extract text from transcript segments
            # Current YouTube uses <span class="yt-core-attributed-string"> for text
            # Legacy uses .segment-text or yt-formatted-string
            segments = await page.locator(
                f'{segment_selector} span.yt-core-attributed-string'
            ).all_text_contents()

            if not segments:
                segments = await page.locator(
                    f'{segment_selector} .segment-text'
                ).all_text_contents()

            if not segments:
                segments = await page.locator(
                    f'{segment_selector} yt-formatted-string'
                ).all_text_contents()

            if not segments:
                # Last resort: get all text from segments (includes timestamps)
                segments = await page.locator(segment_selector).all_text_contents()

            if not segments:
                logger.info(f"Playwright fallback: no transcript text found for {video_id}")
                return None

            # Clean and join segments — remove timestamps and duplicates
            cleaned = []
            seen = set()
            for seg in segments:
                text = seg.strip()
                # Skip empty, pure timestamps (e.g. "0:18"), and a11y labels (e.g. "18 seconds")
                if not text:
                    continue
                if re.match(r'^\d+:\d{2}$', text):
                    continue
                if re.match(r'^\d+\s*(seconds?|minutes?)$', text):
                    continue
                if text not in seen:
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

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def get_video_transcript(self, url: str) -> Dict[str, Any]:
        """Get transcript for a single YouTube video."""
        return await self._get_transcript_async(url)

    async def process_youtube_url(self, url: str) -> Dict[str, Any]:
        """Process a single YouTube video URL — main entry point for the workflow."""
        return await self.get_video_transcript(url)


# Singleton instance
youtube_service = YouTubeService()
