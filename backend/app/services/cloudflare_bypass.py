"""
Cloudflare bypass service using a tiered approach.

Tier 1 — curl_cffi: Lightweight HTTP fetch with browser TLS fingerprint
         impersonation. Handles sites with only TLS-level checking.
         Injects cached cf_clearance cookies when available.

Tier 2 — nodriver:  WebDriver-free Chrome controller that communicates via
         CDP without any Selenium/WebDriver dependency. Solves Cloudflare
         JS challenges and Turnstile automatically. Harvested cookies are
         cached so subsequent requests can use fast curl_cffi.
"""

import asyncio
import time
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from loguru import logger

from app.config import settings


# ── Cookie cache ────────────────────────────────────────────────────────────
# Maps domain → {cookies: dict, user_agent: str, expires_at: float}
_cookie_cache: Dict[str, Dict[str, Any]] = {}
_domain_locks: Dict[str, asyncio.Lock] = {}

# Cloudflare markers in HTML
CLOUDFLARE_HTML_MARKERS = [
    "cf-browser-verification",
    "cf_chl_opt",
    "challenges.cloudflare.com",
    "Just a moment",
    "Checking if the site connection is secure",
    "Attention Required! | Cloudflare",
    "cf-challenge-running",
    "ray ID",
]


def _get_domain(url: str) -> str:
    """Extract domain from URL."""
    return urlparse(url).netloc


def _get_domain_lock(domain: str) -> asyncio.Lock:
    """Get or create an asyncio Lock for a domain to prevent concurrent solves."""
    if domain not in _domain_locks:
        _domain_locks[domain] = asyncio.Lock()
    return _domain_locks[domain]


