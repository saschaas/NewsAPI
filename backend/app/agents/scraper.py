import time
from typing import Dict, Any
from datetime import datetime, timedelta
from loguru import logger

from app.agents.state import NewsProcessingState
from app.services import web_scraper, youtube_service, rss_service
from app.utils import generate_content_hash, normalize_content
from app.utils.llm_config import get_model_for_step, is_vision_model
from app.config import settings


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
            if youtube_service.is_channel_or_playlist_url(state['source_url']):
                # YouTube channel/playlist → list recent videos, treat as listing page
                max_articles = state.get('max_articles', 20)
                channel_result = await youtube_service.get_channel_videos(
                    state['source_url'],
                    max_results=max_articles,
                )

                if channel_result['status'] != 'success':
                    state['errors'].append(f"YouTube channel listing failed: {channel_result.get('error', 'Unknown error')}")
                    state['status'] = 'error'
                    state['stage'] = 'scraper_failed'
                    return state

                videos = channel_result.get('videos', [])
                if not videos:
                    state['errors'].append("YouTube channel returned no videos")
                    state['status'] = 'error'
                    state['stage'] = 'scraper_failed'
                    return state

                # Filter videos by publish date (only recent videos)
                max_age_days = settings.YOUTUBE_MAX_VIDEO_AGE_DAYS
                cutoff = datetime.utcnow() - timedelta(days=max_age_days)
                filtered_videos = []
                for v in videos:
                    upload_date_str = v.get('upload_date')
                    ts = v.get('timestamp')
                    if upload_date_str:
                        try:
                            upload_dt = datetime.strptime(upload_date_str, '%Y%m%d')
                            if upload_dt < cutoff:
                                logger.debug(f"Skipping old video: {v.get('title', '')} (uploaded {upload_date_str})")
                                continue
                        except (ValueError, TypeError):
                            pass  # Can't parse date, include the video
                    elif ts:
                        try:
                            upload_dt = datetime.utcfromtimestamp(int(ts))
                            if upload_dt < cutoff:
                                logger.debug(f"Skipping old video: {v.get('title', '')} (ts {ts})")
                                continue
                        except (ValueError, TypeError, OSError):
                            pass
                    filtered_videos.append(v)

                if not filtered_videos:
                    logger.info(f"No recent videos (last {max_age_days} days) from channel")
                    state['status'] = 'success'
                    state['stage'] = 'all_articles_finalized'
                    state['stage_timings']['scraper'] = time.time() - stage_start
                    return state

                logger.info(f"Filtered to {len(filtered_videos)}/{len(videos)} recent videos (last {max_age_days} days)")

                # Set up as listing page (same pattern as RSS)
                state['is_listing_page'] = True
                state['article_links'] = [v['url'] for v in filtered_videos]
                state['current_article_index'] = 0
                state['processed_articles'] = []
                state['raw_content'] = f"YouTube channel: {channel_result.get('channel_title', '')} - {len(filtered_videos)} videos"
                state['metadata'] = {
                    'channel_title': channel_result.get('channel_title', ''),
                    'video_count': len(filtered_videos),
                }
                state['stage'] = 'link_extraction_complete'
                state['stage_timings']['scraper'] = time.time() - stage_start

                logger.info(f"Scraper node: YouTube channel listed, {len(state['article_links'])} video links")
                return state

            else:
                # Single YouTube video → extract transcript directly
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
        error_msg = str(e) or f"{type(e).__name__} (no message)"
        logger.error(f"Scraper node error: {type(e).__name__}: {error_msg}")
        state['errors'].append(f"Scraper exception: {error_msg}")
        state['status'] = 'error'
        state['stage'] = 'scraper_failed'
        return state
