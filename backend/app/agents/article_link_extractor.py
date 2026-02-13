import time
import json
from typing import List
from loguru import logger
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from app.agents.state import NewsProcessingState
from app.services.ollama import ollama_service
from app.utils.llm_config import get_model_for_step, is_vision_model


async def article_link_extractor_node(state: NewsProcessingState) -> NewsProcessingState:
    """
    Article Link Extractor Agent Node

    Analyzes HTML content to determine if it's a listing page and extracts article links.
    Uses LLM to intelligently identify article links from different website structures.

    Args:
        state: Current workflow state

    Returns:
        Updated state with article_links and is_listing_page flags
    """
    stage_start = time.time()
    logger.info(f"Article Link Extractor: Analyzing {state['source_url']}")

    try:
        # Only process websites (YouTube is always a single video)
        if state['source_type'] != 'website':
            state['is_listing_page'] = False
            state['article_links'] = []
            state['stage'] = 'link_extraction_complete'
            state['stage_timings']['article_link_extractor'] = time.time() - stage_start
            return state

        # Check if we have HTML content
        if not state.get('raw_html'):
            logger.warning("No raw_html available for link extraction")
            state['is_listing_page'] = False
            state['article_links'] = []
            state['stage'] = 'link_extraction_complete'
            state['stage_timings']['article_link_extractor'] = time.time() - stage_start
            return state

        # Parse HTML
        soup = BeautifulSoup(state['raw_html'], 'lxml')
        base_url = state['source_url']
        base_domain = urlparse(base_url).netloc

        # PHASE 1: Identify the main article listing container
        logger.info("Phase 1: Identifying main article listing area")
        article_container = await identify_article_container(
            soup,
            base_url,
            state.get('extraction_instructions'),
            state.get('screenshot')
        )

        if not article_container:
            logger.warning("Could not identify article container, treating as single article")
            state['is_listing_page'] = False
            state['article_links'] = []
            state['stage'] = 'link_extraction_complete'
            state['stage_timings']['article_link_extractor'] = time.time() - stage_start
            return state

        logger.info(f"Identified article container: <{article_container.name}> with class={article_container.get('class')}")

        # PHASE 2: Extract links from the identified container
        logger.info("Phase 2: Extracting article links from identified area")
        all_links = []
        for link in article_container.find_all('a', href=True):
            href = link.get('href', '')
            # Make absolute URL
            absolute_url = urljoin(base_url, href)

            # Only consider links from the same domain
            if urlparse(absolute_url).netloc != base_domain:
                continue

            # Skip obvious non-article links
            url_lower = absolute_url.lower()
            if any(skip in url_lower for skip in [
                '/tag/', '/category/', '/author/', '/search', '/login', '/signup',
                '/contact', '/about', '/privacy', '/terms', '#', 'javascript:',
                '.pdf', '.jpg', '.png', '.gif', '.css', '.js'
            ]):
                continue

            # Get link text
            link_text = link.get_text(strip=True)

            # Skip links with no text or very short text
            if not link_text or len(link_text) < 15:
                continue

            # Get parent article element if exists
            parent = link.find_parent(['article', 'div', 'li', 'section'])
            context = parent.get_text(separator=' ', strip=True)[:200] if parent else link_text

            all_links.append({
                'url': absolute_url,
                'text': link_text,
                'context': context
            })

        # Remove duplicates (same URL)
        seen_urls = set()
        unique_links = []
        for link in all_links:
            if link['url'] not in seen_urls:
                seen_urls.add(link['url'])
                unique_links.append(link)

        logger.info(f"Found {len(unique_links)} unique article links in container")

        # If very few links, treat as single article
        if len(unique_links) < 2:
            logger.info("Less than 2 links found, treating as single article page")
            state['is_listing_page'] = False
            state['article_links'] = []
            state['stage'] = 'link_extraction_complete'
            state['stage_timings']['article_link_extractor'] = time.time() - stage_start
            return state

        # Use LLM for final validation if needed (only for edge cases)
        article_links = [link['url'] for link in unique_links[:20]]  # Max 20 articles

        logger.info(f"LLM identified {len(article_links)} article links")

        # Determine if this is a listing page
        if len(article_links) >= 2:
            state['is_listing_page'] = True
            # Limit to first 20 articles to avoid excessive processing time
            state['article_links'] = article_links[:20]
            state['current_article_index'] = 0
            state['processed_articles'] = []
            logger.info(f"Identified as listing page with {len(article_links)} articles (limiting to {len(state['article_links'])})")
        else:
            state['is_listing_page'] = False
            state['article_links'] = []
            logger.info("Identified as single article page")

        state['stage'] = 'link_extraction_complete'
        state['stage_timings']['article_link_extractor'] = time.time() - stage_start

        return state

    except Exception as e:
        logger.error(f"Article Link Extractor error: {e}")
        # Don't fail the whole workflow, just treat as single article
        state['is_listing_page'] = False
        state['article_links'] = []
        state['stage'] = 'link_extraction_complete'
        state['stage_timings']['article_link_extractor'] = time.time() - stage_start
        return state


