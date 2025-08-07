import aiohttp
import asyncio
import time
from typing import Optional, Dict, Any
from urllib.parse import urljoin, urlparse
from pathlib import Path
import hashlib

try:
    from firecrawl import AsyncFirecrawlApp
    FIRECRAWL_AVAILABLE = True
except ImportError:
    FIRECRAWL_AVAILABLE = False
    print("Warning: firecrawl-py not installed. Install with: pip install firecrawl-py")

from config.settings import config
from config.logging_config import get_logger


class WebCrawler:
    """Asynchronous web crawler for product pages with Firecrawl support for dynamic content."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.session: Optional[aiohttp.ClientSession] = None
        self._semaphore = asyncio.Semaphore(config.MAX_WORKERS)
        
        # Initialize Firecrawl if API key is provided
        self.firecrawl_app = None
        if FIRECRAWL_AVAILABLE and config.FIRECRAWL_API_KEY:
            try:
                self.firecrawl_app = AsyncFirecrawlApp(api_key=config.FIRECRAWL_API_KEY)
                self.logger.info("AsyncFirecrawl initialized successfully for dynamic content crawling")
            except Exception as e:
                self.logger.warning(f"Failed to initialize AsyncFirecrawl: {e}. Falling back to traditional crawling.")
                self.firecrawl_app = None
        else:
            if not config.FIRECRAWL_API_KEY:
                self.logger.info("FIRECRAWL_API_KEY not provided. Using traditional HTTP crawling.")
            else:
                self.logger.warning("AsyncFirecrawl not available. Using traditional HTTP crawling.")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._create_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._close_session()
    
    async def _create_session(self):
        """Create aiohttp session with proper configuration."""
        timeout = aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT)
        connector = aiohttp.TCPConnector(limit=config.MAX_WORKERS, limit_per_host=3)
        
        headers = {
            'User-Agent': config.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
        }
        
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers=headers
        )
        
        self.logger.info("Web crawler session created", 
                        module="crawler", 
                        function="_create_session")
    
    async def _close_session(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
            self.logger.info("Web crawler session closed",
                           module="crawler",
                           function="_close_session")
    
    def _generate_product_id(self, url: str) -> str:
        """Generate unique product ID from URL."""
        # Create hash from URL for unique ID
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        return f"P{url_hash.upper()}"
    
    def _validate_url(self, url: str) -> bool:
        """Validate URL format."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    async def _fetch_with_retry(self, url: str, product_id: str) -> Optional[str]:
        """Fetch URL with retry logic."""
        for attempt in range(config.MAX_RETRIES):
            try:
                start_time = time.time()
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        content = await response.text()
                        duration_ms = int((time.time() - start_time) * 1000)
                        
                        self.logger.info("HTTP request successful",
                                       module="crawler",
                                       function="_fetch_with_retry",
                                       product_id=product_id,
                                       duration_ms=duration_ms,
                                       data={
                                           "url": url,
                                           "status_code": response.status,
                                           "content_length": len(content),
                                           "content_type": response.headers.get('content-type', '')
                                       })
                        return content
                    
                    else:
                        self.logger.warning(f"HTTP {response.status} response",
                                          module="crawler",
                                          function="_fetch_with_retry",
                                          product_id=product_id,
                                          data={
                                              "url": url,
                                              "status_code": response.status,
                                              "attempt": attempt + 1
                                          })
            
            except asyncio.TimeoutError:
                self.logger.warning(f"Request timeout (attempt {attempt + 1})",
                                  module="crawler",
                                  function="_fetch_with_retry",
                                  product_id=product_id,
                                  data={"url": url, "attempt": attempt + 1})
            
            except aiohttp.ClientError as e:
                self.logger.warning(f"Client error: {str(e)} (attempt {attempt + 1})",
                                  module="crawler",
                                  function="_fetch_with_retry",
                                  product_id=product_id,
                                  data={"url": url, "attempt": attempt + 1, "error": str(e)})
            
            except Exception as e:
                self.logger.error(f"Unexpected error: {str(e)} (attempt {attempt + 1})",
                                module="crawler",
                                function="_fetch_with_retry",
                                product_id=product_id,
                                data={"url": url, "attempt": attempt + 1, "error": str(e)})
            
            # Wait before retry with exponential backoff
            if attempt < config.MAX_RETRIES - 1:
                wait_time = config.REQUEST_DELAY * (config.RETRY_BACKOFF_FACTOR ** attempt)
                await asyncio.sleep(wait_time)
        
        self.logger.error("All retry attempts failed",
                        module="crawler",
                        function="_fetch_with_retry",
                        product_id=product_id,
                        data={"url": url, "max_retries": config.MAX_RETRIES})
        return None
    
    async def _fetch_with_firecrawl(self, url: str, product_id: str) -> Optional[str]:
        """Fetch URL using Firecrawl for dynamic content with enhanced configuration."""
        if not self.firecrawl_app:
            return None
        
        try:
            start_time = time.time()
            
            # Simplified Firecrawl configuration with only supported parameters
            scrape_params = {
                'url': url,
                'formats': ['html', 'markdown'],  # Multiple formats for better content extraction
                'timeout': config.FIRECRAWL_TIMEOUT * 1000,  # Convert to milliseconds
            }
            
            # Add basic actions for better dynamic content handling (if supported)
            if config.FIRECRAWL_ACTIONS_ENABLED:
                try:
                    scrape_params['actions'] = [
                        {"type": "wait", "milliseconds": 2000},  # Initial wait for page load
                        {"type": "scroll", "direction": "down", "amount": 3},  # Scroll to trigger lazy loading
                        {"type": "wait", "milliseconds": 1000},  # Wait after scroll
                        {"type": "scrape"}  # Final scrape
                    ]
                except Exception:
                    # If actions are not supported, continue without them
                    pass
            
            response = await self.firecrawl_app.scrape_url(**scrape_params)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            if response and response.success:
                # Enhanced content extraction with fallback hierarchy
                html_content = None
                content_source = "unknown"
                
                # Priority 1: Raw HTML (most complete)
                if hasattr(response, 'rawHtml') and response.rawHtml:
                    html_content = response.rawHtml
                    content_source = "rawHtml"
                # Priority 2: HTML field
                elif hasattr(response, 'html') and response.html:
                    html_content = response.html
                    content_source = "html"
                # Priority 3: Convert markdown to HTML with enhanced structure
                elif hasattr(response, 'markdown') and response.markdown:
                    # Create more structured HTML from markdown
                    title = getattr(response, 'title', '') or ''
                    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta charset="utf-8">
