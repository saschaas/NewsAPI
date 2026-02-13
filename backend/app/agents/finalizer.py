import time
from typing import Dict, Any
from loguru import logger
from datetime import datetime
from sqlalchemy.orm import Session

from app.agents.state import NewsProcessingState
from app.models import NewsArticle, StockMention, ProcessingLog, DataSource
from app.database import SessionLocal


async def finalizer_node(state: NewsProcessingState) -> NewsProcessingState:
    """
    Finalizer Agent Node

    Saves processed data to database.
    For listing pages, tracks results and prepares to process next article.

    Args:
        state: Current workflow state

    Returns:
        Updated state with success status
    """
    stage_start = time.time()
    logger.info(f"Finalizer node: Saving article '{state['title'][:50]}...'")

    db = SessionLocal()

    try:
        # Determine the actual article URL
        # If from listing page, use the specific article URL, otherwise use source URL
        if state.get('is_listing_page') and state.get('article_links'):
            current_index = state.get('current_article_index', 0)
            article_url = state['article_links'][current_index]
        else:
            article_url = state['source_url']

        # Check for duplicate by content hash
        existing = db.query(NewsArticle).filter(
            NewsArticle.content_hash == state['content_hash']
        ).first()

        if existing:
            logger.info(f"Article already exists (ID: {existing.id}), skipping save")

            # Track this result for listing pages
            if state.get('is_listing_page'):
                state.setdefault('processed_articles', []).append({
                    'url': article_url,
                    'status': 'duplicate',
                    'article_id': existing.id
                })

                # Move to next article if available
                state['current_article_index'] = state.get('current_article_index', 0) + 1
                total_articles = len(state.get('article_links', []))

                if state['current_article_index'] < total_articles:
                    # More articles to process - continue to next article
                    logger.info(f"Duplicate found, moving to article {state['current_article_index'] + 1}/{total_articles}")
                    state['status'] = 'skipped'
                    state['stage'] = 'article_saved_continue'  # Continue to next article
                    db.close()
                    return state
                else:
                    # All articles processed
                    logger.info(f"All {total_articles} articles processed from listing page (last was duplicate)")
                    state['status'] = 'success'
                    state['stage'] = 'all_articles_finalized'
                    db.close()
                    return state

            # Single article mode - just skip
            state['status'] = 'skipped'
            state['stage'] = 'duplicate_skipped'
            db.close()
            return state

        # Create article
        article = NewsArticle(
            data_source_id=state['source_id'],
            url=article_url,  # Use the specific article URL
            title=state['title'],
            content=state['content'],
            summary=state['summary'],
            main_topic=state['main_topic'],
            author=state['author'],
            published_date=state.get('published_date'),
            content_hash=state['content_hash'],
            is_high_impact=state['is_high_impact'],
            raw_metadata_json=str(state['metadata']) if state['metadata'] else None
        )

        db.add(article)
        db.flush()  # Get article ID

        article_id = article.id
        logger.info(f"Created article ID: {article_id}")

        # Create stock mentions
        for mention in state['stock_mentions']:
            stock_mention = StockMention(
                article_id=article_id,
                ticker_symbol=mention['ticker_symbol'],
                company_name=mention['company_name'],
                stock_exchange=mention.get('stock_exchange'),
                market_segment=mention.get('market_segment'),
                sentiment_score=mention['sentiment_score'],
                sentiment_label=mention.get('sentiment_label'),
                confidence_score=mention.get('confidence_score'),
                context_snippet=mention.get('context_snippet')
            )
            db.add(stock_mention)

        logger.info(f"Created {len(state['stock_mentions'])} stock mentions")

        # Create processing logs for each stage
        total_duration = int((time.time() - state['start_time']) * 1000)  # ms

        for stage_name, duration in state['stage_timings'].items():
            log_entry = ProcessingLog(
                article_id=article_id,
                data_source_id=state['source_id'],
                stage=stage_name,
                status='success',
                duration_ms=int(duration * 1000)
            )
            db.add(log_entry)

        # Overall success log
        overall_log = ProcessingLog(
            article_id=article_id,
            data_source_id=state['source_id'],
            stage='overall',
            status='success',
            duration_ms=total_duration
        )
        db.add(overall_log)

        # Update data source last fetch status
        source = db.query(DataSource).filter(DataSource.id == state['source_id']).first()
        if source:
            source.last_fetch_timestamp = datetime.utcnow()
            source.last_fetch_status = 'success'
            source.health_status = 'healthy'
            source.error_message = None

        # Commit all changes
        db.commit()

        # Track this result for listing pages
        if state.get('is_listing_page'):
            state.setdefault('processed_articles', []).append({
                'url': article_url,
                'status': 'success',
                'article_id': article_id,
                'stocks_found': len(state['stock_mentions'])
            })

            # Move to next article if available
            state['current_article_index'] = state.get('current_article_index', 0) + 1
            total_articles = len(state.get('article_links', []))

            if state['current_article_index'] < total_articles:
                # More articles to process
                logger.info(f"Moving to article {state['current_article_index'] + 1}/{total_articles}")
                state['status'] = 'success'
                state['stage'] = 'article_saved_continue'  # Signal to fetch next article
            else:
                # All articles processed
                logger.info(f"All {total_articles} articles processed from listing page")
                state['status'] = 'success'
                state['stage'] = 'all_articles_finalized'
        else:
            # Single article mode
            state['status'] = 'success'
            state['stage'] = 'finalized'

        state['stage_timings']['finalizer'] = time.time() - stage_start

        logger.info(f"Finalizer node: Successfully saved article {article_id} with {len(state['stock_mentions'])} stocks")

        return state

    except Exception as e:
        logger.error(f"Finalizer node error: {e}")
        db.rollback()
        state['errors'].append(f"Finalizer exception: {str(e)}")
        state['status'] = 'error'
        state['stage'] = 'finalizer_failed'

        # Log the error
        try:
            error_log = ProcessingLog(
                data_source_id=state['source_id'],
                stage='finalizer',
                status='error',
                error_message=str(e)
            )
            db.add(error_log)
            db.commit()
        except:
            pass

        return state

    finally:
        db.close()