async def identify_article_container(soup: BeautifulSoup, base_url: str, extraction_instructions: str = None, screenshot: str = None):
    """
    Identify the main container element that holds article listings

    Args:
        soup: BeautifulSoup object of the page
        base_url: The base URL for context
        extraction_instructions: Optional user instructions
        screenshot: Optional screenshot for vision models

    Returns:
        BeautifulSoup element representing the article container, or None
    """
    # Use LLM to identify container (especially helpful with vision)
    model = get_model_for_step('link_extractor')
    use_vision = is_vision_model(model) and screenshot is not None

    # Find all potential container elements
    potential_containers = []

    # Look for common patterns
    for tag in ['main', 'div', 'section', 'article']:
        for elem in soup.find_all(tag):
            # Count article-like children
            article_count = len(elem.find_all('article'))
            link_count = len(elem.find_all('a'))

            # Skip if too few or too many links
            if link_count < 5 or link_count > 200:
                continue

            # Get identifying info
            elem_class = ' '.join(elem.get('class', []))
            elem_id = elem.get('id', '')

            # Score based on class/id names
            score = 0
            for keyword in ['article', 'post', 'content', 'main', 'feed', 'list', 'grid', 'news']:
                if keyword in elem_class.lower() or keyword in elem_id.lower():
                    score += 2

            if article_count > 0:
                score += article_count

            potential_containers.append({
                'element': elem,
                'tag': tag,
                'class': elem_class,
                'id': elem_id,
                'article_count': article_count,
                'link_count': link_count,
                'score': score
            })

    # Sort by score
    potential_containers.sort(key=lambda x: x['score'], reverse=True)

    if not potential_containers:
        logger.warning("No potential article containers found")
        return None

    # If using vision model, ask it to identify the best container
    if use_vision:
        logger.info("Using vision model to identify article container")

        # Prepare container info for LLM
        container_info = []
        for i, cont in enumerate(potential_containers[:10]):  # Top 10
            container_info.append({
                'id': i,
                'tag': cont['tag'],
                'class': cont['class'][:100],
                'id_attr': cont['id'],
                'article_count': cont['article_count'],
                'link_count': cont['link_count']
            })

        user_instructions = ""
        if extraction_instructions:
            user_instructions = f"\n\nUSER INSTRUCTIONS: {extraction_instructions}\nUse these instructions to help identify the correct content area."

        prompt = f"""You are looking at a news website screenshot. I need you to identify which HTML container holds the main article listings.{user_instructions}

Below are the top candidate containers found on the page:
{json.dumps(container_info, indent=2)}

Look at the screenshot and identify which container ID (0-9) contains the MAIN ARTICLE LISTINGS.
The correct container should:
- Have multiple article headlines visible
- Be the primary content area (not sidebar, not navigation, not footer)
- Contain clickable article links
- Show article titles/headlines

Respond with ONLY the container ID number (e.g., 0, 1, 2, etc.) or -1 if none match.

Response:"""

        try:
            result = await ollama_service.generate(
                model=model,
                prompt=prompt,
                temperature=0.1,
                format=None,
                images=[screenshot]
            )

            if result and result.get('response'):
                response_text = result['response'].strip()
                try:
                    container_id = int(response_text)
                    if 0 <= container_id < len(container_info):
                        logger.info(f"Vision model selected container {container_id}")
                        return potential_containers[container_id]['element']
                except:
                    logger.warning(f"Could not parse container ID from response: {response_text}")
        except Exception as e:
            logger.error(f"Error using vision model for container identification: {e}")

    # Fallback: return highest scoring container
    best_container = potential_containers[0]
    logger.info(f"Using highest-scored container: <{best_container['tag']}> class='{best_container['class'][:50]}' (score={best_container['score']})")
    return best_container['element']