</head>
<body>
{response.markdown}
</body>
</html>"""
                    content_source = "markdown_converted"
                
                if html_content:
                    # Enhanced logging with more details
                    metadata = {
                        "url": url,
                        "content_length": len(html_content),
                        "content_source": content_source,
                        "method": "firecrawl_simplified",
                        "actions_used": config.FIRECRAWL_ACTIONS_ENABLED,
                        "title": getattr(response, 'title', '') or '',
                        "status_code": getattr(response, 'statusCode', 'unknown')
                    }
                    
                    self.logger.info("Simplified Firecrawl request successful",
                                   module="crawler",
                                   function="_fetch_with_firecrawl",
                                   product_id=product_id,
                                   duration_ms=duration_ms,
                                   data=metadata)
                    return html_content
                else:
                    # Log detailed response for debugging
                    response_debug = {
                        "url": url,
                        "has_html": hasattr(response, 'html'),
                        "has_rawHtml": hasattr(response, 'rawHtml'),
                        "has_markdown": hasattr(response, 'markdown'),
                        "response_keys": list(vars(response).keys()) if response else []
                    }
                    self.logger.warning("Firecrawl returned empty content",
                                      module="crawler",
                                      function="_fetch_with_firecrawl",
                                      product_id=product_id,
                                      data=response_debug)
            else:
                error_msg = getattr(response, 'error', 'Unknown error') if response else 'No response'
                status_code = getattr(response, 'statusCode', 'unknown') if response else 'no_response'
                self.logger.warning(f"Firecrawl request failed: {error_msg}",
                                  module="crawler",
                                  function="_fetch_with_firecrawl",
                                  product_id=product_id,
                                  data={
                                      "url": url, 
                                      "error": error_msg,
                                      "status_code": status_code,
                                      "success": getattr(response, 'success', False) if response else False
                                  })
                
        except Exception as e:
            self.logger.error(f"Firecrawl error: {str(e)}",
                            module="crawler",
                            function="_fetch_with_firecrawl",
                            product_id=product_id,
                            data={"url": url, "error": str(e)})
        
        return None
    
    def _save_html(self, html_content: str, product_id: str) -> str:
        """Save HTML content to local file with proper UTF-8 encoding."""
        try:
            file_path = config.get_file_path("html", product_id, "html")
            
            # Ensure proper UTF-8 encoding for Korean text
            with open(file_path, 'w', encoding='utf-8', errors='replace') as f:
                f.write(html_content)
            
            self.logger.info("HTML saved to local file",
                           module="crawler",
                           function="_save_html",
                           product_id=product_id,
                           data={
                               "file_path": file_path,
                               "file_size": len(html_content.encode('utf-8'))
                           })
            
            return file_path
        
        except Exception as e:
            self.logger.error(f"Failed to save HTML: {str(e)}",
                            module="crawler",
                            function="_save_html",
                            product_id=product_id,
                            error=str(e))
            raise
    
    async def crawl_url(self, url: str, product_id: Optional[str] = None) -> Dict[str, Any]:
        """Crawl single URL and return result."""
        if not self._validate_url(url):
            raise ValueError(f"Invalid URL format: {url}")
        
        if not product_id:
            product_id = self._generate_product_id(url)
        
        async with self._semaphore:
            self.logger.step_start("crawling", product_id=product_id, data={"url": url})
            start_time = time.time()
            
            try:
                # Try Firecrawl first for dynamic content, then fallback to traditional crawling
                html_content = None
                
                if self.firecrawl_app:
                    self.logger.info("Attempting Firecrawl for dynamic content",
                                   module="crawler",
                                   product_id=product_id,
                                   data={"url": url, "method": "firecrawl"})
                    html_content = await self._fetch_with_firecrawl(url, product_id)
                
                # Fallback to traditional HTTP crawling if Firecrawl fails or is not available
                if not html_content:
                    if self.firecrawl_app:
                        self.logger.info("Firecrawl failed, falling back to traditional HTTP crawling",
                                       module="crawler",
                                       product_id=product_id,
                                       data={"url": url, "method": "http_fallback"})
                    else:
                        self.logger.info("Using traditional HTTP crawling",
                                       module="crawler",
                                       product_id=product_id,
                                       data={"url": url, "method": "http"})
                    
                    html_content = await self._fetch_with_retry(url, product_id)
                
                if not html_content:
                    raise Exception("Failed to fetch HTML content with both Firecrawl and traditional methods")
                
                # Save HTML to local file
                html_file_path = self._save_html(html_content, product_id)
                
                # Calculate processing time
                duration_ms = int((time.time() - start_time) * 1000)
                
                result = {
                    "product_id": product_id,
                    "url": url,
                    "html_content": html_content,
                    "html_file_path": html_file_path,
                    "status": "success",
                    "timestamp": time.time(),
                    "duration_ms": duration_ms
                }
                
                self.logger.step_complete("crawling", 
                                        duration_ms=duration_ms,
                                        product_id=product_id,
                                        data={
                                            "url": url,
                                            "html_file_path": html_file_path,
                                            "content_size": len(html_content)
                                        })
                
                return result
            
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                
                self.logger.step_error("crawling", 
                                     str(e),
                                     product_id=product_id,
                                     duration_ms=duration_ms,
                                     data={"url": url})
                
                return {
                    "product_id": product_id,
                    "url": url,
                    "html_content": None,
                    "html_file_path": None,
                    "status": "failed",
                    "error": str(e),
                    "timestamp": time.time(),
                    "duration_ms": duration_ms
                }
    
    async def crawl_urls(self, urls: list) -> list:
        """Crawl multiple URLs concurrently."""
        self.logger.info(f"Starting batch crawling of {len(urls)} URLs",
                        module="crawler",
                        function="crawl_urls",
                        data={"url_count": len(urls)})
        
        start_time = time.time()
        
        # Create tasks for concurrent execution
        tasks = [self.crawl_url(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle exceptions
        processed_results = []
        success_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Task failed with exception: {str(result)}",
                                module="crawler",
                                function="crawl_urls",
                                data={"url": urls[i], "error": str(result)})
                processed_results.append({
                    "url": urls[i],
                    "status": "failed",
                    "error": str(result),
                    "timestamp": time.time()
                })
            else:
                processed_results.append(result)
                if result.get("status") == "success":
                    success_count += 1
        
        total_duration_ms = int((time.time() - start_time) * 1000)
        
        self.logger.info("Batch crawling completed",
                        module="crawler",
                        function="crawl_urls",
                        duration_ms=total_duration_ms,
                        data={
                            "total_urls": len(urls),
                            "success_count": success_count,
                            "failure_count": len(urls) - success_count,
                            "success_rate": success_count / len(urls) if urls else 0
                        })
        
        return processed_results