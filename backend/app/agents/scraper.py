import time
from typing import Dict, Any
from loguru import logger

from app.agents.state import NewsProcessingState
from app.services import web_scraper, youtube_service, rss_service
from app.utils import generate_content_hash, normalize_content
from app.utils.llm_config import get_model_for_step, is_vision_model


async def scraper_node(state: NewsProcessingState) -> NewsProcessingState:
    """
    Scraper Agent Node

    Fetches raw content from websites or YouTube videos

    Args:
        state: Current workflow state

    Returns:
        Updated state with raw content
    """
    stage_start = time.time()
    logger.info(f"Scraper node: Processing {state['source_type']} - {state['source_url']}")

    try:
        if state['source_type'] == 'website':
            # Check if we need a screenshot for vision-based link extraction
            link_extractor_model = get_model_for_step('link_extractor')
            take_screenshot = is_vision_model(link_extractor_model)

            if take_screenshot:
                logger.info(f"Taking screenshot for vision model: {link_extractor_model}")

            # Scrape website
            result = await web_scraper.scrape_url(
                state['source_url'],
                take_screenshot=take_screenshot
            )

            if result['status'] != 'success':
                state['errors'].append(f"Scraping failed: {result.get('error', 'Unknown error')}")
                state['status'] = 'error'
                state['stage'] = 'scraper_failed'
                return state

            state['raw_html'] = result['raw_html']
            state['raw_content'] = result['raw_content']
            state['screenshot'] = result.get('screenshot')
            state['metadata'] = result['metadata']

        elif state['source_type'] == 'youtube':
            # Process YouTube video
            result = await youtube_service.process_youtube_url(state['source_url'])

            if result['status'] != 'success':
                state['errors'].append(f"YouTube processing failed: {result.get('error', 'Unknown error')}")
                state['status'] = 'error'
                state['stage'] = 'scraper_failed'
                return state

            state['transcript'] = result['transcript']
            state['raw_content'] = result['transcript']
            state['metadata'] = result['metadata']

        elif state['source_type'] == 'rss':
            # Fetch RSS feed - bypasses browser-based scraping entirely
            result = await rss_service.fetch_feed(state['source_url'])

            if result['status'] != 'success':
                state['errors'].append(f"RSS fetch failed: {result.get('error', 'Unknown error')}")
                state['status'] = 'error'
                state['stage'] = 'scraper_failed'
                return state

            entries = result.get('entries', [])
            if not entries:
                state['errors'].append("RSS feed returned no entries")
                state['status'] = 'error'
                state['stage'] = 'scraper_failed'
                return state

            # RSS provides article URLs directly - skip LLM-based link extraction
            max_articles = state.get('max_articles', 20)
            state['is_listing_page'] = True
            state['article_links'] = [entry['url'] for entry in entries if entry.get('url')][:max_articles]
            state['raw_content'] = f"RSS feed: {result.get('feed_title', '')} - {len(entries)} entries"
            state['metadata'] = {'feed_title': result.get('feed_title', ''), 'entry_count': len(entries)}
            state['stage'] = 'link_extraction_complete'
            state['stage_timings']['scraper'] = time.time() - stage_start

            logger.info(f"Scraper node: RSS feed parsed, {len(state['article_links'])} article links")
            return state

        else:
            state['errors'].append(f"Unknown source type: {state['source_type']}")
            state['status'] = 'error'
            state['stage'] = 'scraper_failed'
            return state

        # Generate content hash
        if state['raw_content']:
            normalized = normalize_content(state['raw_content'])
            state['content_hash'] = generate_content_hash(normalized)
        else:
            state['errors'].append("No content extracted")
            state['status'] = 'error'
            state['stage'] = 'scraper_failed'
            return state

        # Update state
        state['stage'] = 'scraped'
        state['stage_timings']['scraper'] = time.time() - stage_start

        logger.info(f"Scraper node: Successfully scraped {len(state['raw_content'])} characters")

        return state

    except Exception as e:
        logger.error(f"Scraper node error: {e}")
        state['errors'].append(f"Scraper exception: {str(e)}")
        state['status'] = 'error'
        state['stage'] = 'scraper_failed'
        return state
