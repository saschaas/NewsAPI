from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any, List
from loguru import logger
import asyncio
from datetime import datetime


class WebScraperService:
    """Service for web scraping using Playwright"""

    # Common cookie banner selectors
    COOKIE_SELECTORS = [
        # Generic
        'button:has-text("Accept")',
        'button:has-text("Accept All")',
        'button:has-text("I Accept")',
        'button:has-text("I Agree")',
        'button:has-text("Agree")',
        'button:has-text("OK")',
        'button:has-text("Got it")',
        'button:has-text("Allow")',
        'button:has-text("Allow All")',
        # German
        'button:has-text("Akzeptieren")',
        'button:has-text("Alle akzeptieren")',
        'button:has-text("Einverstanden")',
        'button:has-text("Zustimmen")',
        # Common class names
        '.accept-cookies',
        '.cookie-accept',
        '.consent-accept',
        '#cookie-accept',
        '#accept-cookies',
        '[data-testid="cookie-accept"]',
        '[data-testid="accept-all"]',
    ]

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    async def initialize(self):
        """Initialize Playwright browser"""
        if self.browser is None:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            self.context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0',
                },
            )

    async def close(self):
        """Close browser"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()

    async def handle_cookie_banner(self, page: Page) -> bool:
        """
        Attempt to click cookie accept buttons

        Args:
            page: Playwright page object

        Returns:
            True if banner was handled, False otherwise
        """
        for selector in self.COOKIE_SELECTORS:
            try:
                button = page.locator(selector).first
                if await button.is_visible(timeout=2000):
                    await button.click()
                    logger.info(f"Clicked cookie banner with selector: {selector}")
                    await page.wait_for_timeout(1000)  # Wait for banner to close
                    return True
            except Exception:
                continue

        return False

    def extract_metadata(self, html: str) -> Dict[str, Any]:
        """
        Extract metadata from HTML (Open Graph, meta tags, etc.)

        Args:
            html: Raw HTML content

        Returns:
            Dictionary of metadata
        """
        soup = BeautifulSoup(html, 'lxml')
        metadata = {}

        # Open Graph tags
        og_tags = soup.find_all('meta', property=lambda x: x and x.startswith('og:'))
        for tag in og_tags:
            property_name = tag.get('property', '').replace('og:', '')
            content = tag.get('content', '')
            if property_name and content:
                metadata[f'og_{property_name}'] = content

        # Standard meta tags
        meta_tags = {
            'description': soup.find('meta', {'name': 'description'}),
            'keywords': soup.find('meta', {'name': 'keywords'}),
            'author': soup.find('meta', {'name': 'author'}),
            'publish_date': soup.find('meta', {'name': 'publish_date'}),
            'article:published_time': soup.find('meta', {'property': 'article:published_time'}),
            'article:author': soup.find('meta', {'property': 'article:author'}),
        }

        for key, tag in meta_tags.items():
            if tag:
                content = tag.get('content', '')
                if content:
                    metadata[key] = content

        # Title
        title_tag = soup.find('title')
        if title_tag:
            metadata['page_title'] = title_tag.get_text().strip()

        return metadata

    def extract_article_content(self, html: str) -> Optional[str]:
        """
        Extract main article content from HTML

        Args:
            html: Raw HTML content

        Returns:
            Extracted text content or None
        """
        soup = BeautifulSoup(html, 'lxml')

        # Try common article selectors
        article_selectors = [
            'article',
            '[role="main"]',
            '.article-content',
            '.post-content',
            '.entry-content',
            '.content',
            'main',
        ]

        for selector in article_selectors:
            article = soup.select_one(selector)
            if article:
                # Remove script and style tags
                for tag in article(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                    tag.decompose()

                text = article.get_text(separator=' ', strip=True)
                if len(text) > 100:  # Minimum content length
                    return text

        # Fallback: get body text
        body = soup.find('body')
        if body:
            for tag in body(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                tag.decompose()
            return body.get_text(separator=' ', strip=True)

        return None

    async def scrape_url(
        self,
        url: str,
        wait_for_selector: Optional[str] = None,
        timeout: int = 30000,
        take_screenshot: bool = False,
        retry_on_403: bool = True
    ) -> Dict[str, Any]:
        """
        Scrape a URL and extract content

        Args:
            url: URL to scrape
            wait_for_selector: Optional selector to wait for
            timeout: Timeout in milliseconds
            take_screenshot: Whether to take a screenshot (for vision models)
            retry_on_403: Whether to retry with delays on 403 errors

        Returns:
            Dictionary with raw_html, raw_content, metadata, screenshot, and status
        """
        await self.initialize()

        page = await self.context.new_page()

        # Add random delay to appear more human-like (1-3 seconds)
        import random
        await asyncio.sleep(random.uniform(1.0, 3.0))

        try:
            # Navigate to URL
            logger.info(f"Navigating to {url}")
            response = await page.goto(url, timeout=timeout, wait_until='domcontentloaded')

            if not response or response.status != 200:
                status_code = response.status if response else 'No response'
                logger.error(f"Failed to load {url}: HTTP {status_code}")

                # Retry once with longer delay for 401/403 errors (anti-bot protection)
                if retry_on_403 and response and response.status in [401, 403]:
                    logger.info(f"Retrying {url} after {response.status} error with longer delay...")
                    await page.close()
                    # Wait longer between retries to appear more human
                    await asyncio.sleep(random.uniform(5.0, 8.0))
                    return await self.scrape_url(url, wait_for_selector, timeout, take_screenshot, retry_on_403=False)

                return {
                    'status': 'error',
                    'error': f'HTTP {status_code}',
                    'raw_html': None,
                    'raw_content': None,
                    'metadata': {}
                }

            # Handle cookie banner
            await self.handle_cookie_banner(page)

            # Wait for specific selector if provided
            if wait_for_selector:
                try:
                    await page.wait_for_selector(wait_for_selector, timeout=5000)
                except Exception as e:
                    logger.warning(f"Timeout waiting for selector {wait_for_selector}: {e}")

            # Wait for dynamic content and let any anti-bot checks complete
            # Longer wait for better success with protected sites
            await page.wait_for_timeout(3000)

            # Take screenshot if requested (for vision models)
            screenshot_base64 = None
            if take_screenshot:
                try:
                    screenshot_bytes = await page.screenshot(full_page=False)
                    import base64
                    screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                    logger.info("Captured screenshot for vision model")
                except Exception as e:
                    logger.warning(f"Failed to capture screenshot: {e}")

            # Extract content
            raw_html = await page.content()
            raw_content = await page.evaluate("() => document.body.innerText")

            # Extract metadata
            metadata = self.extract_metadata(raw_html)

            # Try to extract article content
            article_content = self.extract_article_content(raw_html)

            return {
                'status': 'success',
                'url': url,
                'raw_html': raw_html,
                'raw_content': article_content or raw_content,
                'metadata': metadata,
                'screenshot': screenshot_base64,
                'fetched_at': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'raw_html': None,
                'raw_content': None,
                'metadata': {}
            }

        finally:
            await page.close()


# Singleton instance
web_scraper = WebScraperService()
