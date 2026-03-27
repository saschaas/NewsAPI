import time
import json
from typing import Dict, Any, Optional
from loguru import logger
from datetime import datetime
from sqlalchemy.orm import Session

from app.agents.state import NewsProcessingState
from app.services import ollama_service
from app.models import LLMCache
from app.database import SessionLocal
from app.config import settings
from app.utils.llm_config import get_model_for_step


async def get_cached_analysis(content_hash: str, prompt_type: str) -> Optional[Dict[str, Any]]:
    """Check if we have cached LLM response for this content"""
    db = SessionLocal()
    try:
        cache_entry = db.query(LLMCache).filter(
            LLMCache.content_hash == content_hash,
            LLMCache.prompt_type == prompt_type
        ).first()

        if cache_entry:
            # Update usage stats
            cache_entry.use_count += 1
            cache_entry.last_used_at = datetime.utcnow()
            db.commit()

            logger.info(f"Cache hit for {prompt_type}: {content_hash[:16]}...")
            return json.loads(cache_entry.response_json)

        return None
    finally:
        db.close()


async def cache_analysis(content_hash: str, prompt_type: str, response: Dict[str, Any], model_name: str):
    """Cache LLM response"""
    db = SessionLocal()
    try:
        cache_entry = LLMCache(
            content_hash=content_hash,
            model_name=model_name,
            prompt_type=prompt_type,
            response_json=json.dumps(response)
        )
        db.add(cache_entry)
        db.commit()
        logger.info(f"Cached {prompt_type} response: {content_hash[:16]}...")
    except Exception as e:
        logger.error(f"Error caching analysis: {e}")
        db.rollback()
    finally:
        db.close()


async def analyzer_node(state: NewsProcessingState) -> NewsProcessingState:
    """
    Analyzer Agent Node

    Extracts structured information from raw content using LLM

    Args:
        state: Current workflow state

    Returns:
        Updated state with analyzed content
    """
    stage_start = time.time()
    logger.info(f"Analyzer node: Processing content (hash: {state['content_hash'][:16]}...)")

    try:
        # Check cache first
        cached = await get_cached_analysis(state['content_hash'], 'analysis')

        if cached:
            # Use cached result — prefer pre-set YouTube metadata over cached LLM values
            has_preset_title = state.get('title') and state['title'].strip()
            state['title'] = state['title'] if has_preset_title else cached.get('title', '')
            state['content'] = state['raw_content']  # Keep original content
            state['summary'] = cached.get('summary')
            state['main_topic'] = cached.get('main_topic')
            if not state.get('author'):
                state['author'] = cached.get('author')
            state['is_high_impact'] = cached.get('is_high_impact', False)

            # Parse published date — keep pre-set value from YouTube metadata
            if not state.get('published_date') and cached.get('published_date'):
                try:
                    state['published_date'] = datetime.fromisoformat(cached['published_date'])
                except:
                    state['published_date'] = None

            state['stage'] = 'analyzed'
            state['stage_timings']['analyzer'] = time.time() - stage_start
            logger.info("Analyzer node: Used cached analysis")
            return state

        # Build user instructions section if provided
        user_instructions = ""
        extraction_instructions = state.get('extraction_instructions')
        if extraction_instructions:
            user_instructions = f"""

USER-PROVIDED EXTRACTION INSTRUCTIONS:
{extraction_instructions}

IMPORTANT: Pay special attention to the user's instructions above when extracting information,
particularly for the publication date/time and other metadata that may be mentioned.
"""

        # Build metadata context for the prompt (helps LLM with YouTube transcripts)
        metadata_context = ""
        if state.get('title') and state['title'].strip():
            metadata_context += f"\nKnown Title: {state['title']}"
        if state.get('author'):
            metadata_context += f"\nKnown Author: {state['author']}"
        if state.get('published_date'):
            metadata_context += f"\nKnown Published Date: {state['published_date'].isoformat()}"

        # Build prompt — use configurable content limit instead of hardcoded 8000
        content_limit = settings.LLM_MAX_CONTENT_CHARS
        prompt = f"""You are a financial news analyst. Extract the following information from the article.{user_instructions}{metadata_context}

Article Content:
{state['raw_content'][:content_limit]}

Extract:
1. Title: The main headline (if not available, create a concise title)
2. Summary: 3-5 sentence summary covering the main thesis, key stocks or topics discussed, and the most important takeaways. Be specific — include names, numbers, and conclusions rather than generic descriptions.
3. Main Topic: Primary subject (e.g., "Earnings Report", "Market Analysis", "IPO", "Merger", "Regulatory News")
4. Author: Author name (if available in the text)
5. Published Date: When it was published in ISO format (YYYY-MM-DD HH:MM:SS) if available. Look carefully for date/time information in the article content.
6. High Impact: Is this likely to significantly impact the stock market? (true/false)

Respond ONLY with valid JSON in this exact format:
{{
  "title": "...",
  "summary": "...",
  "main_topic": "...",
  "author": "...",
  "published_date": "YYYY-MM-DD HH:MM:SS",
  "is_high_impact": true
}}"""

        # Call LLM with configured model
        model = get_model_for_step('analyzer')
        result = await ollama_service.generate(
            prompt=prompt,
            model=model,
            temperature=0.3,
            format="json",
            num_ctx=settings.LLM_NUM_CTX
        )

        if not result or not result.get('response'):
            state['errors'].append("LLM analysis failed: no response")
            state['status'] = 'error'
            state['stage'] = 'analyzer_failed'
            return state

        analysis = result['response']

        # Validate response
        if not isinstance(analysis, dict):
            state['errors'].append("LLM analysis failed: invalid response format")
            state['status'] = 'error'
            state['stage'] = 'analyzer_failed'
            return state

        # Update state — prefer pre-set YouTube metadata over LLM extraction
        # article_fetcher pre-sets title/author/published_date for YouTube videos
        has_preset_title = state.get('title') and state['title'].strip()
        state['title'] = state['title'] if has_preset_title else analysis.get('title', 'Untitled')
        state['content'] = state['raw_content']
        state['summary'] = analysis.get('summary')
        state['main_topic'] = analysis.get('main_topic')
        if not state.get('author'):
            state['author'] = analysis.get('author') or state['metadata'].get('author')
        state['is_high_impact'] = analysis.get('is_high_impact', False)

        # Parse published date — keep pre-set value from YouTube metadata if available
        if not state.get('published_date'):
            published_str = analysis.get('published_date')
            if published_str:
                try:
                    state['published_date'] = datetime.fromisoformat(published_str.replace(' ', 'T'))
                except:
                    meta_date = state['metadata'].get('article:published_time') or state['metadata'].get('publish_date')
                    if meta_date:
                        try:
                            state['published_date'] = datetime.fromisoformat(meta_date)
                        except:
                            state['published_date'] = None
                    else:
                        state['published_date'] = None

        # Cache the result
        await cache_analysis(state['content_hash'], 'analysis', analysis, model)

        state['stage'] = 'analyzed'
        state['stage_timings']['analyzer'] = time.time() - stage_start

        logger.info(f"Analyzer node: Extracted title '{state['title'][:50]}...'")

        return state

    except Exception as e:
        logger.error(f"Analyzer node error: {e}")
        state['errors'].append(f"Analyzer exception: {str(e)}")
        state['status'] = 'error'
        state['stage'] = 'analyzer_failed'
        return state
