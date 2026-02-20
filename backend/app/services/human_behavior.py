"""
Human-like behavior simulation for Playwright pages.

Simulates mouse movements, scrolling, and timing patterns to make
automated browsing appear more natural to bot detection systems.
"""

import random
import asyncio
from loguru import logger
from playwright.async_api import Page


async def simulate_human_behavior(page: Page) -> None:
    """
    Simulate human-like behavior on a loaded page.

    Performs random mouse movements and scrolling to mimic a real user
    reading a page. All actions are wrapped in try/except so failures
    never crash the scrape pipeline.

    Args:
        page: Playwright page object (after page load)
    """
    try:
        viewport = page.viewport_size or {"width": 1920, "height": 1080}
        width = viewport["width"]
        height = viewport["height"]

        # Random mouse movements across the viewport
        num_moves = random.randint(3, 6)
        for _ in range(num_moves):
            x = random.randint(100, width - 100)
            y = random.randint(100, height - 100)
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.1, 0.4))

        # Scroll down in steps
        num_scrolls = random.randint(2, 4)
        for _ in range(num_scrolls):
            scroll_amount = random.randint(200, 600)
            await page.mouse.wheel(0, scroll_amount)
            await asyncio.sleep(random.uniform(0.3, 0.8))

        # 30% chance of scrolling back up slightly
        if random.random() < 0.3:
            scroll_up = random.randint(100, 300)
            await page.mouse.wheel(0, -scroll_up)
            await asyncio.sleep(random.uniform(0.2, 0.5))

        # Scroll back to top for content extraction
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(random.uniform(0.2, 0.5))

        logger.debug(f"Human behavior simulation: {num_moves} mouse moves, {num_scrolls} scrolls")

    except Exception as e:
        logger.debug(f"Human behavior simulation error (non-fatal): {e}")