async def identify_article_links_with_llm(links: List[dict], base_url: str, extraction_instructions: str = None, screenshot: str = None) -> List[str]:
    """
    Use LLM to identify which links are actual article links (supports vision models)

    Args:
        links: List of link dictionaries with url, text, and context
        base_url: The base URL for context
        extraction_instructions: Optional user-provided instructions for extraction
        screenshot: Optional base64-encoded screenshot for vision models

    Returns:
        List of article URLs
    """
    # Take top 100 links (already sorted by article likelihood score)
    links_sample = links[:100]

    # Prepare link data for LLM
    link_data = []
    for i, link in enumerate(links_sample):
        link_data.append({
            'id': i,
            'url': link['url'],
            'text': link['text'][:120],  # Truncate long text
            'context': link['context'][:200],
            'score': link.get('score', 0)  # Include pre-filter score as hint
        })

    # Build user instructions section if provided
    user_instructions = ""
    if extraction_instructions:
        user_instructions = f"""

USER-PROVIDED EXTRACTION INSTRUCTIONS:
{extraction_instructions}

IMPORTANT: Follow the user's instructions above when identifying article links.
"""

    # Use configured model for link extraction
    model = get_model_for_step('link_extractor')
    is_using_vision = is_vision_model(model) and screenshot is not None

    if is_using_vision:
        logger.info(f"Using vision model {model} with screenshot for article link extraction")
        prompt = f"""You are analyzing a news website screenshot to identify article links.

Website URL: {base_url}{user_instructions}

I'm showing you a screenshot of the website along with a list of links found on the page.
Your task is to identify which links point to individual news articles by LOOKING AT THE VISUAL LAYOUT.

IMPORTANT CRITERIA for article links:
1. Links to full article pages (not homepage, category pages, or navigation)
2. Links with article titles or headlines as text
3. Links that VISUALLY appear to be article listings (look for article cards, headlines, thumbnails)
4. Exclude: navigation links, category links, social media, author pages, tags, search
5. Exclude: links to external sites, ads, related content sections

Use the VISUAL CONTEXT from the screenshot to identify which links are likely news articles.
Look for repeating visual patterns that indicate article listings.

Links found:
{json.dumps(link_data, indent=2)}

Respond with ONLY a JSON array of link IDs that are article links.
Example response: [0, 3, 5, 12, 15]

If no article links found, respond: []

Response:"""
    else:
        prompt = f"""You are analyzing a news website to identify article links.

Website URL: {base_url}{user_instructions}

Below is a list of links found on this page. Your task is to identify which links point to individual news articles.

IMPORTANT CRITERIA for article links:
1. Links to full article pages (not homepage, category pages, or navigation)
2. Links with article titles or headlines as text
3. Links within article listing contexts (like "Read more", article headlines)
4. Exclude: navigation links, category links, social media, author pages, tags, search
5. Exclude: links to external sites, ads, related content sections

Links found:
{json.dumps(link_data, indent=2)}

Respond with ONLY a JSON array of link IDs that are article links.
Example response: [0, 3, 5, 12, 15]

If no article links found, respond: []

Response:"""

    try:
        # Call LLM (with or without vision)
        result = await ollama_service.generate(
            model=model,
            prompt=prompt,
            temperature=0.3,
            format=None,  # Don't force JSON format for this response
            images=[screenshot] if is_using_vision else None
        )

        if not result:
            logger.error("No response from Ollama")
            return []

        # Get response text
        response_text = result.get('response', '')
        if not response_text:
            logger.warning("Empty response from LLM")
            return []

        response_text = response_text.strip()
        logger.debug(f"LLM response for article links: {response_text[:200]}")

        # Try to extract JSON array
        if '[' in response_text and ']' in response_text:
            # Extract just the array part
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            json_str = response_text[start_idx:end_idx]

            article_ids = json.loads(json_str)

            # Extract URLs for identified articles
            article_urls = []
            for link_id in article_ids:
                if isinstance(link_id, int) and 0 <= link_id < len(link_data):
                    article_urls.append(link_data[link_id]['url'])

            # Remove duplicates while preserving order
            seen = set()
            unique_urls = []
            for url in article_urls:
                if url not in seen:
                    seen.add(url)
                    unique_urls.append(url)

            return unique_urls
        else:
            logger.warning("LLM response did not contain valid JSON array")
            return []

    except Exception as e:
        logger.error(f"Error in LLM article link identification: {e}")
        return []
