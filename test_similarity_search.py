import os
import pandas as pd
from typing import List, Dict, Optional
from dotenv import load_dotenv
from google.cloud import aiplatform, firestore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from vertexai.language_models import TextEmbeddingModel

load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION", "asia-northeast3")
FIRESTORE_COLLECTION = "firestore"

# 초기화
aiplatform.init(project=PROJECT_ID, location=LOCATION)
db = firestore.Client(project=PROJECT_ID, database='firestore')
text_embedding_model = TextEmbeddingModel.from_pretrained("gemini-embedding-001")

def get_text_embedding(text: str) -> List[float]:
    """텍스트로부터 임베딩을 생성합니다 (1536차원)."""
    if not text: return []
    embeddings = text_embedding_model.get_embeddings([text], output_dimensionality=1536)
    return embeddings[0].values

def search_similar_products(query_text: str, num_neighbors: int = 5):
    """유사 상품 검색 함수"""
    print(f"\n🔍 검색 쿼리: '{query_text}'")
    print("="*80)
    
    collection_ref = db.collection(FIRESTORE_COLLECTION)
    
    # 전체 문서 수 확인
    all_docs = list(collection_ref.stream())
    print(f"총 상품 수: {len(all_docs)}")
    
    # 쿼리 임베딩 생성
    query_embedding = get_text_embedding(query_text)
    
    # 벡터 검색 시도
    try:
        vector_query = collection_ref.find_nearest(
            vector_field="text_embedding",
            query_vector=query_embedding,
            limit=num_neighbors,
            distance_measure=DistanceMeasure.COSINE
        )
        vector_results = list(vector_query.stream())
        
        if len(vector_results) > 0:
            print("🎯 벡터 검색 성공!")
            for i, doc in enumerate(vector_results):
                doc_data = doc.to_dict()
                # 상품 정보 표시
                text_preview = doc_data.get('text_content', '')[:100] + "..."
                print(f"  {i+1}. 상품 ID: {doc.id}")
                print(f"     내용 미리보기: {text_preview}")
                print()
        else:
            print("⚠️ 벡터 검색 결과 없음 - 대체 검색 사용")
            # 대체 검색으로 모든 문서 반환
            for i, doc in enumerate(all_docs[:num_neighbors]):
                doc_data = doc.to_dict()
                text_preview = doc_data.get('text_content', '')[:100] + "..."
                print(f"  {i+1}. 상품 ID: {doc.id}")
                print(f"     내용 미리보기: {text_preview}")
                print()
                
    except Exception as e:
        print(f"❌ 검색 오류: {e}")

if __name__ == "__main__":
    # 다양한 검색 쿼리 테스트
    test_queries = [
        "여름에 시원한 반팔 티셔츠",
        "운동할 때 신는 편안한 신발",
        "겨울에 따뜻한 패딩 점퍼",
        "캐주얼한 청바지",
        "여행갈 때 쓸 백팩",
        "후드티"
    ]
    
    for query in test_queries:
        search_similar_products(query, num_neighbors=3)
        print()