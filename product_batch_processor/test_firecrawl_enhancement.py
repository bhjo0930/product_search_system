#!/usr/bin/env python3
"""
Test script for enhanced Firecrawl configuration
Compare content extraction before and after improvements
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import config
from config.logging_config import setup_logging, get_logger
from modules.crawler import WebCrawler


async def test_enhanced_crawling():
    """Test enhanced Firecrawl configuration with sample URLs."""
    setup_logging()
    logger = get_logger(__name__)
    
    # Test URLs - use various types of websites
    test_urls = [
        "https://example.com",  # Simple static site
        "https://news.ycombinator.com",  # Content-heavy site
        # Add your specific product URLs here for testing
    ]
    
    logger.info("Starting enhanced Firecrawl test",
               data={
                   "test_urls": len(test_urls),
                   "firecrawl_enabled": bool(config.FIRECRAWL_API_KEY),
                   "enhanced_features": {
                       "actions_enabled": config.FIRECRAWL_ACTIONS_ENABLED,
                       "ads_blocked": config.FIRECRAWL_BLOCK_ADS,
                       "mobile_view": config.FIRECRAWL_MOBILE,
                       "include_tags": len(config.FIRECRAWL_INCLUDE_TAGS),
                       "exclude_tags": len(config.FIRECRAWL_EXCLUDE_TAGS)
                   }
               })
    
    async with WebCrawler() as crawler:
        results = []
        
        for i, url in enumerate(test_urls):
            logger.info(f"Testing URL {i+1}/{len(test_urls)}: {url}")
            
            try:
                result = await crawler.crawl_url(url)
                
                if result["status"] == "success":
                    content_length = len(result["html_content"])
                    logger.info(f"✅ Success: {url}",
                               data={
                                   "content_length": content_length,
                                   "duration_ms": result["duration_ms"]
                               })
                    
                    # Save sample for manual inspection
                    sample_file = f"test_output_{i+1}.html"
                    with open(sample_file, 'w', encoding='utf-8') as f:
                        f.write(result["html_content"][:5000])  # First 5KB for inspection
                    
                    results.append({
                        "url": url,
                        "status": "success",
                        "content_length": content_length,
                        "duration_ms": result["duration_ms"],
                        "sample_file": sample_file
                    })
                else:
                    logger.error(f"❌ Failed: {url}",
                                data={"error": result.get("error", "Unknown error")})
                    results.append({
                        "url": url,
                        "status": "failed",
                        "error": result.get("error", "Unknown error")
                    })
                
                # Delay between requests
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Exception for {url}: {str(e)}")
                results.append({
                    "url": url,
                    "status": "exception",
                    "error": str(e)
                })
    
    # Summary report
    successful = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] != "success"]
    
    logger.info("Enhanced Firecrawl test completed",
               data={
                   "total_urls": len(test_urls),
                   "successful": len(successful),
                   "failed": len(failed),
                   "success_rate": len(successful) / len(test_urls) if test_urls else 0,
                   "avg_content_length": sum(r.get("content_length", 0) for r in successful) / len(successful) if successful else 0
               })
    
    print("\n=== Enhanced Firecrawl Test Results ===")
    print(f"Total URLs tested: {len(test_urls)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    print(f"Success rate: {len(successful) / len(test_urls) * 100:.1f}%")
    
    if successful:
        avg_length = sum(r["content_length"] for r in successful) / len(successful)
        print(f"Average content length: {avg_length:.0f} characters")
        
        print("\n=== Successful URLs ===")
        for result in successful:
            print(f"✅ {result['url']}")
            print(f"   Content: {result['content_length']:,} chars, Duration: {result['duration_ms']}ms")
            print(f"   Sample saved to: {result['sample_file']}")
    
    if failed:
        print("\n=== Failed URLs ===")
        for result in failed:
            print(f"❌ {result['url']}")
            print(f"   Error: {result['error']}")
    
    return results


if __name__ == "__main__":
    if not config.FIRECRAWL_API_KEY:
        print("❌ FIRECRAWL_API_KEY not set. Please set it in your .env file.")
        sys.exit(1)
    
    print("🚀 Testing enhanced Firecrawl configuration...")
    print(f"🔧 Enhanced features enabled:")
    print(f"   - Actions: {config.FIRECRAWL_ACTIONS_ENABLED}")
    print(f"   - Ad blocking: {config.FIRECRAWL_BLOCK_ADS}")
    print(f"   - Mobile view: {config.FIRECRAWL_MOBILE}")
    print(f"   - Include tags: {len(config.FIRECRAWL_INCLUDE_TAGS)} tags")
    print(f"   - Exclude tags: {len(config.FIRECRAWL_EXCLUDE_TAGS)} tags")
    print()
    
    results = asyncio.run(test_enhanced_crawling())