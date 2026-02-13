import yt_dlp
import os
from typing import Optional, Dict, Any
from loguru import logger
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.config import settings
from app.services.ollama import ollama_service


class YouTubeService:
    """Service for downloading and processing YouTube videos"""

    def __init__(self):
        self.downloads_dir = settings.DOWNLOADS_DIR
        self.executor = ThreadPoolExecutor(max_workers=2)

    def _download_audio_sync(self, url: str, output_path: str) -> Dict[str, Any]:
        """
        Synchronous download of YouTube audio (runs in thread pool)

        Args:
            url: YouTube URL
            output_path: Path to save audio file

        Returns:
            Dict with status and info
        """
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_path,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

                return {
                    'status': 'success',
                    'title': info.get('title', ''),
                    'author': info.get('uploader', ''),
                    'duration': info.get('duration', 0),
                    'description': info.get('description', ''),
                    'upload_date': info.get('upload_date', ''),
                    'view_count': info.get('view_count', 0),
                }

        except Exception as e:
            logger.error(f"Error downloading YouTube audio: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

    async def download_audio(self, url: str) -> Dict[str, Any]:
        """
        Download audio from YouTube video

        Args:
            url: YouTube URL

        Returns:
            Dict with download status, file path, and metadata
        """
        # Create unique filename based on timestamp
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"youtube_{timestamp}"
        output_path = os.path.join(self.downloads_dir, filename)

        # Ensure downloads directory exists
        os.makedirs(self.downloads_dir, exist_ok=True)

        logger.info(f"Downloading YouTube audio from {url}")

        # Run download in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.executor,
            self._download_audio_sync,
            url,
            output_path
        )

        if result['status'] == 'success':
            # yt-dlp adds .mp3 extension
            actual_path = f"{output_path}.mp3"
            result['file_path'] = actual_path
            result['url'] = url

        return result

    async def transcribe_audio(self, audio_path: str) -> Optional[str]:
        """
        Transcribe audio file using Whisper via Ollama

        Args:
            audio_path: Path to audio file

        Returns:
            Transcribed text or None
        """
        logger.info(f"Transcribing audio: {audio_path}")

        try:
            # Note: Actual Whisper integration via Ollama may vary
            # This is a placeholder that should be adjusted based on
            # Ollama's Whisper implementation

            transcript = await ollama_service.transcribe_audio(audio_path)

            if transcript:
                logger.info(f"Transcription completed: {len(transcript)} characters")
                return transcript
            else:
                logger.error("Transcription failed: no output")
                return None

        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return None

    def cleanup_audio_file(self, file_path: str) -> bool:
        """
        Delete audio file after processing

        Args:
            file_path: Path to audio file

        Returns:
            True if deleted successfully
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up audio file: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error cleaning up audio file {file_path}: {e}")
            return False

    async def process_youtube_url(self, url: str) -> Dict[str, Any]:
        """
        Full pipeline: download, transcribe, and cleanup

        Args:
            url: YouTube URL

        Returns:
            Dict with transcript, metadata, and status
        """
        # Download audio
        download_result = await self.download_audio(url)

        if download_result['status'] != 'success':
            return download_result

        file_path = download_result['file_path']

        try:
            # Transcribe
            transcript = await self.transcribe_audio(file_path)

            if not transcript:
                return {
                    'status': 'error',
                    'error': 'Transcription failed',
                    'metadata': {k: v for k, v in download_result.items() if k != 'file_path'}
                }

            # Extract metadata
            metadata = {
                'title': download_result.get('title', ''),
                'author': download_result.get('author', ''),
                'duration': download_result.get('duration', 0),
                'description': download_result.get('description', ''),
                'upload_date': download_result.get('upload_date', ''),
                'view_count': download_result.get('view_count', 0),
            }

            return {
                'status': 'success',
                'url': url,
                'transcript': transcript,
                'raw_content': transcript,
                'metadata': metadata,
                'fetched_at': datetime.utcnow().isoformat()
            }

        finally:
            # Always cleanup the audio file
            self.cleanup_audio_file(file_path)


# Singleton instance
youtube_service = YouTubeService()
