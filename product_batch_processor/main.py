#!/usr/bin/env python3
"""
Product Batch Processor
Web crawling and product information extraction system with cloud storage integration.
"""

import asyncio
import time
import uuid
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import config
from config.logging_config import setup_logging, get_logger
from modules.crawler import WebCrawler
from modules.extractor import ProductExtractor
from modules.image_processor import ImageProcessor
from modules.storage import CloudStorage
from modules.embedding import EmbeddingGenerator


class ProductBatchProcessor:
    """Main batch processor for product information extraction and storage."""
    
    def __init__(self):
        self.batch_id = f"BATCH_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.logger = get_logger(__name__)
        
        # Initialize components
        self.extractor = ProductExtractor()
        self.storage = CloudStorage()
        self.embedding_generator = EmbeddingGenerator()
        
        self.logger.info("Product Batch Processor initialized",
                        module="main",
                        function="__init__",
                        batch_id=self.batch_id,
                        data={
                            "config_project": config.PROJECT_ID,
                            "config_location": config.LOCATION,
                            "config_bucket": config.GCS_BUCKET
                        })
    
    async def process_single_url(self, url: str, product_id: Optional[str] = None) -> Dict[str, Any]:
        """Process a single URL through the complete pipeline."""
        if not product_id:
            product_id = f"P{str(uuid.uuid4())[:8].upper()}"
        
        self.logger.info(f"Starting processing of URL",
                        module="main",
                        function="process_single_url",
                        batch_id=self.batch_id,
                        product_id=product_id,
                        data={"url": url})
        
        start_time = time.time()
        result = {
            "batch_id": self.batch_id,
            "url": url,
            "product_id": product_id,
            "steps": {},
            "status": "processing",
            "start_time": start_time
        }
        
        try:
            # Step 1: Web Crawling
            async with WebCrawler() as crawler:
                crawl_result = await crawler.crawl_url(url, product_id)
                result["steps"]["crawling"] = {
                    "status": crawl_result["status"],
                    "timestamp": crawl_result["timestamp"],
                    "duration_ms": crawl_result["duration_ms"]
                }
                
                if crawl_result["status"] != "success":
                    result["status"] = "failed"
                    result["error"] = f"Crawling failed: {crawl_result.get('error', 'Unknown error')}"
                    return result
                
                html_content = crawl_result["html_content"]
                html_file_path = crawl_result["html_file_path"]
            
            # Step 2: Information Extraction
            extraction_result = await self.extractor.extract_product_info(html_content, url, product_id)
            result["steps"]["extraction"] = {
                "status": extraction_result["status"],
                "timestamp": extraction_result["timestamp"],
                "duration_ms": extraction_result["duration_ms"]
            }
            
            if extraction_result["status"] != "success":
                result["status"] = "failed"
                result["error"] = f"Extraction failed: {extraction_result.get('error', 'Unknown error')}"
                return result
            
            product_info = extraction_result["product_info"]
            json_file_path = extraction_result["json_file_path"]
            
            # Step 3: Image Processing
            async with ImageProcessor() as image_processor:
                image_result = await image_processor.process_images(product_info, product_id)
                result["steps"]["image_processing"] = {
                    "status": image_result["status"],
                    "timestamp": image_result["timestamp"],
                    "duration_ms": image_result["duration_ms"]
                }
                
                if image_result["status"] != "success":
                    self.logger.warning("Image processing failed, continuing without images",
                                      module="main",
                                      function="process_single_url",
                                      product_id=product_id,
                                      error=image_result.get("error", "Unknown error"))
                    processed_images = []
                else:
                    processed_images = image_result["processed_images"]
            
            # Step 4: GCS Upload
            uploaded_images = await self.storage.upload_images_to_gcs(processed_images, product_id)
            result["steps"]["gcs_upload"] = {
                "status": "success" if uploaded_images else "failed",
                "timestamp": time.time(),
                "duration_ms": 0  # Duration is tracked in storage module
            }
            
            # Update product info with uploaded image URLs
            product_info["images"] = uploaded_images
            
            # Step 5: Embedding Generation
            embedding_result = await self.embedding_generator.generate_embeddings(
                product_info, processed_images, product_id
            )
            result["steps"]["embedding"] = {
                "status": embedding_result["status"],
                "timestamp": embedding_result["timestamp"],
                "duration_ms": embedding_result["duration_ms"]
            }
            
            if embedding_result["status"] != "success":
                self.logger.warning("Embedding generation failed, continuing without embeddings",
                                  module="main",
                                  function="process_single_url",
                                  product_id=product_id,
                                  error=embedding_result.get("error", "Unknown error"))
                embeddings = {"text_embedding": [], "image_embedding": []}
            else:
                embeddings = embedding_result["embeddings"]
            
            # Step 6: Firestore Save
            firestore_result = await self.storage.save_to_firestore(product_info, embeddings, product_id)
            result["steps"]["firestore_save"] = {
                "status": "success" if firestore_result["firestore_saved"] else "failed",
                "timestamp": firestore_result["timestamp"],
                "duration_ms": firestore_result["duration_ms"]
            }
            
            if not firestore_result["firestore_saved"]:
                result["status"] = "failed"
                result["error"] = f"Firestore save failed: {firestore_result.get('error', 'Unknown error')}"
                return result
            
            # Complete processing
            total_duration_ms = int((time.time() - start_time) * 1000)
            result.update({
                "status": "completed",
                "total_duration_ms": total_duration_ms,
                "end_time": time.time(),
                "product_info": product_info,
                "html_file_path": html_file_path,
                "json_file_path": json_file_path,
                "processed_images_count": len([img for img in uploaded_images if img.get("gcs_uploaded", False)]),
                "embeddings_generated": {
                    "text": len(embeddings["text_embedding"]) > 0,
                    "image": len(embeddings["image_embedding"]) > 0
                }
            })
            
            self.logger.info("URL processing completed successfully",
                           module="main",
                           function="process_single_url",
                           batch_id=self.batch_id,
                           product_id=product_id,
                           duration_ms=total_duration_ms,
                           data={
                               "url": url,
                               "images_processed": result["processed_images_count"],
                               "embeddings_text": result["embeddings_generated"]["text"],
                               "embeddings_image": result["embeddings_generated"]["image"]
                           })
            
            return result
        
        except Exception as e:
            total_duration_ms = int((time.time() - start_time) * 1000)
            result.update({
                "status": "failed",
                "error": str(e),
                "total_duration_ms": total_duration_ms,
                "end_time": time.time()
            })
            
            self.logger.error("URL processing failed with exception",
                            module="main",
                            function="process_single_url",
                            batch_id=self.batch_id,
                            product_id=product_id,
                            duration_ms=total_duration_ms,
                            error=str(e),
                            data={"url": url})
            
            return result
    
    async def process_batch_urls(self, urls: List[str], max_workers: Optional[int] = None) -> Dict[str, Any]:
        """Process multiple URLs in batch."""
        if max_workers is None:
            max_workers = config.MAX_WORKERS
        
        self.logger.info(f"Starting batch processing",
                        module="main",
                        function="process_batch_urls",
                        batch_id=self.batch_id,
                        data={
                            "total_urls": len(urls),
                            "max_workers": max_workers
                        })
        
        start_time = time.time()
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_workers)
        
        async def process_with_semaphore(url: str) -> Dict[str, Any]:
            async with semaphore:
                # Add delay between requests to be respectful
                await asyncio.sleep(config.REQUEST_DELAY)
                return await self.process_single_url(url)
        
        # Process URLs concurrently
        tasks = [process_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle exceptions
        processed_results = []
        success_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Task failed with exception: {str(result)}",
                                module="main",
                                function="process_batch_urls",
                                batch_id=self.batch_id,
                                data={"url": urls[i], "error": str(result)})
                processed_results.append({
                    "batch_id": self.batch_id,
                    "url": urls[i],
                    "status": "failed",
                    "error": str(result),
                    "timestamp": time.time()
                })
            else:
                processed_results.append(result)
                if result.get("status") == "completed":
                    success_count += 1
        
        total_duration_ms = int((time.time() - start_time) * 1000)
        
        batch_result = {
            "batch_id": self.batch_id,
            "total_urls": len(urls),
            "success_count": success_count,
            "failure_count": len(urls) - success_count,
            "success_rate": success_count / len(urls) if urls else 0,
            "total_duration_ms": total_duration_ms,
            "results": processed_results,
            "timestamp": time.time()
        }
        
        self.logger.info("Batch processing completed",
                        module="main",
                        function="process_batch_urls",
                        batch_id=self.batch_id,
                        duration_ms=total_duration_ms,
                        data={
                            "total_urls": len(urls),
                            "successful": success_count,
                            "failed": len(urls) - success_count,
                            "success_rate": f"{batch_result['success_rate']:.2%}"
                        })
        
        return batch_result


