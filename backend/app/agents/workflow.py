import time
from typing import Literal
from loguru import logger

from langgraph.graph import StateGraph, END

from app.agents.state import NewsProcessingState
from app.agents.scraper import scraper_node
from app.agents.article_link_extractor import article_link_extractor_node
from app.agents.article_fetcher import article_fetcher_node
from app.agents.analyzer import analyzer_node
from app.agents.ner import ner_stock_node
from app.agents.finalizer import finalizer_node
from app.agents.error_handler import error_handler_node


def supervisor_router(state: NewsProcessingState) -> Literal[
    "scraper", "article_link_extractor", "article_fetcher", "analyzer", "ner", "finalizer", "error_handler", "end"
]:
    """
    Supervisor Agent - Routes workflow based on current state

    Args:
        state: Current workflow state

    Returns:
        Next node name to execute
    """
    stage = state.get('stage', 'init')
    errors = state.get('errors', [])
    status = state.get('status', '')

    logger.debug(f"Supervisor routing: stage={stage}, errors={len(errors)}, status={status}")

    # Check for errors first
    if errors or status == 'error':
        return "error_handler"

    # Route based on stage
    if stage == 'init':
        return "scraper"
    elif stage == 'scraped':
        # After scraping, extract article links
        return "article_link_extractor"
    elif stage == 'link_extraction_complete':
        # Decide if listing page or single article
        if state.get('is_listing_page') and state.get('article_links'):
            # Listing page - fetch first article
            return "article_fetcher"
        else:
            # Single article - analyze the scraped content
            return "analyzer"
    elif stage == 'article_fetched':
        # After fetching an individual article, analyze it
        return "analyzer"
    elif stage == 'article_fetch_failed':
        # Article fetch failed, check if more articles to process
        if state.get('is_listing_page'):
            total_articles = len(state.get('article_links', []))
            current_index = state.get('current_article_index', 0)
            if current_index < total_articles:
                # Try next article
                return "article_fetcher"
            else:
                # No more articles
                return "end"
        else:
            return "error_handler"
    elif stage == 'analyzed':
        return "ner"
    elif stage == 'ner_complete':
        return "finalizer"
    elif stage == 'article_saved_continue':
        # Article saved, more articles to process
        return "article_fetcher"
    elif stage == 'all_articles_finalized':
        # All articles from listing page processed
        return "end"
    elif stage == 'finalized' or stage == 'duplicate_skipped':
        # Single article finalized
        return "end"
    elif stage == 'error_handled':
        return "end"
    else:
        # Unknown stage, route to error handler
        logger.error(f"Unknown stage: {stage}")
        state['errors'].append(f"Unknown workflow stage: {stage}")
        return "error_handler"


# Build the workflow graph
workflow = StateGraph(NewsProcessingState)

# Add nodes
workflow.add_node("scraper", scraper_node)
workflow.add_node("article_link_extractor", article_link_extractor_node)
workflow.add_node("article_fetcher", article_fetcher_node)
workflow.add_node("analyzer", analyzer_node)
workflow.add_node("ner", ner_stock_node)
workflow.add_node("finalizer", finalizer_node)
workflow.add_node("error_handler", error_handler_node)

# Set entry point
workflow.set_entry_point("scraper")

# Add conditional edges from each node to supervisor
workflow.add_conditional_edges(
    "scraper",
    supervisor_router,
    {
        "article_link_extractor": "article_link_extractor",
        "error_handler": "error_handler",
        "end": END
    }
)

workflow.add_conditional_edges(
    "article_link_extractor",
    supervisor_router,
    {
        "article_fetcher": "article_fetcher",
        "analyzer": "analyzer",
        "error_handler": "error_handler",
        "end": END
    }
)

workflow.add_conditional_edges(
    "article_fetcher",
    supervisor_router,
    {
        "analyzer": "analyzer",
        "article_fetcher": "article_fetcher",  # Loop back for failed articles
        "error_handler": "error_handler",
        "end": END
    }
)

workflow.add_conditional_edges(
    "analyzer",
    supervisor_router,
    {
        "ner": "ner",
        "error_handler": "error_handler",
        "end": END
    }
)

workflow.add_conditional_edges(
    "ner",
    supervisor_router,
    {
        "finalizer": "finalizer",
        "error_handler": "error_handler",
        "end": END
    }
)

workflow.add_conditional_edges(
    "finalizer",
    supervisor_router,
    {
        "article_fetcher": "article_fetcher",  # Loop back for next article
        "end": END,
        "error_handler": "error_handler"
    }
)

workflow.add_edge("error_handler", END)

# Compile the workflow with increased recursion limit for multi-article processing
# Each article goes through ~8 steps (including supervisor routing), so 20 articles needs 162+ recursions
app = workflow.compile()

logger.info("LangGraph workflow compiled successfully with multi-article support (recursion_limit: 200)")


async def process_news_article(source_id: int, source_url: str, source_type: str, extraction_instructions: str = None) -> NewsProcessingState:
    """
    Process a news article through the full LangGraph workflow

    Args:
        source_id: Database ID of the data source
        source_url: URL to process
        source_type: 'website' or 'youtube'
        extraction_instructions: Optional user instructions for article extraction

    Returns:
        Final workflow state
    """
    logger.info(f"Starting workflow for source {source_id}: {source_url}")

    # Initialize state
    initial_state: NewsProcessingState = {
        'source_id': source_id,
        'source_url': source_url,
        'source_type': source_type,
        'extraction_instructions': extraction_instructions,
        'raw_content': None,
        'raw_html': None,
        'screenshot': None,
        'video_path': None,
        'transcript': None,
        'metadata': {},
        'is_listing_page': False,
        'article_links': [],
        'current_article_index': 0,
        'processed_articles': [],
        'title': '',
        'content': '',
        'summary': None,
        'main_topic': None,
        'author': None,
        'published_date': None,
        'is_high_impact': False,
        'stock_mentions': [],
        'content_hash': '',
        'stage': 'init',
        'errors': [],
        'status': '',
        'start_time': time.time(),
        'stage_timings': {}
    }

    # Run workflow with increased recursion limit for multi-article processing
    try:
        result = await app.ainvoke(
            initial_state,
            config={"recursion_limit": 200}
        )

        total_time = time.time() - initial_state['start_time']
        logger.info(
            f"Workflow completed for {source_url}: "
            f"status={result['status']}, stage={result['stage']}, time={total_time:.2f}s"
        )

        return result

    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")
        initial_state['errors'].append(f"Workflow exception: {str(e)}")
        initial_state['status'] = 'error'
        initial_state['stage'] = 'workflow_failed'
        return initial_state
