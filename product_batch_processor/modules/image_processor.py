import aiohttp
import asyncio
import time
import hashlib
from typing import List, Dict, Any, Optional
from pathlib import Path
from urllib.parse import urlparse
import os

from PIL import Image, ImageOps, ExifTags

from config.settings import config
from config.logging_config import get_logger


class ImageProcessor:
    """Process and download product images."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.session: Optional[aiohttp.ClientSession] = None
        self._semaphore = asyncio.Semaphore(config.MAX_WORKERS)
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._create_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._close_session()
    
    async def _create_session(self):
        """Create aiohttp session for image downloads."""
        timeout = aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT)
        connector = aiohttp.TCPConnector(limit=config.MAX_WORKERS)
        
        headers = {
            'User-Agent': config.USER_AGENT,
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers=headers
        )
        
        self.logger.info("Image processor session created",
                        module="image_processor",
                        function="_create_session")
    
    async def _close_session(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
            self.logger.info("Image processor session closed",
                           module="image_processor",
                           function="_close_session")
    
    def _generate_image_filename(self, product_id: str, image_index: int, image_url: str) -> str:
        """Generate unique filename for image."""
        # Get file extension from URL or default to jpg
        parsed_url = urlparse(image_url)
        path = parsed_url.path
        
        if '.' in path:
            original_ext = path.split('.')[-1].lower()
            if original_ext in config.SUPPORTED_FORMATS:
                extension = original_ext
            else:
                extension = 'jpg'
        else:
            extension = 'jpg'
        
        # If converting to JPG, use jpg extension
        if config.CONVERT_TO_JPG and extension != 'jpg':
            extension = 'jpg'
        
        return f"{product_id}_{image_index:02d}.{extension}"
    
    def _validate_image_size(self, content_length: Optional[str]) -> bool:
        """Validate image size before download."""
        if not content_length:
            return True  # Allow if size unknown
        
        try:
            size = int(content_length)
            return size <= config.MAX_IMAGE_SIZE
        except (ValueError, TypeError):
            return True
    
    def _fix_image_orientation(self, image: Image.Image) -> Image.Image:
        """Fix image orientation based on EXIF data."""
        try:
            # Check if image has EXIF data
            if hasattr(image, '_getexif'):
                exif = image._getexif()
                if exif is not None:
                    # Get orientation tag (274 is the EXIF orientation tag)
                    orientation_tag = None
                    for tag, name in ExifTags.TAGS.items():
                        if name == 'Orientation':
                            orientation_tag = tag
                            break
                    
                    orientation = exif.get(orientation_tag, 1) if orientation_tag else 1
                    
                    # Apply rotation based on orientation
                    if orientation == 2:
                        image = image.transpose(Image.FLIP_LEFT_RIGHT)
                    elif orientation == 3:
                        image = image.rotate(180, expand=True)
                    elif orientation == 4:
                        image = image.transpose(Image.FLIP_TOP_BOTTOM)
                    elif orientation == 5:
                        image = image.transpose(Image.FLIP_LEFT_RIGHT).rotate(90, expand=True)
                    elif orientation == 6:
                        image = image.rotate(270, expand=True)
                    elif orientation == 7:
                        image = image.transpose(Image.FLIP_LEFT_RIGHT).rotate(270, expand=True)
                    elif orientation == 8:
                        image = image.rotate(90, expand=True)
            
            return image
        
        except Exception as e:
            self.logger.warning(f"Failed to fix image orientation: {str(e)}",
                              module="image_processor",
                              function="_fix_image_orientation")
            return image
    
    def _resize_image(self, image: Image.Image) -> Image.Image:
        """Resize image if it exceeds maximum dimensions."""
        try:
            width, height = image.size
            
            if width <= config.MAX_IMAGE_WIDTH and height <= config.MAX_IMAGE_HEIGHT:
                return image
            
            # Calculate new size maintaining aspect ratio
            ratio = min(config.MAX_IMAGE_WIDTH / width, config.MAX_IMAGE_HEIGHT / height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            
            # Use high-quality resampling
            resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            self.logger.info("Image resized",
                           module="image_processor",
                           function="_resize_image",
                           data={
                               "original_size": f"{width}x{height}",
                               "new_size": f"{new_width}x{new_height}",
                               "ratio": ratio
                           })
            
            return resized_image
        
        except Exception as e:
            self.logger.warning(f"Failed to resize image: {str(e)}",
                              module="image_processor",
                              function="_resize_image")
            return image
    
    def _convert_to_jpg(self, image: Image.Image) -> Image.Image:
        """Convert image to JPG format."""
        try:
            # If already RGB, return as is
            if image.mode == 'RGB':
                return image
            
            # Convert to RGB
            if image.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparent images
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                return background
            else:
                return image.convert('RGB')
        
        except Exception as e:
            self.logger.warning(f"Failed to convert image to JPG: {str(e)}",
                              module="image_processor",
                              function="_convert_to_jpg")
            return image
    
    def _process_image_file(self, image_path: str) -> Dict[str, Any]:
        """Process downloaded image file."""
        try:
            with Image.open(image_path) as img:
                # Fix orientation
                img = self._fix_image_orientation(img)
                
                # Resize if needed
                img = self._resize_image(img)
                
                # Convert to JPG if needed
                if config.CONVERT_TO_JPG:
                    img = self._convert_to_jpg(img)
                    
                    # Update file path if conversion changed extension
                    if not image_path.lower().endswith('.jpg'):
                        new_path = os.path.splitext(image_path)[0] + '.jpg'
                        img.save(new_path, 'JPEG', quality=config.JPG_QUALITY, optimize=True)
                        
                        # Remove original if different
                        if new_path != image_path:
                            os.remove(image_path)
                            image_path = new_path
                    else:
                        img.save(image_path, 'JPEG', quality=config.JPG_QUALITY, optimize=True)
                else:
                    # Save in original format
                    img.save(image_path, optimize=True)
                
                # Get final image info
                final_img = Image.open(image_path)
                
                return {
                    "success": True,
                    "file_path": image_path,
                    "width": final_img.width,
                    "height": final_img.height,
                    "format": final_img.format,
                    "file_size": os.path.getsize(image_path)
                }
        
        except Exception as e:
            self.logger.error(f"Failed to process image: {str(e)}",
                            module="image_processor",
                            function="_process_image_file",
                            error=str(e))
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _download_image(self, image_url: str, product_id: str, image_index: int) -> Dict[str, Any]:
        """Download single image."""
        filename = self._generate_image_filename(product_id, image_index, image_url)
        file_path = config.get_file_path("image", product_id + f"_{image_index:02d}", 
                                       filename.split('.')[-1])
        
        try:
            async with self.session.get(image_url) as response:
                if response.status != 200:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}",
                        "image_url": image_url
                    }
                
                # Check content length
                content_length = response.headers.get('content-length')
                if not self._validate_image_size(content_length):
                    return {
                        "success": False,
                        "error": "Image too large",
                        "image_url": image_url,
                        "content_length": content_length
                    }
                
                # Download image data
                image_data = await response.read()
                
                # Save to file
                with open(file_path, 'wb') as f:
                    f.write(image_data)
                
                self.logger.info("Image downloaded",
                               module="image_processor",
                               function="_download_image",
                               product_id=product_id,
                               data={
                                   "image_url": image_url,
                                   "file_path": file_path,
                                   "file_size": len(image_data),
                                   "content_type": response.headers.get('content-type', '')
                               })
                
                return {
                    "success": True,
                    "file_path": file_path,
                    "image_url": image_url,
                    "file_size": len(image_data),
                    "content_type": response.headers.get('content-type', '')
                }
        
        except Exception as e:
            self.logger.error(f"Failed to download image: {str(e)}",
                            module="image_processor",
                            function="_download_image",
                            product_id=product_id,
                            error=str(e),
                            data={"image_url": image_url})
            return {
                "success": False,
                "error": str(e),
                "image_url": image_url
            }
    
    async def process_images(self, product_info: Dict[str, Any], product_id: str) -> Dict[str, Any]:
        """Process all images for a product."""
        self.logger.step_start("image_processing", product_id=product_id)
        start_time = time.time()
        
        try:
            images = product_info.get('images', [])
            if not images:
                self.logger.info("No images to process",
                               module="image_processor",
                               function="process_images",
                               product_id=product_id)
                return {
                    "product_id": product_id,
                    "processed_images": [],
                    "status": "success",
                    "timestamp": time.time(),
                    "duration_ms": 0
                }
            
            processed_images = []
            
            # Process images with semaphore for concurrency control
            async with self._semaphore:
                for index, image_info in enumerate(images[:10]):  # Limit to 10 images
                    image_url = image_info.get('url', '')
                    if not image_url:
                        continue
                    
                    # Download image
                    download_result = await self._download_image(image_url, product_id, index)
                    
                    if download_result['success']:
                        # Process image file
                        process_result = self._process_image_file(download_result['file_path'])
                        
                        if process_result['success']:
                            processed_image = {
                                **image_info,
                                "local_path": process_result['file_path'],
                                "processed": True,
                                "width": process_result['width'],
                                "height": process_result['height'],
                                "format": process_result['format'],
                                "file_size": process_result['file_size']
                            }
                        else:
                            processed_image = {
                                **image_info,
                                "processed": False,
                                "error": process_result['error']
                            }
                    else:
                        processed_image = {
                            **image_info,
                            "processed": False,
                            "error": download_result['error']
                        }
                    
                    processed_images.append(processed_image)
            
            duration_ms = int((time.time() - start_time) * 1000)
            success_count = sum(1 for img in processed_images if img.get('processed', False))
            
            result = {
                "product_id": product_id,
                "processed_images": processed_images,
                "status": "success",
                "timestamp": time.time(),
                "duration_ms": duration_ms,
                "success_count": success_count,
                "total_count": len(processed_images)
            }
            
            self.logger.step_complete("image_processing",
                                    duration_ms=duration_ms,
                                    product_id=product_id,
                                    data={
                                        "total_images": len(processed_images),
                                        "successful": success_count,
                                        "failed": len(processed_images) - success_count
                                    })
            
            return result
        
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            
            self.logger.step_error("image_processing",
                                 str(e),
                                 product_id=product_id,
                                 duration_ms=duration_ms)
            
            return {
                "product_id": product_id,
                "processed_images": [],
                "status": "failed",
                "error": str(e),
                "timestamp": time.time(),
                "duration_ms": duration_ms
            }