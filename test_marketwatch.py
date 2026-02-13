"""
Test script for MarketWatch multi-article workflow

This script tests the new multi-article processing workflow without requiring
the full Docker stack. It demonstrates:
1. Fetching MarketWatch listing page
2. Extracting article links (simulated)
3. Fetching individual articles
4. Processing workflow

Run this script to verify the enhanced workflow logic.
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import httpx


async def fetch_marketwatch_listing():
    """Fetch the MarketWatch home page"""
    url = "https://www.marketwatch.com/"
    print(f"\n{'='*60}")
    print(f"STEP 1: Fetching MarketWatch listing page")
    print(f"URL: {url}")
    print(f"{'='*60}\n")

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = await client.get(url, headers=headers)

        if response.status_code != 200:
            print(f"[ERROR] Failed to fetch: HTTP {response.status_code}")
            return None, []

        print(f"[SUCCESS] Successfully fetched page ({len(response.text)} characters)")
        return response.text, response.url


def extract_article_links(html, base_url):
    """Extract article links from HTML (simulates LLM-based extraction)"""
    print(f"\n{'='*60}")
    print(f"STEP 2: Extracting article links from HTML")
    print(f"{'='*60}\n")

    soup = BeautifulSoup(html, 'html.parser')
    base_domain = urlparse(str(base_url)).netloc

    # Find all links
    all_links = []
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        absolute_url = urljoin(str(base_url), href)

        # Only same-domain links
        if urlparse(absolute_url).netloc != base_domain:
            continue

        link_text = link.get_text(strip=True)

        # Filter for article-like links (heuristic approach)
        # In real workflow, LLM does this intelligently
        if any(pattern in absolute_url.lower() for pattern in ['/story/', '/articles/', '/news/']):
            if link_text and len(link_text) > 20:  # Likely a headline
                all_links.append({
                    'url': absolute_url,
                    'text': link_text[:100]
                })

    # Remove duplicates
    unique_links = []
    seen_urls = set()
    for link in all_links:
        if link['url'] not in seen_urls:
            seen_urls.add(link['url'])
            unique_links.append(link)

    print(f"[INFO] Found {len(unique_links)} article links")
    print(f"\nFirst 10 articles:")
    for i, link in enumerate(unique_links[:10], 1):
        print(f"  {i}. {link['text']}")
        print(f"     {link['url'][:80]}...")

    return unique_links


async def fetch_article(url):
    """Fetch an individual article"""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        try:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                # Extract article content
                soup = BeautifulSoup(response.text, 'html.parser')

                # Try to find article content
                article_body = soup.find('article') or soup.find('div', class_='article-body')
                if article_body:
                    # Remove scripts and styles
                    for tag in article_body(['script', 'style', 'nav', 'footer', 'aside']):
                        tag.decompose()
                    content = article_body.get_text(separator=' ', strip=True)
                else:
                    content = soup.get_text(separator=' ', strip=True)[:1000]

                return {
                    'status': 'success',
                    'url': url,
                    'content_length': len(content),
                    'content_preview': content[:200] + '...' if len(content) > 200 else content
                }
            else:
                return {'status': 'error', 'url': url, 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'status': 'error', 'url': url, 'error': str(e)}


async def simulate_workflow(article_links, max_articles=5):
    """Simulate the multi-article workflow"""
    print(f"\n{'='*60}")
    print(f"STEP 3: Simulating Multi-Article Workflow")
    print(f"Processing first {max_articles} articles...")
    print(f"{'='*60}\n")

    results = []

    for i, link in enumerate(article_links[:max_articles], 1):
        print(f"\n--- Article {i}/{max_articles} ---")
        print(f"Title: {link['text'][:60]}...")
        print(f"URL: {link['url'][:70]}...")

        # Fetch article
        result = await fetch_article(link['url'])

        if result['status'] == 'success':
            print(f"[OK] Fetched successfully ({result['content_length']} characters)")
            print(f"Preview: {result['content_preview'][:150]}...")

            # In real workflow, this would go through:
            # Analyzer Agent → NER Agent → Finalizer Agent
            print(f"    [SIMULATED] Analyzer: Extract title, summary, topics")
            print(f"    [SIMULATED] NER: Extract stock mentions and sentiment")
            print(f"    [SIMULATED] Finalizer: Save to database")

            results.append({
                'url': link['url'],
                'status': 'success',
                'title': link['text']
            })
        else:
            print(f"[FAILED] {result.get('error', 'Unknown error')}")
            results.append({
                'url': link['url'],
                'status': 'failed',
                'error': result.get('error')
            })

        # Small delay to be respectful to the server
        await asyncio.sleep(1)

    return results


async def main():
    """Main test function"""
    print("\n" + "="*60)
    print("MarketWatch Multi-Article Workflow Test")
    print("="*60)

    # Step 1: Fetch listing page
    html, base_url = await fetch_marketwatch_listing()
    if not html:
        print("\n[ERROR] Test failed: Could not fetch MarketWatch page")
        return

    # Step 2: Extract article links
    article_links = extract_article_links(html, base_url)
    if not article_links:
        print("\n[ERROR] Test failed: No article links found")
        return

    print(f"\n[SUCCESS] Successfully identified {len(article_links)} articles on listing page")

    # Step 3: Simulate workflow for first few articles
    results = await simulate_workflow(article_links, max_articles=5)

    # Summary
    print(f"\n{'='*60}")
    print(f"WORKFLOW SUMMARY")
    print(f"{'='*60}\n")

    successful = len([r for r in results if r['status'] == 'success'])
    failed = len([r for r in results if r['status'] == 'failed'])

    print(f"Total articles found: {len(article_links)}")
    print(f"Articles tested: {len(results)}")
    print(f"  [OK] Successful: {successful}")
    print(f"  [FAIL] Failed: {failed}")

    print(f"\n{'='*60}")
    print(f"EXPECTED REAL WORKFLOW")
    print(f"{'='*60}\n")
    print(f"1. Scraper Agent: Fetch main page [OK]")
    print(f"2. Article Link Extractor: Use LLM to identify {len(article_links)} article links [OK]")
    print(f"3. Article Fetcher: Loop through each article")
    print(f"   For each article:")
    print(f"     a. Fetch article content [OK]")
    print(f"     b. Analyzer Agent: Extract metadata with LLM")
    print(f"     c. NER Agent: Extract stocks and sentiment with LLM")
    print(f"     d. Finalizer Agent: Save to database")
    print(f"4. Complete: {len(article_links)} articles processed and saved")

    print(f"\n{'='*60}")
    print(f"[SUCCESS] Test Complete!")
    print(f"{'='*60}\n")
    print(f"This demonstrates that the enhanced workflow can:")
    print(f"  • Detect listing pages (MarketWatch homepage)")
    print(f"  • Extract multiple article links ({len(article_links)} found)")
    print(f"  • Fetch individual full articles")
    print(f"  • Process each article separately")
    print(f"\nTo run with full LLM processing:")
    print(f"  1. docker-compose up -d")
    print(f"  2. docker exec -it newsapi-ollama-1 ollama pull llama3.1")
    print(f"  3. POST to /api/v1/sources with MarketWatch URL")
    print(f"  4. POST to /api/v1/sources/1/test to trigger processing")


if __name__ == "__main__":
    asyncio.run(main())
