import time
from loguru import logger

from app.agents.state import NewsProcessingState
from app.services import web_scraper, rss_service
from app.utils import generate_content_hash, normalize_content


async def article_fetcher_node(state: NewsProcessingState) -> NewsProcessingState:
    """
    Article Fetcher Agent Node

    Fetches an individual article from the article_links list.
    This node is called repeatedly for each article in a listing page.

    Args:
        state: Current workflow state

    Returns:
        Updated state with article content
    """
    stage_start = time.time()

    try:
        # Get the current article URL
        current_index = state.get('current_article_index', 0)
        article_links = state.get('article_links', [])

        if current_index >= len(article_links):
            # No more articles to process
            state['errors'].append("No article URL to fetch")
            state['status'] = 'error'
            state['stage'] = 'article_fetcher_failed'
            return state

        article_url = article_links[current_index]
        logger.info(f"Article Fetcher: Fetching article {current_index + 1}/{len(article_links)}: {article_url}")

        # Try lightweight HTTP fetch first (no browser overhead)
        lightweight_result = await rss_service.fetch_entry_content(article_url)
        if lightweight_result:
            result = lightweight_result
            logger.info(f"Article Fetcher: Lightweight HTTP fetch succeeded for {article_url}")
        else:
            # Fall back to browser-based scraping
            result = await web_scraper.scrape_url(
                article_url,
                retry_on_403=True  # Enable retry for 403 errors
            )

        if result['status'] != 'success':
            logger.warning(f"Failed to fetch article {article_url}: {result.get('error')}")
            # Skip this article and move to next
            state['current_article_index'] += 1
            state['stage'] = 'article_fetch_failed'
            state['stage_timings'][f'article_fetcher_{current_index}'] = time.time() - stage_start
            return state

        # Update state with article content
        state['raw_html'] = result['raw_html']
        state['raw_content'] = result['raw_content']
        state['metadata'] = result['metadata']

        # Generate content hash for this article
        if state['raw_content']:
            normalized = normalize_content(state['raw_content'])
            state['content_hash'] = generate_content_hash(normalized)
        else:
            logger.warning(f"No content extracted from article {article_url}")
            state['current_article_index'] += 1
            state['stage'] = 'article_fetch_failed'
            state['stage_timings'][f'article_fetcher_{current_index}'] = time.time() - stage_start
            return state

        # Reset analysis fields for this new article
        state['title'] = ''
        state['content'] = ''
        state['summary'] = None
        state['main_topic'] = None
        state['author'] = None
        state['published_date'] = None
        state['is_high_impact'] = False
        state['stock_mentions'] = []

        state['stage'] = 'article_fetched'
        state['stage_timings'][f'article_fetcher_{current_index}'] = time.time() - stage_start

        logger.info(f"Article Fetcher: Successfully fetched {len(state['raw_content'])} characters")

        return state

    except Exception as e:
        logger.error(f"Article Fetcher error: {e}")
        state['errors'].append(f"Article Fetcher exception: {str(e)}")
        state['status'] = 'error'
        state['stage'] = 'article_fetcher_failed'
        state['stage_timings']['article_fetcher'] = time.time() - stage_start
        return state