def read_urls_from_file(file_path: str) -> List[str]:
    """Read URLs from text file (one URL per line)."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f.readlines() if line.strip()]
        
        # Filter out comments and empty lines
        urls = [url for url in urls if not url.startswith('#') and url]
        
        return urls
    except Exception as e:
        print(f"Error reading URLs from file: {e}")
        return []


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Product Batch Processor')
    parser.add_argument('--url', type=str, help='Single URL to process')
    parser.add_argument('--file', type=str, help='File containing URLs (one per line)')
    parser.add_argument('--mode', choices=['single', 'batch'], default='single',
                       help='Processing mode')
    parser.add_argument('--workers', type=int, default=config.MAX_WORKERS,
                       help='Maximum number of concurrent workers')
    parser.add_argument('--product-id', type=str, help='Custom product ID (single mode only)')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default=config.LOG_LEVEL, help='Logging level')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    logger = get_logger(__name__)
    
    logger.info("Product Batch Processor starting",
               module="main",
               function="main",
               data={
                   "mode": args.mode,
                   "workers": args.workers,
                   "log_level": args.log_level
               })
    
    try:
        if args.mode == 'single':
            if not args.url:
                print("Error: --url is required for single mode")
                sys.exit(1)
            
            # Process single URL
            async def run_single():
                processor = ProductBatchProcessor()
                result = await processor.process_single_url(args.url, args.product_id)
                
                print(f"\n=== Processing Result ===")
                print(f"Status: {result['status']}")
                print(f"Product ID: {result['product_id']}")
                print(f"Duration: {result.get('total_duration_ms', 0)}ms")
                
                if result['status'] == 'completed':
                    print(f"Images processed: {result.get('processed_images_count', 0)}")
                    print(f"Text embedding: {'✓' if result.get('embeddings_generated', {}).get('text') else '✗'}")
                    print(f"Image embedding: {'✓' if result.get('embeddings_generated', {}).get('image') else '✗'}")
                else:
                    print(f"Error: {result.get('error', 'Unknown error')}")
                
                return result
            
            result = asyncio.run(run_single())
            
        elif args.mode == 'batch':
            if not args.file:
                print("Error: --file is required for batch mode")
                sys.exit(1)
            
            urls = read_urls_from_file(args.file)
            if not urls:
                print(f"Error: No valid URLs found in {args.file}")
                sys.exit(1)
            
            # Process batch URLs
            async def run_batch():
                processor = ProductBatchProcessor()
                result = await processor.process_batch_urls(urls, args.workers)
                
                print(f"\n=== Batch Processing Result ===")
                print(f"Batch ID: {result['batch_id']}")
                print(f"Total URLs: {result['total_urls']}")
                print(f"Successful: {result['success_count']}")
                print(f"Failed: {result['failure_count']}")
                print(f"Success Rate: {result['success_rate']:.2%}")
                print(f"Total Duration: {result['total_duration_ms']}ms")
                
                return result
            
            result = asyncio.run(run_batch())
        
        logger.info("Product Batch Processor completed successfully",
                   module="main",
                   function="main")
        
    except KeyboardInterrupt:
        logger.info("Processing interrupted by user",
                   module="main",
                   function="main")
        sys.exit(1)
    
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}",
                    module="main",
                    function="main",
                    error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()