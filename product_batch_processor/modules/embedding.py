import time
from typing import List, Dict, Any, Optional

import vertexai
from google.cloud import aiplatform
from vertexai.language_models import TextEmbeddingModel
from vertexai.vision_models import MultiModalEmbeddingModel, Image

from config.settings import config
from config.logging_config import get_logger


class EmbeddingGenerator:
    """Generate text and image embeddings using Vertex AI models."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self._setup_models()
    
    def _setup_models(self):
        """Initialize embedding models."""
        try:
            # Initialize Vertex AI
            aiplatform.init(project=config.PROJECT_ID, location=config.LOCATION)
            vertexai.init(project=config.PROJECT_ID, location=config.LOCATION)
            
            # Initialize embedding models (기존 시스템과 동일한 모델 사용)
            self.text_model = TextEmbeddingModel.from_pretrained("gemini-embedding-001")
            self.multimodal_model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding")
            
            self.logger.info("Embedding models initialized successfully",
                           module="embedding",
                           function="_setup_models",
                           data={
                               "text_model": "gemini-embedding-001",
                               "image_model": "multimodalembedding",
                               "text_dimension": 1536,  # 기존 시스템과 동일
                               "image_dimension": 1408   # 기존 시스템과 동일
                           })
        
        except Exception as e:
            self.logger.error(f"Failed to initialize embedding models: {str(e)}",
                            module="embedding",
                            function="_setup_models",
                            error=str(e))
            raise
    
    def _prepare_text_content(self, product_info: Dict[str, Any]) -> str:
        """Prepare text content for embedding generation."""
        try:
            text_parts = []
            
            # Add product name
            name = product_info.get("name", "").strip()
            if name:
                text_parts.append(f"상품명: {name}")
            
            # Add description
            description = product_info.get("description", "").strip()
            if description:
                text_parts.append(f"설명: {description}")
            
            # Add category
            category = product_info.get("category", "").strip()
            if category:
                text_parts.append(f"카테고리: {category}")
            
            # Add brand
            brand = product_info.get("brand", "").strip()
            if brand:
                text_parts.append(f"브랜드: {brand}")
            
            # Add attributes
            attributes = product_info.get("attributes", {})
            if attributes:
                attr_parts = []
                for key, value in attributes.items():
                    if value and str(value).strip():
                        attr_parts.append(f"{key}: {value}")
                
                if attr_parts:
                    text_parts.append("속성: " + ", ".join(attr_parts))
            
            # Add product code
            product_code = product_info.get("product_code", "").strip()
            if product_code:
                text_parts.append(f"상품코드: {product_code}")
            
            # Add price information
            price = product_info.get("price")
            currency = product_info.get("currency", "KRW")
            if price is not None:
                text_parts.append(f"가격: {price} {currency}")
            
            combined_text = "\n".join(text_parts)
            
            self.logger.debug("Text content prepared for embedding",
                            module="embedding",
                            function="_prepare_text_content",
                            data={
                                "text_length": len(combined_text),
                                "parts_count": len(text_parts)
                            })
            
            return combined_text
        
        except Exception as e:
            self.logger.error(f"Failed to prepare text content: {str(e)}",
                            module="embedding",
                            function="_prepare_text_content",
                            error=str(e))
            return ""
    
    def generate_text_embedding(self, text_content: str, product_id: str) -> List[float]:
        """Generate text embedding from content."""
        try:
            if not text_content or not text_content.strip():
                self.logger.warning("Empty text content for embedding",
                                  module="embedding",
                                  function="generate_text_embedding",
                                  product_id=product_id)
                return []
            
            start_time = time.time()
            
            # Generate embedding (기존 시스템과 동일한 차원 사용)
            embeddings = self.text_model.get_embeddings(
                [text_content],
                output_dimensionality=1536  # 기존 시스템과 동일
            )
            
            if not embeddings:
                raise ValueError("No embeddings returned from model")
            
            embedding_vector = embeddings[0].values
            duration_ms = int((time.time() - start_time) * 1000)
            
            self.logger.info("Text embedding generated successfully",
                           module="embedding",
                           function="generate_text_embedding",
                           product_id=product_id,
                           duration_ms=duration_ms,
                           data={
                               "text_length": len(text_content),
                               "embedding_dimension": len(embedding_vector),
                               "model": config.TEXT_EMBEDDING_MODEL
                           })
            
            return embedding_vector
        
        except Exception as e:
            self.logger.error(f"Failed to generate text embedding: {str(e)}",
                            module="embedding",
                            function="generate_text_embedding",
                            product_id=product_id,
                            error=str(e))
            return []
    
    def generate_image_embedding(self, image_path: str, product_id: str) -> List[float]:
        """Generate image embedding from local image file."""
        try:
            if not image_path:
                self.logger.warning("No image path provided",
                                  module="embedding",
                                  function="generate_image_embedding",
                                  product_id=product_id)
                return []
            
            start_time = time.time()
            
            # Load image (기존 시스템과 동일한 방식)
            image = Image.load_from_file(image_path)
            
            # Generate embedding (기존 시스템과 동일한 차원 사용)
            embeddings = self.multimodal_model.get_embeddings(
                image=image,
                dimension=1408  # 기존 시스템과 동일
            )
            
            if not hasattr(embeddings, 'image_embedding') or not embeddings.image_embedding:
                raise ValueError("No image embedding returned from model")
            
            embedding_vector = embeddings.image_embedding
            duration_ms = int((time.time() - start_time) * 1000)
            
            self.logger.info("Image embedding generated successfully",
                           module="embedding",
                           function="generate_image_embedding",
                           product_id=product_id,
                           duration_ms=duration_ms,
                           data={
                               "image_path": image_path,
                               "embedding_dimension": len(embedding_vector),
                               "model": config.IMAGE_EMBEDDING_MODEL
                           })
            
            return embedding_vector
        
        except Exception as e:
            self.logger.error(f"Failed to generate image embedding: {str(e)}",
                            module="embedding",
                            function="generate_image_embedding",
                            product_id=product_id,
                            error=str(e),
                            data={"image_path": image_path})
            return []
    
    def _find_main_image(self, processed_images: List[Dict[str, Any]]) -> Optional[str]:
        """Find the main product image for embedding."""
        if not processed_images:
            return None
        
        # Look for successfully processed images
        processed_only = [img for img in processed_images if img.get("processed", False)]
        if not processed_only:
            return None
        
        # Prefer main type images
        main_images = [img for img in processed_only if img.get("type") == "main"]
        if main_images:
            return main_images[0].get("local_path")
        
        # Fall back to first processed image
        return processed_only[0].get("local_path")
    
    async def generate_embeddings(self, product_info: Dict[str, Any], 
                                processed_images: List[Dict[str, Any]], 
                                product_id: str) -> Dict[str, Any]:
        """Generate both text and image embeddings for a product."""
        self.logger.step_start("embedding_generation", product_id=product_id)
        start_time = time.time()
        
        try:
            embeddings = {
                "text_embedding": [],
                "image_embedding": []
            }
            
            # Generate text embedding
            text_content = self._prepare_text_content(product_info)
            if text_content:
                text_embedding = self.generate_text_embedding(text_content, product_id)
                embeddings["text_embedding"] = text_embedding
            else:
                self.logger.warning("No text content available for embedding",
                                  module="embedding",
                                  function="generate_embeddings",
                                  product_id=product_id)
            
            # Generate image embedding
            main_image_path = self._find_main_image(processed_images)
            if main_image_path:
                image_embedding = self.generate_image_embedding(main_image_path, product_id)
                embeddings["image_embedding"] = image_embedding
            else:
                self.logger.warning("No suitable image found for embedding",
                                  module="embedding",
                                  function="generate_embeddings",
                                  product_id=product_id,
                                  data={"total_images": len(processed_images)})
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            result = {
                "product_id": product_id,
                "embeddings": embeddings,
                "status": "success",
                "timestamp": time.time(),
                "duration_ms": duration_ms,
                "text_embedding_dim": len(embeddings["text_embedding"]),
                "image_embedding_dim": len(embeddings["image_embedding"])
            }
            
            self.logger.step_complete("embedding_generation",
                                    duration_ms=duration_ms,
                                    product_id=product_id,
                                    data={
                                        "text_embedding_generated": len(embeddings["text_embedding"]) > 0,
                                        "image_embedding_generated": len(embeddings["image_embedding"]) > 0,
                                        "text_dimension": len(embeddings["text_embedding"]),
                                        "image_dimension": len(embeddings["image_embedding"]),
                                        "main_image_path": main_image_path
                                    })
            
            return result
        
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            
            self.logger.step_error("embedding_generation",
                                 str(e),
                                 product_id=product_id,
                                 duration_ms=duration_ms)
            
            return {
                "product_id": product_id,
                "embeddings": {"text_embedding": [], "image_embedding": []},
                "status": "failed",
                "error": str(e),
                "timestamp": time.time(),
                "duration_ms": duration_ms
            }
    
    def validate_embeddings(self, embeddings: Dict[str, List[float]]) -> Dict[str, bool]:
        """Validate generated embeddings."""
        validation_result = {
            "text_embedding_valid": False,
            "image_embedding_valid": False
        }
        
        # Validate text embedding (기존 시스템과 동일한 차원)
        text_embedding = embeddings.get("text_embedding", [])
        if text_embedding and len(text_embedding) == 1536:  # 기존 시스템과 동일
            # Check if embedding contains valid numbers
            if all(isinstance(x, (int, float)) and not (x != x) for x in text_embedding):  # NaN check
                validation_result["text_embedding_valid"] = True
        
        # Validate image embedding (기존 시스템과 동일한 차원)
        image_embedding = embeddings.get("image_embedding", [])
        if image_embedding and len(image_embedding) == 1408:  # 기존 시스템과 동일
            # Check if embedding contains valid numbers
            if all(isinstance(x, (int, float)) and not (x != x) for x in image_embedding):  # NaN check
                validation_result["image_embedding_valid"] = True
        
        self.logger.debug("Embedding validation completed",
                        module="embedding",
                        function="validate_embeddings",
                        data={
                            "text_valid": validation_result["text_embedding_valid"],
                            "image_valid": validation_result["image_embedding_valid"],
                            "text_dim": len(text_embedding),
                            "image_dim": len(image_embedding)
                        })
        
        return validation_result