class CloudflareBypassService:
    """Tiered Cloudflare bypass: curl_cffi (Tier 1) → nodriver (Tier 2)."""

    # ── Cloudflare detection ────────────────────────────────────────────

    @staticmethod
    def is_cloudflare_block(
        headers: Optional[Dict[str, str]] = None,
        html: Optional[str] = None,
    ) -> bool:
        """Detect whether a response is a Cloudflare block/challenge page."""
        if headers:
            server = headers.get("server", "").lower()
            if server == "cloudflare" or "cf-ray" in headers:
                return True

        if html:
            html_lower = html[:5000].lower()  # only inspect head
            for marker in CLOUDFLARE_HTML_MARKERS:
                if marker.lower() in html_lower:
                    return True

        return False

    # ── Cookie cache ────────────────────────────────────────────────────

    def get_cached_cookies(self, domain: str) -> Optional[Dict[str, Any]]:
        """Return cached cookies + UA for *domain*, or None if expired/absent."""
        entry = _cookie_cache.get(domain)
        if entry and entry["expires_at"] > time.time():
            logger.debug(f"Cloudflare cookie cache hit for {domain}")
            return entry
        if entry:
            logger.debug(f"Cloudflare cookie cache expired for {domain}")
            del _cookie_cache[domain]
        return None

    def cache_cookies(
        self, domain: str, cookies: Dict[str, str], user_agent: str
    ) -> None:
        """Store cookies + UA for *domain* with configurable TTL."""
        _cookie_cache[domain] = {
            "cookies": cookies,
            "user_agent": user_agent,
            "expires_at": time.time() + settings.CF_COOKIE_TTL_SECONDS,
        }
        logger.info(
            f"Cached Cloudflare cookies for {domain} "
            f"(TTL {settings.CF_COOKIE_TTL_SECONDS}s)"
        )

    # ── Tier 1: curl_cffi ──────────────────────────────────────────────

    async def curl_cffi_fetch(
        self,
        url: str,
        timeout: int = 30,
    ) -> Optional[Dict[str, Any]]:
        """
        Lightweight HTTP fetch with browser TLS fingerprint impersonation.

        Injects cached cf_clearance cookies when available for the domain.
        Returns dict with status/html/headers on success, None on failure.
        """
        if not settings.CLOUDFLARE_BYPASS_ENABLED:
            return None

        try:
            from curl_cffi.requests import AsyncSession
        except ImportError:
            logger.warning("curl_cffi not installed — skipping Tier 1 fetch")
            return None

        domain = _get_domain(url)
        cached = self.get_cached_cookies(domain)

        cookies = {}
        extra_headers = {}
        if cached:
            cookies = cached["cookies"]
            extra_headers["User-Agent"] = cached["user_agent"]

        headers = {
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            **extra_headers,
        }

        try:
            async with AsyncSession(
                impersonate=settings.CURL_CFFI_IMPERSONATE,
            ) as session:
                response = await session.get(
                    url,
                    headers=headers,
                    cookies=cookies,
                    timeout=timeout,
                    allow_redirects=True,
                )

                if response.status_code == 200:
                    html = response.text
                    # Quick check: did we get a Cloudflare challenge page
                    # disguised as 200?
                    if self.is_cloudflare_block(html=html):
                        logger.debug(
                            f"curl_cffi got Cloudflare challenge page for {url}"
                        )
                        return None

                    logger.info(
                        f"curl_cffi fetch success: {url} "
                        f"({len(html)} chars)"
                    )
                    return {
                        "status": "success",
                        "url": url,
                        "html": html,
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                    }

                if response.status_code in (403, 503):
                    logger.debug(
                        f"curl_cffi HTTP {response.status_code} for {url} "
                        "— likely Cloudflare"
                    )
                    return None

                logger.debug(
                    f"curl_cffi HTTP {response.status_code} for {url}"
                )
                return None

        except Exception as e:
            logger.debug(f"curl_cffi fetch error for {url}: {e}")
            return None

    # ── Tier 2: nodriver ───────────────────────────────────────────────

    async def nodriver_fetch(
        self,
        url: str,
        timeout: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch a URL using nodriver (WebDriver-free Chrome).

        Solves Cloudflare JS challenges and Turnstile automatically.
        On success, harvests and caches cf_clearance cookies for the domain
        so subsequent requests can use the fast curl_cffi path.

        Returns dict with status/html on success, None on failure.
        """
        if not settings.CLOUDFLARE_BYPASS_ENABLED or not settings.NODRIVER_ENABLED:
            return None

        try:
            import nodriver as uc
        except ImportError:
            logger.warning("nodriver not installed — skipping Tier 2 fetch")
            return None

        timeout = timeout or settings.NODRIVER_TIMEOUT
        domain = _get_domain(url)
        lock = _get_domain_lock(domain)

        # Prevent concurrent nodriver solves for the same domain.
        # If another coroutine is already solving, wait for it and then
        # try curl_cffi with the freshly cached cookies.
        if lock.locked():
            logger.info(
                f"nodriver solve already in progress for {domain}, waiting…"
            )
            async with lock:
                pass  # wait for the other solve to finish
            # Try using the freshly cached cookies instead
            cached = self.get_cached_cookies(domain)
            if cached:
                result = await self.curl_cffi_fetch(url)
                if result:
                    return result

        async with lock:
            browser = None
            try:
                logger.info(f"nodriver: starting Chrome for {url}")

                browser = await uc.start(
                    headless=settings.NODRIVER_HEADLESS,
                    browser_args=[
                        "--disable-gpu",
                        "--no-first-run",
                        "--no-default-browser-check",
                    ],
                )

                tab = await browser.get(url)

                # Wait for Cloudflare challenge to resolve.
                # We poll the page content until we see real content or timeout.
                start = time.time()
                resolved = False
                html = ""

                while time.time() - start < timeout:
                    await tab.sleep(2)

                    try:
                        html = await tab.get_content()
                    except Exception:
                        html = ""

                    if not html:
                        continue

                    # Check if we're past the challenge
                    if not self.is_cloudflare_block(html=html) and len(html) > 500:
                        resolved = True
                        break

                if not resolved:
                    logger.warning(
                        f"nodriver: Cloudflare challenge not resolved "
                        f"within {timeout}s for {url}"
                    )
                    return None

                logger.info(
                    f"nodriver: challenge resolved for {url} "
                    f"({len(html)} chars)"
                )

                # ── Harvest cookies ─────────────────────────────────────
                try:
                    all_cookies = await browser.cookies.get_all()
                    cookie_dict = {}
                    for cookie in all_cookies:
                        name = getattr(cookie, "name", None) or cookie.get("name", "")
                        value = getattr(cookie, "value", None) or cookie.get("value", "")
                        if name and value:
                            cookie_dict[name] = value

                    # Detect the User-Agent Chrome is actually using
                    try:
                        user_agent = await tab.evaluate("navigator.userAgent")
                    except Exception:
                        user_agent = ""

                    if cookie_dict:
                        self.cache_cookies(domain, cookie_dict, user_agent or "")
                        cf_cookie = cookie_dict.get("cf_clearance", "")
                        if cf_cookie:
                            logger.info(
                                f"nodriver: harvested cf_clearance for {domain}"
                            )
                except Exception as e:
                    logger.warning(f"nodriver: cookie harvesting error: {e}")

                return {
                    "status": "success",
                    "url": url,
                    "html": html,
                }

            except Exception as e:
                logger.error(f"nodriver error for {url}: {e}")
                return None

            finally:
                if browser:
                    try:
                        browser.stop()
                    except Exception:
                        pass


# Singleton
cloudflare_bypass_service = CloudflareBypassService()
