import json
import time
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import aiplatform

from config.settings import config
from config.logging_config import get_logger


@dataclass
class ProductImage:
    """Product image information."""
    url: str
    local_path: str = ""
    gcs_path: str = ""
    type: str = "main"  # main, thumbnail, detail
    alt_text: str = ""
    width: Optional[int] = None
    height: Optional[int] = None


@dataclass
class ProductInfo:
    """Product information data model."""
    product_id: str
    product_code: str = ""
    name: str = ""
    description: str = ""
    category: str = ""
    price: Optional[float] = None
    currency: str = "KRW"
    brand: str = ""
    images: List[ProductImage] = None
    attributes: Dict[str, Any] = None
    source: Dict[str, Any] = None
    processing: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.images is None:
            self.images = []
        if self.attributes is None:
            self.attributes = {}
        if self.source is None:
            self.source = {}
        if self.processing is None:
            self.processing = {}


class ProductExtractor:
    """Extract product information from HTML using AI and parsing."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self._setup_ai_model()
    
    def _setup_ai_model(self):
        """Initialize AI model for extraction."""
        try:
            # Initialize Vertex AI
            aiplatform.init(project=config.PROJECT_ID, location=config.LOCATION)
            vertexai.init(project=config.PROJECT_ID, location=config.LOCATION)
            
            # Initialize Gemini model
            self.model = GenerativeModel(config.EXTRACTION_MODEL)
            
            self.logger.info("AI model initialized successfully",
                           module="extractor",
                           function="_setup_ai_model",
                           data={"model": config.EXTRACTION_MODEL})
        
        except Exception as e:
            self.logger.error(f"Failed to initialize AI model: {str(e)}",
                            module="extractor",
                            function="_setup_ai_model",
                            error=str(e))
            raise
    
    def _clean_html(self, html_content: str) -> str:
        """Clean HTML content for better extraction with proper Korean encoding."""
        try:
            # Use proper encoding for Korean content
            soup = BeautifulSoup(html_content, 'html.parser', from_encoding='utf-8')
            
            # Remove script and style elements
            for script in soup(["script", "style", "noscript"]):
                script.decompose()
            
            # Remove comments
            from bs4 import Comment
            for comment in soup.findAll(text=lambda text: isinstance(text, Comment)):
                comment.extract()
            
            # Get clean text with proper encoding
            clean_text = soup.get_text()
            
            # Clean up whitespace while preserving Korean characters
            lines = []
            for line in clean_text.splitlines():
                line = line.strip()
                if line and not line.isspace():
                    # Replace multiple spaces with single space
                    line = re.sub(r'\s+', ' ', line)
                    lines.append(line)
            
            clean_text = '\n'.join(lines)
            
            # Ensure proper UTF-8 encoding
            if isinstance(clean_text, bytes):
                clean_text = clean_text.decode('utf-8', errors='replace')
            
            return clean_text
        
        except Exception as e:
            self.logger.warning(f"HTML cleaning failed: {str(e)}",
                              module="extractor",
                              function="_clean_html",
                              error=str(e))
            return html_content
    
    async def _extract_images_from_html(self, html_content: str, base_url: str) -> List[ProductImage]:
        """Extract image URLs from HTML with improved Korean site support."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser', from_encoding='utf-8')
            images = []
            
            # 1. Try to get og:image from traditional HTTP request (for meta tags that Firecrawl misses)
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(base_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200:
                            traditional_html = await response.text()
                            traditional_soup = BeautifulSoup(traditional_html, 'html.parser', from_encoding='utf-8')
                            
                            # Extract og:image from traditional HTML
                            og_image = traditional_soup.find('meta', property='og:image')
                            if og_image and og_image.get('content'):
                                og_url = og_image.get('content')
                                if og_url.startswith('//'):
                                    og_url = 'https:' + og_url
                                elif og_url.startswith('/'):
                                    og_url = urljoin(base_url, og_url)
                                
                                product_image = ProductImage(
                                    url=og_url,
                                    type="main",
                                    alt_text="Product image from og:image",
                                    width=None,
                                    height=None
                                )
                                images.append(product_image)
                                
                                self.logger.info("Successfully extracted og:image from traditional HTTP request",
                                               module="extractor", 
                                               function="_extract_images_from_html",
                                               data={"og_image_url": og_url})
            except Exception as e:
                self.logger.debug(f"Failed to get og:image from traditional HTTP: {e}")
            
            # 2. Extract from meta tags in Firecrawl content (backup)
            meta_images = []
            
            # Open Graph images
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                meta_images.append(('og:image', og_image.get('content')))
            
            # Twitter card images  
            twitter_image = soup.find('meta', {'name': 'twitter:image'})
            if twitter_image and twitter_image.get('content'):
                meta_images.append(('twitter:image', twitter_image.get('content')))
            
            # Add meta images from Firecrawl (if any)
            for source, src in meta_images:
                if src and src not in [img.url for img in images]:
                    # Convert relative URLs to absolute
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = urljoin(base_url, src)
                    elif not src.startswith(('http://', 'https://')):
                        src = urljoin(base_url, src)
                    
                    product_image = ProductImage(
                        url=src,
                        type="main",
                        alt_text=f"Product image from {source}",
                        width=None,
                        height=None
                    )
                    images.append(product_image)
            
            # 2. Look for Lotte ON specific product images in metadata
            meta_data_input = soup.find('input', {'id': 'metaData'})
            if meta_data_input:
                try:
                    meta_value = meta_data_input.get('value', '{}')
                    # Decode HTML entities
                    import html
                    meta_value = html.unescape(meta_value)
                    data = json.loads(meta_value)
                    
                    if 'product' in data and 'imgInfo' in data['product']:
                        img_info = data['product']['imgInfo']
                        image_list = img_info.get('imageList', [])
                        
                        for img_data in image_list[:5]:  # Take first 5 metadata images
                            # Build image URL from Lotte ON metadata structure
                            img_route = img_data.get('imgRteNm', '')
                            img_filename = img_data.get('imgFileNm', '')
                            
                            if img_route and img_filename:
                                img_url = f"https://contents.lotteon.com/itemimage{img_route}{img_filename}"
                                
                                # Check if not already added
                                if img_url not in [img.url for img in images]:
                                    product_image = ProductImage(
                                        url=img_url,
                                        type="main",
                                        alt_text="Product image from Lotte ON metadata",
                                        width=None,
                                        height=None
                                    )
                                    images.append(product_image)
                except (json.JSONDecodeError, AttributeError) as e:
                    self.logger.debug(f"Failed to parse metadata: {e}")
            
            # 3. Look for structured data (JSON-LD)
            script_tags = soup.find_all('script', type='application/ld+json')
            for script in script_tags:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get('@type') == 'Product':
                        image_data = data.get('image', [])
                        if isinstance(image_data, str):
                            image_data = [image_data]
                        
                        for img_url in image_data[:3]:  # Take first 3 structured data images
                            if img_url and img_url not in [img.url for img in images]:
                                product_image = ProductImage(
                                    url=img_url,
                                    type="main",
                                    alt_text="Product image from structured data",
                                    width=None,
                                    height=None
                                )
                                images.append(product_image)
                except (json.JSONDecodeError, AttributeError):
                    continue
            
            # 4. Find all img tags with improved filtering for Lotte ON
            img_tags = soup.find_all('img')
            
            for idx, img in enumerate(img_tags):
                src = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or img.get('data-original')
                if not src:
                    continue
                
                # Convert relative URLs to absolute
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = urljoin(base_url, src)
                elif not src.startswith(('http://', 'https://')):
                    src = urljoin(base_url, src)
                
                # Skip if already added from meta tags or structured data
                if any(existing.url == src for existing in images):
                    continue
                
                # Enhanced filtering for Korean e-commerce sites
                # Skip very small images, likely icons
                width = img.get('width')
                height = img.get('height')
                
                if width and height:
                    try:
                        w, h = int(width), int(height)
                        if w < 100 or h < 100:
                            continue
                    except ValueError:
                        pass
                
                # Skip common icon/logo patterns (enhanced for Korean sites)
                skip_patterns = ['favicon', 'logo', 'icon', 'sprite', 'banner', 'btn', 'button', 'arrow', 'star', 'rating']
                if any(pattern in src.lower() for pattern in skip_patterns):
                    continue
                
                # Skip placeholder or loading images
                if any(pattern in src.lower() for pattern in ['placeholder', 'loading', 'blank', 'transparent']):
                    continue
                
                # Priority for Lotte ON product images
                img_type = "detail"
                
                # Lotte ON specific patterns for main product images
                if any(keyword in src.lower() for keyword in ['itemimage', 'contents.lotteon.com/itemimage']):
                    # Check if it's the first image variant (usually _1.png, _1.jpg)
                    if '_1.' in src or src.endswith('_1.png') or src.endswith('_1.jpg'):
                        img_type = "main"
                    else:
                        img_type = "detail"
                elif any(keyword in src.lower() for keyword in ['thumb', 'small', 'mini']):
                    img_type = "thumbnail"
                elif any(keyword in src.lower() for keyword in ['main', 'primary']):
                    img_type = "main"
                
                product_image = ProductImage(
                    url=src,
                    type=img_type,
                    alt_text=img.get('alt', ''),
                    width=int(width) if width and width.isdigit() else None,
                    height=int(height) if height and height.isdigit() else None
                )
                
                images.append(product_image)
                
                # Limit number of images but prioritize main images
                if len(images) >= 10:
                    break
            
            self.logger.info(f"Extracted {len(images)} images from HTML",
                           module="extractor",
                           function="_extract_images_from_html",
                           data={"image_count": len(images), "meta_images": len(meta_images)})
            
            return images
        
        except Exception as e:
            self.logger.error(f"Failed to extract images: {str(e)}",
                            module="extractor",
                            function="_extract_images_from_html",
                            error=str(e))
            return []
    
    def _create_extraction_prompt(self, html_content: str, url: str) -> str:
        """Create enhanced prompt for comprehensive AI extraction including specifications."""
        clean_text = self._clean_html(html_content)
        
        # Limit text length to avoid token limits
        max_chars = 12000  # Increased for more detailed extraction
        if len(clean_text) > max_chars:
            clean_text = clean_text[:max_chars] + "..."
        
        prompt = f"""
다음 웹페이지 내용에서 상품 정보를 상세히 추출하여 JSON 형식으로 반환해주세요.
특히 상품 상세 정보, 제품 사양, 스펙 테이블의 모든 정보를 포함해주세요.

웹페이지 URL: {url}

웹페이지 내용:
{clean_text}

다음 JSON 형식으로 정확히 반환해주세요:
{{
    "name": "상품명",
    "description": "상품 설명 (최대 1000자)",
    "category": "카테고리",
    "price": 가격숫자 (숫자만, 단위 제외),
    "currency": "통화코드 (KRW, USD 등)",
    "brand": "브랜드명",
    "product_code": "상품코드/SKU/모델번호",
    "manufacturer": "제조사/제조업체",
    "origin_country": "원산지/제조국",
    "model_name": "품명 및 모델명",
    "product_status": "상품상태 (새상품, 중고 등)",
    "specifications": {{
        "정격전압": "정격전압 정보",
        "소비전력": "소비전력 정보", 
        "에너지소비효율등급": "효율등급",
        "크기": "제품 크기/치수",
        "용량": "용량 정보",
        "형태": "제품 형태",
        "무게": "제품 무게",
        "출시년월": "동일모델 출시년월",
        "추가설치비용": "추가 설치 비용",
        "품질보증기준": "품질보증 기준",
        "AS책임자": "A/S 책임자",
        "AS전화번호": "A/S 전화번호"
    }},
    "attributes": {{
        "color": "색상",
        "size": "크기",
        "material": "소재",
        "weight": "무게", 
        "dimensions": "치수",
        "voltage": "전압",
        "power": "전력",
        "warranty": "보증기간"
    }}
}}

주의사항:
1. 상품 상세 정보 테이블, 제품 사양, 스펙 정보를 모두 찾아서 포함하세요
2. "상품상세참조", "상품상세 참조" 같은 텍스트가 있어도 실제 값을 찾으려 노력하세요
3. 제조사, 원산지, A/S 정보, 품질보증 등 모든 제품 정보를 추출하세요
4. 정격전압, 소비전력, 에너지효율등급 등 기술 사양도 포함하세요
5. 모든 필드가 확인되지 않으면 빈 문자열 ""을 사용하세요
6. price는 숫자만 추출하고, 통화 단위는 currency 필드에 별도 기입
7. JSON 형식을 정확히 지켜주세요
8. 한국어 상품의 경우 currency는 "KRW"로 설정
9. specifications와 attributes에 모든 추가 정보를 포함하세요
10. 테이블 형태의 상품 정보가 있다면 반드시 모든 항목을 추출하세요
"""
        return prompt
    
    async def _extract_with_ai(self, html_content: str, url: str) -> Dict[str, Any]:
        """Extract product information using AI."""
        try:
            prompt = self._create_extraction_prompt(html_content, url)
            
            self.logger.debug("Sending extraction request to AI model",
                            module="extractor",
                            function="_extract_with_ai",
                            data={"prompt_length": len(prompt)})
            
            # Generate response
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": config.EXTRACTION_TEMPERATURE,
                    "max_output_tokens": config.MAX_EXTRACTION_TOKENS,
                }
            )
            
            # Parse JSON response
            response_text = response.text.strip()
            
            # Clean response (remove markdown formatting if present)
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            
            # Parse JSON
            extracted_data = json.loads(response_text)
            
            self.logger.info("AI extraction completed successfully",
                           module="extractor",
                           function="_extract_with_ai",
                           data={
                               "extracted_fields": list(extracted_data.keys()),
                               "response_length": len(response_text)
                           })
            
            return extracted_data
        
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse AI response as JSON: {str(e)}",
                            module="extractor",
                            function="_extract_with_ai",
                            error=str(e),
                            data={"response_text": response_text[:500]})
            return {}
        
        except Exception as e:
            self.logger.error(f"AI extraction failed: {str(e)}",
                            module="extractor",
                            function="_extract_with_ai",
                            error=str(e))
            return {}
    
    def _save_json(self, product_info: ProductInfo, product_id: str) -> str:
        """Save product information as JSON file."""
        try:
            file_path = config.get_file_path("json", product_id, "json")
            
            # Convert to dictionary and ensure JSON serializable
            data = asdict(product_info)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            
            self.logger.info("Product JSON saved",
                           module="extractor",
                           function="_save_json",
                           product_id=product_id,
                           data={"file_path": file_path})
            
            return file_path
        
        except Exception as e:
            self.logger.error(f"Failed to save JSON: {str(e)}",
                            module="extractor",
                            function="_save_json",
                            product_id=product_id,
                            error=str(e))
            raise
    
    async def extract_product_info(self, html_content: str, url: str, product_id: str) -> Dict[str, Any]:
        """Extract product information from HTML content."""
        self.logger.step_start("extraction", product_id=product_id, data={"url": url})
        start_time = time.time()
        
        try:
            # Extract basic info with AI
            ai_data = await self._extract_with_ai(html_content, url)
            
            # Extract images from HTML
            images = await self._extract_images_from_html(html_content, url)
            
            # Create ProductInfo object with enhanced fields
            enhanced_attributes = ai_data.get('attributes', {})
            
            # Add specifications to attributes for backward compatibility
            specifications = ai_data.get('specifications', {})
            enhanced_attributes.update({
                'manufacturer': ai_data.get('manufacturer', ''),
                'origin_country': ai_data.get('origin_country', ''),
                'model_name': ai_data.get('model_name', ''),
                'product_status': ai_data.get('product_status', ''),
                'specifications': specifications
            })
            
            product_info = ProductInfo(
                product_id=product_id,
                name=ai_data.get('name', ''),
                description=ai_data.get('description', ''),
                category=ai_data.get('category', ''),
                price=ai_data.get('price'),
                currency=ai_data.get('currency', 'KRW'),
                brand=ai_data.get('brand', ''),
                product_code=ai_data.get('product_code', ''),
                images=[asdict(img) for img in images],
                attributes=enhanced_attributes,
                source={
                    "url": url,
                    "crawl_timestamp": datetime.now().isoformat(),
                    "html_length": len(html_content)
                },
                processing={
                    "status": "completed",
                    "created_at": datetime.now().isoformat(),
                    "extracted_images": len(images)
                }
            )
            
            # Save JSON file
            json_file_path = self._save_json(product_info, product_id)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            result = {
                "product_id": product_id,
                "product_info": asdict(product_info),
                "json_file_path": json_file_path,
                "status": "success",
                "timestamp": time.time(),
                "duration_ms": duration_ms
            }
            
            self.logger.step_complete("extraction",
                                    duration_ms=duration_ms,
                                    product_id=product_id,
                                    data={
                                        "extracted_fields": len(ai_data),
                                        "image_count": len(images),
                                        "json_file_path": json_file_path
                                    })
            
            return result
        
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            
            self.logger.step_error("extraction",
                                 str(e),
                                 product_id=product_id,
                                 duration_ms=duration_ms,
                                 data={"url": url})
            
            return {
                "product_id": product_id,
                "product_info": None,
                "json_file_path": None,
                "status": "failed",
                "error": str(e),
                "timestamp": time.time(),
                "duration_ms": duration_ms
            }