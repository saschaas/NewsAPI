import time
from typing import Dict, Any, List
from loguru import logger

from app.agents.state import NewsProcessingState
from app.agents.analyzer import get_cached_analysis, cache_analysis
from app.services import ollama_service
from app.config import settings
from app.utils.llm_config import get_model_for_step


async def ner_stock_node(state: NewsProcessingState) -> NewsProcessingState:
    """
    NER/Stock Agent Node

    Extracts stock mentions and analyzes sentiment for EACH stock separately

    CRITICAL: This agent must keep stock information completely separate.
    Each stock gets its own sentiment analysis based on its specific context.

    Args:
        state: Current workflow state

    Returns:
        Updated state with stock mentions
    """
    stage_start = time.time()
    logger.info(f"NER node: Extracting stock mentions from '{state['title'][:50]}...'")

    try:
        # Check cache
        cached = await get_cached_analysis(state['content_hash'], 'ner')

        if cached and isinstance(cached, list):
            state['stock_mentions'] = cached
            state['stage'] = 'ner_complete'
            state['stage_timings']['ner'] = time.time() - stage_start
            logger.info(f"NER node: Used cached NER ({len(cached)} stocks)")
            return state

        # Build prompt with strong emphasis on separation
        prompt = f"""You are a financial entity extraction specialist. Analyze this article and extract ALL stock mentions.

Article:
Title: {state['title']}
Content: {state['content'][:4000]}

For EACH stock mentioned:
1. Extract: ticker symbol, company name, stock exchange (NYSE/NASDAQ/etc), market segment (Technology/Healthcare/etc)
2. Analyze sentiment SPECIFICALLY AND ONLY for that stock (NOT general market sentiment)
3. Provide a confidence score (0.0 to 1.0)
4. Extract a relevant snippet that specifically mentions THIS stock

CRITICAL INSTRUCTIONS:
- If multiple stocks are mentioned, keep their information COMPLETELY SEPARATE
- DO NOT mix sentiment between different stocks
- Sentiment must be specific to EACH stock based on what the article says about THAT stock
- If the article mentions "Apple is doing well but Microsoft is struggling", Apple gets positive sentiment and Microsoft gets negative
- Sentiment score: -1.0 (very negative) to +1.0 (very positive)
- Sentiment label: very_negative, negative, neutral, positive, very_positive

If NO stocks are mentioned, return: {{"stocks": []}}

Respond ONLY with valid JSON object:
{{
  "stocks": [
    {{
      "ticker_symbol": "AAPL",
      "company_name": "Apple Inc.",
      "stock_exchange": "NASDAQ",
      "market_segment": "Technology",
      "sentiment_score": 0.75,
      "sentiment_label": "positive",
      "confidence_score": 0.92,
      "context_snippet": "Apple's Q4 earnings exceeded expectations with strong iPhone sales..."
    }}
  ]
}}"""

        # Call LLM with configured model
        model = get_model_for_step('ner')
        result = await ollama_service.generate(
            prompt=prompt,
            model=model,
            temperature=0.2,  # Lower temperature for more consistent extraction
            format="json"
        )

        if not result or not result.get('response'):
            logger.warning(f"NER analysis failed: no response from Ollama (model={model}), assuming no stocks mentioned")
            logger.debug(f"NER raw result: {result}")
            state['stock_mentions'] = []
            state['stage'] = 'ner_complete'
            state['stage_timings']['ner'] = time.time() - stage_start
            return state

        logger.debug(f"NER raw response type: {type(result['response'])}, value: {str(result['response'])[:200]}")

        stock_mentions = result['response']

        # Handle different response formats
        if isinstance(stock_mentions, dict):
            # LLM wraps the array in an object — find the list value
            # Try known keys first, then fall back to first list value
            for key in ('stocks', 'mentions', 'stock_mentions', 'results'):
                if key in stock_mentions and isinstance(stock_mentions[key], list):
                    stock_mentions = stock_mentions[key]
                    break
            else:
                # Fall back: use the first value that is a list
                for value in stock_mentions.values():
                    if isinstance(value, list):
                        stock_mentions = value
                        break
                else:
                    logger.warning(f"NER response is dict without any list values: {list(stock_mentions.keys())}")
                    stock_mentions = []

        # Validate response is now a list
        if not isinstance(stock_mentions, list):
            logger.error(f"NER response is not a list after parsing: {type(stock_mentions)}")
            state['stock_mentions'] = []
        else:
            # Validate each stock mention
            validated_mentions = []
            for mention in stock_mentions:
                if not isinstance(mention, dict):
                    continue

                # Ensure required fields
                if not mention.get('ticker_symbol') or not mention.get('company_name'):
                    continue

                # Validate sentiment score
                sentiment_score = mention.get('sentiment_score', 0.0)
                if not isinstance(sentiment_score, (int, float)):
                    sentiment_score = 0.0
                else:
                    # Clamp to [-1, 1]
                    sentiment_score = max(-1.0, min(1.0, float(sentiment_score)))

                # Validate confidence score
                confidence = mention.get('confidence_score', 0.5)
                if not isinstance(confidence, (int, float)):
                    confidence = 0.5
                else:
                    confidence = max(0.0, min(1.0, float(confidence)))

                validated_mention = {
                    'ticker_symbol': str(mention['ticker_symbol']).upper().strip(),
                    'company_name': str(mention['company_name']).strip(),
                    'stock_exchange': mention.get('stock_exchange', '').strip() or None,
                    'market_segment': mention.get('market_segment', '').strip() or None,
                    'sentiment_score': sentiment_score,
                    'sentiment_label': mention.get('sentiment_label', 'neutral'),
                    'confidence_score': confidence,
                    'context_snippet': mention.get('context_snippet', '')[:500]  # Limit length
                }

                validated_mentions.append(validated_mention)

            state['stock_mentions'] = validated_mentions

        # Cache the result
        await cache_analysis(state['content_hash'], 'ner', state['stock_mentions'], model)

        state['stage'] = 'ner_complete'
        state['stage_timings']['ner'] = time.time() - stage_start

        logger.info(f"NER node: Extracted {len(state['stock_mentions'])} stock mentions")
        for mention in state['stock_mentions']:
            logger.info(
                f"  - {mention['ticker_symbol']} ({mention['company_name']}): "
                f"sentiment={mention['sentiment_score']:.2f} ({mention['sentiment_label']})"
            )

        return state

    except Exception as e:
        logger.error(f"NER node error: {e}")
        state['errors'].append(f"NER exception: {str(e)}")
        # Don't fail the whole workflow for NER errors, just set empty stocks
        state['stock_mentions'] = []
        state['stage'] = 'ner_complete'
        state['stage_timings']['ner'] = time.time() - stage_start
        return state
