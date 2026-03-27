import time
from typing import Dict, Any, List
from loguru import logger

from app.agents.state import NewsProcessingState
from app.agents.analyzer import get_cached_analysis, cache_analysis
from app.services import ollama_service
from app.config import settings
from app.utils.llm_config import get_model_for_step
import re


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

        # For YouTube videos, always include the video description as extra context
        # Descriptions often list all stocks/tickers discussed in the video
        extra_context = ""
        if state.get('source_type') == 'youtube' and state.get('metadata'):
            desc = state['metadata'].get('description', '')
            if desc:
                extra_context = f"\n\nVideo Description (may contain stock tickers and company names — use to ensure ALL stocks are captured):\n{desc[:5000]}"

        # Hint from title about expected count (e.g., "5 Stocks Wall Street Is Buying")
        title_hint = ""
        title = state.get('title', '')
        count_match = re.search(r'(\d+)\s+(?:stocks?|companies|picks?|tickers?)', title, re.IGNORECASE)
        if count_match:
            expected_count = count_match.group(1)
            title_hint = f"\nIMPORTANT: The title mentions {expected_count} stocks — make sure you find and extract ALL {expected_count} of them. Read the ENTIRE content carefully."

        # Build prompt — use configurable content limit
        content_limit = settings.LLM_MAX_CONTENT_CHARS
        prompt = f"""You are a financial entity extraction specialist. Analyze this article and extract ALL stock mentions.

Article:
Title: {state['title']}
Content: {state['content'][:content_limit]}{extra_context}

For EACH stock mentioned:
1. Extract: ticker symbol, company name, stock exchange (NYSE/NASDAQ/etc), market segment (Technology/Healthcare/etc)
2. Analyze sentiment SPECIFICALLY AND ONLY for that stock (NOT general market sentiment)
3. Provide a confidence score (0.0 to 1.0)
4. Write a DETAILED context_snippet (MINIMUM 400 characters, aim for 500-800). This is the most important field. Structure it as:
   - BUSINESS: What the company does in 1-2 sentences
   - THESIS: Why this stock is being discussed — the main bull/bear case, catalyst, or reason for attention
   - FINANCIALS: Key metrics — revenue, earnings, margins, growth rates, guidance, backlog, or any numbers mentioned
   - PROS: Bullish arguments, growth drivers, competitive advantages, institutional buying
   - CONS/RISKS: Bearish arguments, concerns, valuation risks, challenges (if mentioned)
   - TARGETS: Price targets, analyst ratings, or expected upside/downside (if mentioned)
   Write ALL of these sections into a flowing paragraph. Do NOT abbreviate or summarize too aggressively — include the specific numbers, percentages, and details from the article.
5. Set is_sponsored to true ONLY if the stock is a PAID SPONSOR with phrases like "sponsored by", "paid promotion". Otherwise false.

CRITICAL INSTRUCTIONS:
- You MUST read the ENTIRE content from beginning to end — stocks may be discussed anywhere{title_hint}
- Extract ALL stocks discussed, not just the first few
- Keep each stock's information COMPLETELY SEPARATE
- Sentiment must be specific to EACH stock based on what is said about THAT stock
- Sentiment score: -1.0 (very negative) to +1.0 (very positive)
- Sentiment label: very_negative, negative, neutral, positive, very_positive
- Use "n/a" as ticker_symbol if you cannot identify it
- context_snippet MUST be at least 400 characters. Include ALL specific numbers, growth rates, revenue figures, and details discussed. Do not write generic summaries.
- EXCLUDE stocks that are ONLY mentioned as paid sponsors/advertisements with no actual analysis

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
      "context_snippet": "Apple is a technology giant known for iPhone, Mac, and services with a $3T market cap. The stock is being discussed because institutional investors have been aggressively accumulating shares ahead of the AI product cycle. They beat Q4 earnings with revenue up 12% YoY to $94.9B, driven by iPhone sales growing 18% on AI features, while services revenue grew 24% to a record $23.1B. On the bull side, management raised full-year guidance, AI integration is driving upgrade cycles, and the installed base hit 2.2B active devices. On the bear side, China revenue declined 2%, regulatory pressure in the EU remains a concern with potential App Store changes, and the stock trades at 32x forward earnings which some consider stretched. Wall Street consensus is bullish with a median price target of $250, implying 15% upside, and 38 out of 45 analysts rate it a buy.",
      "is_sponsored": false
    }}
  ]
}}"""

        # Call LLM with configured model
        model = get_model_for_step('ner')
        result = await ollama_service.generate(
            prompt=prompt,
            model=model,
            temperature=0.2,  # Lower temperature for more consistent extraction
            format="json",
            num_ctx=settings.LLM_NUM_CTX
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
            for key in ('stocks', 'mentions', 'stock_mentions', 'results'):
                if key in stock_mentions and isinstance(stock_mentions[key], list):
                    stock_mentions = stock_mentions[key]
                    break
            else:
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
            validated_mentions = []
            for mention in stock_mentions:
                if not isinstance(mention, dict):
                    continue

                # Ensure required fields
                if not mention.get('ticker_symbol') or not mention.get('company_name'):
                    continue
                ticker_val = str(mention['ticker_symbol']).strip().upper()
                # Remove leading $ if present (e.g. "$AAPL" → "AAPL")
                ticker_clean = ticker_val.lstrip('$')

                # Reject invalid tickers
                if ticker_clean in ('', 'NONE', 'NULL', 'UNKNOWN', 'N/A', 'NA', 'STOCK'):
                    continue
                # Reject pure numbers (e.g. "$6" from "This $6 Stock")
                if ticker_clean.replace('.', '').isdigit():
                    continue
                # Reject tickers with spaces (e.g. "$6 STOCK")
                if ' ' in ticker_clean:
                    continue
                # Reject tickers that are too long (valid tickers are 1-5 chars)
                if len(ticker_clean) > 5:
                    continue
                # Reject tickers without any letters
                if not any(c.isalpha() for c in ticker_clean):
                    continue

                # Skip sponsored stocks (only mentioned as paid ads, no real analysis)
                if mention.get('is_sponsored', False):
                    logger.info(f"  Excluding sponsored stock: {ticker_val} ({mention.get('company_name')})")
                    continue

                # Validate sentiment score
                sentiment_score = mention.get('sentiment_score', 0.0)
                if not isinstance(sentiment_score, (int, float)):
                    sentiment_score = 0.0
                else:
                    sentiment_score = max(-1.0, min(1.0, float(sentiment_score)))

                # Validate confidence score
                confidence = mention.get('confidence_score', 0.5)
                if not isinstance(confidence, (int, float)):
                    confidence = 0.5
                else:
                    confidence = max(0.0, min(1.0, float(confidence)))

                validated_mention = {
                    'ticker_symbol': ticker_clean,
                    'company_name': str(mention['company_name']).strip(),
                    'stock_exchange': mention.get('stock_exchange', '').strip() or None,
                    'market_segment': mention.get('market_segment', '').strip() or None,
                    'sentiment_score': sentiment_score,
                    'sentiment_label': mention.get('sentiment_label', 'neutral'),
                    'confidence_score': confidence,
                    'context_snippet': mention.get('context_snippet', '')[:1000]
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
        state['stock_mentions'] = []
        state['stage'] = 'ner_complete'
        state['stage_timings']['ner'] = time.time() - stage_start
        return state
