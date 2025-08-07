import time
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from google.cloud import firestore, storage
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

from config.settings import config
from config.logging_config import get_logger


class CloudStorage:
    """Handle Firestore and Google Cloud Storage operations."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self._setup_clients()
        self._semaphore = asyncio.Semaphore(config.MAX_WORKERS)
    
    def _setup_clients(self):
        """Initialize Google Cloud clients."""
        try:
            # Initialize Firestore client
            self.firestore_client = firestore.Client(
                project=config.PROJECT_ID,
                database=config.FIRESTORE_DATABASE
            )
            
            # Initialize Cloud Storage client
            self.storage_client = storage.Client(project=config.PROJECT_ID)
            self.bucket = self.storage_client.bucket(config.GCS_BUCKET)
            
            self.logger.info("Cloud storage clients initialized",
                           module="storage",
                           function="_setup_clients",
                           data={
                               "project_id": config.PROJECT_ID,
                               "firestore_database": config.FIRESTORE_DATABASE,
                               "gcs_bucket": config.GCS_BUCKET
                           })
        
        except Exception as e:
            self.logger.error(f"Failed to initialize cloud clients: {str(e)}",
                            module="storage",
                            function="_setup_clients",
                            error=str(e))
            raise
    
    def _prepare_firestore_data(self, product_info: Dict[str, Any], 
                               embeddings: Dict[str, List[float]]) -> Dict[str, Any]:
        """Prepare data for Firestore storage (기존 시스템과 호환)."""
        # 기존 embedding_firestore.py와 동일한 구조로 저장
        
        # 텍스트 콘텐츠 준비 (기존 시스템 방식)
        text_content = self._prepare_text_content(product_info)
        
        # 이미지 경로 준비 (첫 번째 성공적으로 처리된 이미지) - 완전한 GCS URL 사용
        image_path = ""
        images = product_info.get("images", [])
        for img in images:
            if img.get("gcs_uploaded", False):
                # GCS 공개 URL 사용 (web_app과 호환)
                image_path = img.get("public_url", "")
                if not image_path:
                    # 공개 URL이 없으면 GCS 경로로부터 생성
                    gcs_path = img.get("gcs_path", "")
                    if gcs_path:
                        image_path = f"https://storage.googleapis.com/{config.GCS_BUCKET}/{gcs_path}"
                break
        
        # 기존 시스템과 동일한 구조
        data = {
            "product_id": product_info.get("product_id", ""),
            "text_content": text_content,  # 텍스트 콘텐츠 (기존 시스템과 동일)
            "image_path": image_path,      # 이미지 경로 (기존 시스템과 동일)
            "text_embedding": embeddings.get("text_embedding", []),   # 1536차원
            "image_embedding": embeddings.get("image_embedding", []), # 1408차원
            "created_at": datetime.now().isoformat()
        }
        
        # 추가 정보는 별도 필드에 저장 (기존 데이터와 호환성 유지)
        if product_info.get("name"):
            data["name"] = product_info.get("name", "")
        if product_info.get("description"):
            data["description"] = product_info.get("description", "")
        if product_info.get("category"):
            data["category"] = product_info.get("category", "")
        if product_info.get("price"):
            data["price"] = product_info.get("price")
        if product_info.get("brand"):
            data["brand"] = product_info.get("brand", "")
        
        return data
    
    def _prepare_text_content(self, product_info: Dict[str, Any]) -> str:
        """기존 시스템과 호환되는 텍스트 콘텐츠 준비"""
        text_parts = []
        
        # 상품명
        name = product_info.get("name", "").strip()
        if name:
            text_parts.append(f"상품명: {name}")
        
        # 설명
        description = product_info.get("description", "").strip()
        if description:
            text_parts.append(f"설명: {description}")
        
        # 카테고리
        category = product_info.get("category", "").strip()
        if category:
            text_parts.append(f"카테고리: {category}")
        
        # 브랜드
        brand = product_info.get("brand", "").strip()
        if brand:
            text_parts.append(f"브랜드: {brand}")
        
        # 가격
        price = product_info.get("price")
        currency = product_info.get("currency", "KRW")
        if price is not None:
            text_parts.append(f"가격: {price} {currency}")
        
        # 속성
        attributes = product_info.get("attributes", {})
        if attributes:
            attr_parts = []
            for key, value in attributes.items():
                if value and str(value).strip():
                    attr_parts.append(f"{key}: {value}")
            if attr_parts:
                text_parts.append("속성: " + ", ".join(attr_parts))
        
        return "\n".join(text_parts)
    
    async def upload_image_to_gcs(self, local_path: str, gcs_path: str, 
                                 product_id: str) -> Dict[str, Any]:
        """Upload image to Google Cloud Storage."""
        try:
            blob = self.bucket.blob(gcs_path)
            
            # Upload file
            blob.upload_from_filename(local_path)
            
            # Make blob public (optional, depends on requirements)
            blob.make_public()
            
            public_url = blob.public_url
            
            self.logger.info("Image uploaded to GCS successfully",
                           module="storage",
                           function="upload_image_to_gcs",
                           product_id=product_id,
                           data={
                               "local_path": local_path,
                               "gcs_path": gcs_path,
                               "public_url": public_url,
                               "blob_size": blob.size
                           })
            
            return {
                "success": True,
                "gcs_path": gcs_path,
                "public_url": public_url,
                "blob_size": blob.size
            }
        
        except Exception as e:
            self.logger.error(f"Failed to upload image to GCS: {str(e)}",
                            module="storage",
                            function="upload_image_to_gcs",
                            product_id=product_id,
                            error=str(e),
                            data={
                                "local_path": local_path,
                                "gcs_path": gcs_path
                            })
            return {
                "success": False,
                "error": str(e)
            }
    
    async def upload_images_to_gcs(self, processed_images: List[Dict[str, Any]], 
                                  product_id: str) -> List[Dict[str, Any]]:
        """Upload all processed images to GCS."""
        self.logger.step_start("gcs_upload", product_id=product_id)
        start_time = time.time()
        
        try:
            uploaded_images = []
            
            for index, image_info in enumerate(processed_images):
                if not image_info.get("processed", False):
                    # Skip failed images
                    uploaded_images.append({
                        **image_info,
                        "gcs_uploaded": False,
                        "gcs_error": "Image not processed"
                    })
                    continue
                
                local_path = image_info.get("local_path", "")
                if not local_path:
                    uploaded_images.append({
                        **image_info,
                        "gcs_uploaded": False,
                        "gcs_error": "No local path"
                    })
                    continue
                
                # Generate GCS path
                filename = local_path.split("/")[-1]
                gcs_path = config.get_gcs_path("image", filename)
                
                # Upload to GCS
                upload_result = await self.upload_image_to_gcs(local_path, gcs_path, product_id)
                
                if upload_result["success"]:
                    uploaded_images.append({
                        **image_info,
                        "gcs_path": gcs_path,
                        "public_url": upload_result["public_url"],
                        "gcs_uploaded": True,
                        "gcs_size": upload_result["blob_size"]
                    })
                else:
                    uploaded_images.append({
                        **image_info,
                        "gcs_uploaded": False,
                        "gcs_error": upload_result["error"]
                    })
            
            duration_ms = int((time.time() - start_time) * 1000)
            success_count = sum(1 for img in uploaded_images if img.get("gcs_uploaded", False))
            
            self.logger.step_complete("gcs_upload",
                                    duration_ms=duration_ms,
                                    product_id=product_id,
                                    data={
                                        "total_images": len(uploaded_images),
                                        "successful_uploads": success_count,
                                        "failed_uploads": len(uploaded_images) - success_count
                                    })
            
            return uploaded_images
        
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            
            self.logger.step_error("gcs_upload",
                                 str(e),
                                 product_id=product_id,
                                 duration_ms=duration_ms)
            raise
    
    async def save_to_firestore(self, product_info: Dict[str, Any], 
                               embeddings: Dict[str, List[float]], 
                               product_id: str) -> Dict[str, Any]:
        """Save product information and embeddings to Firestore."""
        self.logger.step_start("firestore_save", product_id=product_id)
        start_time = time.time()
        
        try:
            # Prepare data for Firestore
            firestore_data = self._prepare_firestore_data(product_info, embeddings)
            
            # Save to Firestore
            doc_ref = self.firestore_client.collection(config.FIRESTORE_COLLECTION).document(product_id)
            doc_ref.set(firestore_data)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            result = {
                "product_id": product_id,
                "firestore_saved": True,
                "document_path": f"{config.FIRESTORE_COLLECTION}/{product_id}",
                "timestamp": time.time(),
                "duration_ms": duration_ms
            }
            
            self.logger.step_complete("firestore_save",
                                    duration_ms=duration_ms,
                                    product_id=product_id,
                                    data={
                                        "document_path": result["document_path"],
                                        "text_embedding_dim": len(embeddings.get("text_embedding", [])),
                                        "image_embedding_dim": len(embeddings.get("image_embedding", [])),
                                        "image_count": len(product_info.get("images", []))
                                    })
            
            return result
        
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            
            self.logger.step_error("firestore_save",
                                 str(e),
                                 product_id=product_id,
                                 duration_ms=duration_ms)
            
            return {
                "product_id": product_id,
                "firestore_saved": False,
                "error": str(e),
                "timestamp": time.time(),
                "duration_ms": duration_ms
            }
    
    async def get_product_from_firestore(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve product data from Firestore."""
        try:
            doc_ref = self.firestore_client.collection(config.FIRESTORE_COLLECTION).document(product_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                self.logger.info("Product retrieved from Firestore",
                               module="storage",
                               function="get_product_from_firestore",
                               product_id=product_id)
                return data
            else:
                self.logger.warning("Product not found in Firestore",
                                  module="storage",
                                  function="get_product_from_firestore",
                                  product_id=product_id)
                return None
        
        except Exception as e:
            self.logger.error(f"Failed to retrieve product from Firestore: {str(e)}",
                            module="storage",
                            function="get_product_from_firestore",
                            product_id=product_id,
                            error=str(e))
            return None
    
    async def search_similar_products(self, query_embedding: List[float], 
                                    embedding_type: str = "text_embedding",
                                    limit: int = 10) -> List[Dict[str, Any]]:
        """Search for similar products using vector search."""
        try:
            collection_ref = self.firestore_client.collection(config.FIRESTORE_COLLECTION)
            
            # Perform vector search
            vector_query = collection_ref.find_nearest(
                vector_field=embedding_type,
                query_vector=query_embedding,
                limit=limit,
                distance_measure=DistanceMeasure.COSINE
            )
            
            results = vector_query.get()
            
            similar_products = []
            for doc in results:
                data = doc.to_dict()
                data['document_id'] = doc.id
                similar_products.append(data)
            
            self.logger.info("Vector search completed",
                           module="storage",
                           function="search_similar_products",
                           data={
                               "embedding_type": embedding_type,
                               "query_dimension": len(query_embedding),
                               "results_count": len(similar_products),
                               "limit": limit
                           })
            
            return similar_products
        
        except Exception as e:
            self.logger.error(f"Vector search failed: {str(e)}",
                            module="storage",
                            function="search_similar_products",
                            error=str(e),
                            data={
                                "embedding_type": embedding_type,
                                "query_dimension": len(query_embedding)
                            })
            return []
    
    async def delete_product(self, product_id: str) -> bool:
        """Delete product from Firestore and associated GCS files."""
        try:
            # Get product data first to find GCS files
            product_data = await self.get_product_from_firestore(product_id)
            
            if product_data:
                # Delete GCS files
                images = product_data.get("images", [])
                for image in images:
                    gcs_path = image.get("gcs_path", "")
                    if gcs_path:
                        try:
                            blob = self.bucket.blob(gcs_path)
                            if blob.exists():
                                blob.delete()
                                self.logger.info(f"Deleted GCS file: {gcs_path}",
                                               module="storage",
                                               function="delete_product",
                                               product_id=product_id)
                        except Exception as e:
                            self.logger.warning(f"Failed to delete GCS file {gcs_path}: {str(e)}",
                                              module="storage",
                                              function="delete_product",
                                              product_id=product_id)
            
            # Delete Firestore document
            doc_ref = self.firestore_client.collection(config.FIRESTORE_COLLECTION).document(product_id)
            doc_ref.delete()
            
            self.logger.info("Product deleted successfully",
                           module="storage",
                           function="delete_product",
                           product_id=product_id)
            
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to delete product: {str(e)}",
                            module="storage",
                            function="delete_product",
                            product_id=product_id,
                            error=str(e))
            return False