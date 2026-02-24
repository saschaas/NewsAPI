"""
RSS feed fetching and parsing service.

Provides RSS feed support as an alternative to browser-based scraping,
bypassing anti-bot detection entirely for sites that publish RSS feeds.

The lightweight article fetch (fetch_entry_content) uses curl_cffi for
TLS fingerprint impersonation, making it effective against sites that
only check at the TLS layer (Tier 1 Cloudflare bypass).

Known RSS feeds:
    MarketWatch:
        - https://www.marketwatch.com/rss/topstories
        - https://www.marketwatch.com/rss/marketpulse
"""

import aiohttp
import feedparser
from typing import Optional, Dict, Any, List
from loguru import logger
from datetime import datetime

from app.config import settings
from app.services.scraping import WebScraperService


class RSSService:
    """Service for fetching and parsing RSS feeds."""

    async def fetch_feed(self, feed_url: str) -> Dict[str, Any]:
        """
        Fetch and parse an RSS feed.

        Args:
            feed_url: URL of the RSS feed

        Returns:
            Dictionary with status, entries list, and feed metadata.
            Each entry has: title, url, summary, published, author
        """
        try:
            logger.info(f"Fetching RSS feed: {feed_url}")

            async with aiohttp.ClientSession() as session:
                headers = {
                    "User-Agent": "Mozilla/5.0 (compatible; StockNewsBot/1.0)",
                    "Accept": "application/rss+xml, application/xml, text/xml, */*",
                }
                async with session.get(
                    feed_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=settings.RSS_REQUEST_TIMEOUT),
                ) as response:
                    if response.status != 200:
                        logger.error(f"RSS feed returned HTTP {response.status}: {feed_url}")
                        return {
                            "status": "error",
                            "error": f"HTTP {response.status}",
                            "entries": [],
                        }

                    content = await response.text()

            # Parse the feed
            feed = feedparser.parse(content)

            if feed.bozo and not feed.entries:
                logger.error(f"RSS feed parse error: {feed.bozo_exception}")
                return {
                    "status": "error",
                    "error": f"Parse error: {feed.bozo_exception}",
                    "entries": [],
                }

            entries = []
            for entry in feed.entries:
                parsed_entry = {
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "summary": entry.get("summary", ""),
                    "published": entry.get("published", ""),
                    "author": entry.get("author", ""),
                }
                if parsed_entry["url"]:
                    entries.append(parsed_entry)

            logger.info(f"RSS feed parsed: {len(entries)} entries from {feed_url}")

            return {
                "status": "success",
                "feed_title": feed.feed.get("title", ""),
                "entries": entries,
            }

        except aiohttp.ClientError as e:
            logger.error(f"RSS feed network error: {e}")
            return {"status": "error", "error": str(e), "entries": []}
        except Exception as e:
            logger.error(f"RSS feed error: {e}")
            return {"status": "error", "error": str(e), "entries": []}

    async def _curl_cffi_fetch(self, entry_url: str) -> Optional[str]:
        """
        Fetch HTML using curl_cffi with browser TLS impersonation.

        Returns raw HTML string on success, None on failure.
        """
        try:
            from curl_cffi.requests import AsyncSession
        except ImportError:
            return None

        from app.services.cloudflare_bypass import cloudflare_bypass_service
        from urllib.parse import urlparse

        domain = urlparse(entry_url).netloc
        cached = cloudflare_bypass_service.get_cached_cookies(domain)

        cookies = {}
        ua_header = {}
        if cached:
            cookies = cached["cookies"]
            if cached["user_agent"]:
                ua_header["User-Agent"] = cached["user_agent"]

        headers = {
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            **ua_header,
        }

        try:
            async with AsyncSession(
                impersonate=settings.CURL_CFFI_IMPERSONATE,
            ) as session:
                response = await session.get(
                    entry_url,
                    headers=headers,
                    cookies=cookies,
                    timeout=settings.RSS_REQUEST_TIMEOUT,
                    allow_redirects=True,
                )

                if response.status_code != 200:
                    logger.debug(
                        f"curl_cffi lightweight fetch HTTP {response.status_code}: "
                        f"{entry_url}"
                    )
                    return None

                return response.text

        except Exception as e:
            logger.debug(f"curl_cffi lightweight fetch error: {e}")
            return None

    async def _aiohttp_fetch(self, entry_url: str) -> Optional[str]:
        """Fallback: fetch HTML using aiohttp (original method)."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                }
                async with session.get(
                    entry_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=settings.RSS_REQUEST_TIMEOUT),
                    allow_redirects=True,
                ) as response:
                    if response.status != 200:
                        logger.debug(
                            f"aiohttp lightweight fetch HTTP {response.status}: "
                            f"{entry_url}"
                        )
                        return None
                    return await response.text()

        except Exception as e:
            logger.debug(f"aiohttp lightweight fetch error: {e}")
            return None

    async def fetch_entry_content(self, entry_url: str) -> Optional[Dict[str, Any]]:
        """
        Try a lightweight HTTP fetch of article content (no browser).

        Uses curl_cffi with browser TLS impersonation (Tier 1 bypass) when
        available, falling back to plain aiohttp if curl_cffi is not installed.

        Returns parsed content if successful, or None if the content is
        too short or the HTTP request fails — signaling the caller to
        fall back to browser-based scraping.

        Args:
            entry_url: URL of the article to fetch

        Returns:
            Dictionary with raw_html, raw_content, metadata on success; None on failure
        """
        try:
            logger.info(f"Lightweight fetch attempt: {entry_url}")

            # Tier 1: try curl_cffi (TLS impersonation + cached cookies)
            html = await self._curl_cffi_fetch(entry_url)

            # Fallback: plain aiohttp
            if html is None:
                html = await self._aiohttp_fetch(entry_url)

            if html is None:
                return None

            # Check for Cloudflare challenge page disguised as 200
            from app.services.cloudflare_bypass import CloudflareBypassService
            if CloudflareBypassService.is_cloudflare_block(html=html):
                logger.debug(
                    f"Lightweight fetch got Cloudflare challenge for {entry_url}"
                )
                return None

            # Reuse the scraping service's HTML parsing
            scraper = WebScraperService()
            metadata = scraper.extract_metadata(html)
            article_content = scraper.extract_article_content(html)

            # If extracted content is too short, signal fallback to browser
            if not article_content or len(article_content) < 200:
                logger.debug(f"Lightweight fetch content too short ({len(article_content) if article_content else 0} chars): {entry_url}")
                return None

            logger.info(f"Lightweight fetch success: {len(article_content)} chars from {entry_url}")

            return {
                "status": "success",
                "url": entry_url,
                "raw_html": html,
                "raw_content": article_content,
                "metadata": metadata,
                "fetched_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.debug(f"Lightweight fetch error: {e}")
            return None


# Singleton instance
rss_service = RSSService()
