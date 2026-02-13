from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Literal

from app.services import web_scraper, youtube_service, ollama_service
from app.utils import generate_content_hash, normalize_content

router = APIRouter(prefix="/test", tags=["testing"])


class ScrapeTestRequest(BaseModel):
    """Request model for testing scraping"""
    url: str
    source_type: Literal['website', 'youtube']


class ScrapeTestResponse(BaseModel):
    """Response model for scraping test"""
    status: str
    url: str
    content_preview: str
    content_hash: str
    metadata: dict
    content_length: int


@router.post("/scrape", response_model=ScrapeTestResponse)
async def test_scrape(request: ScrapeTestRequest):
    """
    Test scraping functionality for a URL

    This endpoint is for testing and development purposes.
    It will scrape the provided URL and return a preview of the content.
    """
    try:
        if request.source_type == 'website':
            # Test web scraping
            result = await web_scraper.scrape_url(request.url)

            if result['status'] != 'success':
                raise HTTPException(
                    status_code=500,
                    detail=f"Scraping failed: {result.get('error', 'Unknown error')}"
                )

            raw_content = result['raw_content'] or ''
            normalized = normalize_content(raw_content)
            content_hash = generate_content_hash(normalized)

            return ScrapeTestResponse(
                status='success',
                url=request.url,
                content_preview=raw_content[:500] + '...' if len(raw_content) > 500 else raw_content,
                content_hash=content_hash,
                metadata=result['metadata'],
                content_length=len(raw_content)
            )

        elif request.source_type == 'youtube':
            # Test YouTube processing
            result = await youtube_service.process_youtube_url(request.url)

            if result['status'] != 'success':
                raise HTTPException(
                    status_code=500,
                    detail=f"YouTube processing failed: {result.get('error', 'Unknown error')}"
                )

            transcript = result['transcript'] or ''
            normalized = normalize_content(transcript)
            content_hash = generate_content_hash(normalized)

            return ScrapeTestResponse(
                status='success',
                url=request.url,
                content_preview=transcript[:500] + '...' if len(transcript) > 500 else transcript,
                content_hash=content_hash,
                metadata=result['metadata'],
                content_length=len(transcript)
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )


@router.get("/ollama")
async def test_ollama():
    """Test Ollama connection and basic generation"""
    # Check health
    is_healthy = await ollama_service.check_health()

    if not is_healthy:
        return {
            "status": "unhealthy",
            "message": "Ollama is not accessible"
        }

    # Test simple generation
    result = await ollama_service.generate(
        prompt="Say 'Hello from Ollama!' in JSON format with a 'message' field.",
        model="llama3.1",
        temperature=0.1
    )

    if result:
        return {
            "status": "healthy",
            "message": "Ollama is working correctly",
            "test_response": result.get('response', {})
        }
    else:
        return {
            "status": "error",
            "message": "Ollama responded but generation failed"
        }
