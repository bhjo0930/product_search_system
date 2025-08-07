import os
import numpy as np
from typing import List, Dict
from dotenv import load_dotenv
from google.cloud import aiplatform, firestore
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

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """코사인 유사도 계산"""
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

def manual_similarity_search(query_text: str, num_results: int = 3):
    """수동 유사도 검색"""
    print(f"\n🔍 검색 쿼리: '{query_text}'")
    print("="*80)
    
    # 쿼리 임베딩 생성
    query_embedding = get_text_embedding(query_text)
    
    # 모든 문서 가져오기
    collection_ref = db.collection(FIRESTORE_COLLECTION)
    all_docs = list(collection_ref.stream())
    
    # 각 문서와의 유사도 계산
    similarities = []
    for doc in all_docs:
        doc_data = doc.to_dict()
        product_embedding = doc_data.get('text_embedding', [])
        
        if product_embedding:
            similarity = cosine_similarity(query_embedding, product_embedding)
            similarities.append({
                'product_id': doc.id,
                'similarity': similarity,
                'text_content': doc_data.get('text_content', '')
            })
    
    # 유사도 순으로 정렬
    similarities.sort(key=lambda x: x['similarity'], reverse=True)
    
    # 결과 출력
    print(f"📊 유사도 기반 검색 결과 (상위 {num_results}개):")
    for i, result in enumerate(similarities[:num_results]):
        print(f"\n  {i+1}. 상품 ID: {result['product_id']}")
        print(f"     유사도 점수: {result['similarity']:.4f}")
        
        # 상품 제목 추출
        content = result['text_content']
        title_line = content.split('\n')[0] if content else "제목 없음"
        print(f"     상품명: {title_line}")
        
        # 내용 미리보기
        preview = content[:120].replace('\n', ' ') + "..." if len(content) > 120 else content.replace('\n', ' ')
        print(f"     내용: {preview}")

if __name__ == "__main__":
    # 다양한 검색 쿼리 테스트
    test_queries = [
        "여름에 시원한 반팔 티셔츠",
        "운동할 때 신는 편안한 운동화",
        "겨울에 따뜻한 패딩 점퍼",
        "캐주얼한 청바지 데님 팬츠",
        "여행갈 때 쓸 백팩 가방",
        "후드티 스웨트셔츠"
    ]
    
    for query in test_queries:
        manual_similarity_search(query, num_results=3)
        print()