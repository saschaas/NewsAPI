import yt_dlp
import os
import re
import json
import httpx
from typing import Optional, Dict, Any, List
from loguru import logger
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.config import settings


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

    def __init__(self):
        self.downloads_dir = settings.DOWNLOADS_DIR
        self.executor = ThreadPoolExecutor(max_workers=2)

    # ------------------------------------------------------------------
    # URL type detection
    # ------------------------------------------------------------------

    def is_channel_or_playlist_url(self, url: str) -> bool:
        """Check if URL points to a YouTube channel or playlist (not a single video)."""
        # A video URL on a channel page is still a single video
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

    # ------------------------------------------------------------------
    # Channel / playlist video listing
    # ------------------------------------------------------------------

    def _get_channel_videos_sync(self, url: str, max_results: int = 20) -> Dict[str, Any]:
        """List recent videos from a YouTube channel/playlist (sync)."""
        # Append /videos for bare channel URLs so yt_dlp lists uploads
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

    def _get_transcript_sync(self, url: str) -> Dict[str, Any]:
        """Extract transcript from a single YouTube video via subtitles (sync)."""
        ydl_opts = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                metadata = {
                    'title': info.get('title', ''),
                    'author': info.get('uploader', '') or info.get('channel', ''),
                    'duration': info.get('duration', 0),
                    'description': info.get('description', ''),
                    'upload_date': info.get('upload_date', ''),
                    'view_count': info.get('view_count', 0),
                }

                # Try subtitle-based transcript
                transcript = self._extract_subtitles(info)

                if transcript and len(transcript.strip()) > 50:
                    logger.info(
                        f"Extracted subtitle transcript for '{metadata['title'][:60]}': "
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

                # Fallback: use video description if substantial
                description = info.get('description', '')
                if description and len(description) > 100:
                    logger.info(
                        f"No subtitles for '{metadata['title'][:60]}', "
                        f"using description ({len(description)} chars)"
                    )
                    return {
                        'status': 'success',
                        'url': url,
                        'transcript': description,
                        'raw_content': description,
                        'metadata': metadata,
                        'fetched_at': datetime.utcnow().isoformat(),
                    }

                return {
                    'status': 'error',
                    'error': 'No subtitles or substantial description available',
                    'metadata': metadata,
                }

        except Exception as e:
            logger.error(f"Error extracting transcript from {url}: {e}")
            return {'status': 'error', 'error': str(e)}

    # --- subtitle helpers ------------------------------------------------

    def _extract_subtitles(self, info: dict) -> Optional[str]:
        """Try to extract subtitle text from yt_dlp video info dict."""
        # Manual subtitles are higher quality; try them first
        for source_dict in [info.get('subtitles', {}), info.get('automatic_captions', {})]:
            if not source_dict:
                continue

            # Build a language priority order
            ordered_langs: List[str] = []
            for prefix in ['de', 'en']:
                for lang_key in source_dict:
                    if lang_key.startswith(prefix) and lang_key not in ordered_langs:
                        ordered_langs.append(lang_key)
            # Then any remaining language
            for lang_key in source_dict:
                if lang_key not in ordered_langs:
                    ordered_langs.append(lang_key)

            for lang in ordered_langs:
                formats = source_dict[lang]
                # Prefer json3 (cleanest parse), then vtt, then srt
                for preferred_ext in ['json3', 'vtt', 'srt']:
                    for fmt in formats:
                        if fmt.get('ext') == preferred_ext:
                            sub_url = fmt.get('url')
                            if sub_url:
                                text = self._fetch_subtitle_content(sub_url, preferred_ext)
                                if text and len(text.strip()) > 50:
                                    return text
        return None

    def _fetch_subtitle_content(self, url: str, ext: str) -> Optional[str]:
        """Fetch raw subtitle file and convert to plain text."""
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.get(url)
                if response.status_code != 200:
                    logger.warning(f"Subtitle fetch failed: HTTP {response.status_code}")
                    return None
                raw_text = response.text

            if ext == 'json3':
                return self._parse_json3_subtitles(raw_text)
            return self._parse_vtt_srt_subtitles(raw_text)

        except Exception as e:
            logger.error(f"Error fetching subtitle content: {e}")
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
            # Skip VTT/SRT structural lines
            if line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:'):
                continue
            if '-->' in line:
                continue
            if re.match(r'^\d+$', line):
                continue
            # Strip HTML tags and VTT positioning cues
            line = re.sub(r'<[^>]+>', '', line)
            line = re.sub(r'\{[^}]+\}', '', line).strip()
            if line and line not in seen:
                seen.add(line)
                text_lines.append(line)

        return ' '.join(text_lines)

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def get_video_transcript(self, url: str) -> Dict[str, Any]:
        """Get transcript for a single YouTube video (async wrapper)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._get_transcript_sync,
            url,
        )

    async def process_youtube_url(self, url: str) -> Dict[str, Any]:
        """Process a single YouTube video URL — main entry point for the workflow."""
        return await self.get_video_transcript(url)


# Singleton instance
youtube_service = YouTubeService()
