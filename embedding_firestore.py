import os
import pandas as pd
from typing import List, Dict, Optional
from dotenv import load_dotenv
from google.cloud import aiplatform, firestore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from vertexai.language_models import TextEmbeddingModel
from vertexai.vision_models import Image, MultiModalEmbeddingModel

# .env 파일에서 환경 변수 로드
load_dotenv()

# --- ⚙️ 설정 (환경 변수에서 읽어오기) ---
PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION", "asia-northeast3") # .env에 값이 없으면 기본값 사용

# --- Firestore 정보 ---
FIRESTORE_COLLECTION = os.getenv("FIRESTORE_COLLECTION", "firestore")

# --- 데이터 정보 ---
PRODUCT_DATA_CSV = "products_data_local.csv"

# --- 초기화 ---
if not PROJECT_ID:
    raise ValueError("PROJECT_ID가 .env 파일에 설정되지 않았습니다.")

aiplatform.init(project=PROJECT_ID, location=LOCATION)

# Firestore 클라이언트 초기화 및 데이터베이스 존재 확인
try:
    # 생성된 데이터베이스 ID 'firestore'를 사용
    db = firestore.Client(project=PROJECT_ID, database='firestore')
    # 데이터베이스 존재 확인을 위한 테스트 - 간단한 작업 수행
    collections = db.collections()
    _ = list(collections)  # 제너레이터를 리스트로 변환
    print("✅ Vertex AI SDK 및 Firestore 클라이언트가 초기화되었습니다.")
except Exception as e:
    print(f"❌ Firestore 초기화 실패: {e}")
    print(f"다음 링크에서 Firestore 데이터베이스를 생성해주세요:")
    print(f"https://console.cloud.google.com/datastore/setup?project={PROJECT_ID}")
    exit(1)

# --- 임베딩 모델 로드 ---
text_embedding_model = TextEmbeddingModel.from_pretrained("gemini-embedding-001")
multimodal_embedding_model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding")
print("✅ 텍스트 및 멀티모달 임베딩 모델이 로드되었습니다.")

def get_text_from_local_file(local_path: str) -> str:
    """로컬 파일 경로에서 텍스트 내용을 읽어옵니다."""
    try:
        with open(local_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {local_path}")
        return ""
    except Exception as e:
        print(f"로컬 파일에서 텍스트를 읽는 중 오류 발생: {local_path}, 오류: {e}")
        return ""

def get_text_embedding(text: str) -> List[float]:
    """텍스트로부터 임베딩을 생성합니다 (1536차원)."""
    if not text: return []
    embeddings = text_embedding_model.get_embeddings([text], output_dimensionality=1536)
    return embeddings[0].values

def get_image_embedding(local_image_path: str) -> List[float]:
    """로컬 이미지로부터 임베딩을 생성합니다 (1408차원)."""
    try:
        image = Image.load_from_file(local_image_path)
        embeddings = multimodal_embedding_model.get_embeddings(
            image=image,
            dimension=1408
        )
        return embeddings.image_embedding
    except Exception as e:
        print(f"이미지 임베딩 생성 실패: {local_image_path}, 오류: {e}")
        return []

def process_and_upsert_products_to_firestore(csv_file_path: str):
    """상품 정보를 읽고, 임베딩을 생성하여 Firestore에 저장합니다."""
    try:
        # keep_default_na=False를 사용하여 빈 문자열을 NaN으로 읽지 않도록 합니다.
        products_df = pd.read_csv(csv_file_path, keep_default_na=False)
    except FileNotFoundError:
        print(f"오류: CSV 파일을 찾을 수 없습니다. 경로를 확인하세요: {csv_file_path}")
        return
        
    print(f"\n🚀 총 {len(products_df)}개의 상품 정보 처리를 시작합니다...")
    
    # Firestore batch 크기 제한(500개)을 고려하여 처리
    batch = db.batch()
    batch_count = 0
    max_batch_size = 500

    for _, row in products_df.iterrows():
        product_id = str(row['product_id'])
        text_path = row['text_file_local_path']
        image_path = row['image_file_local_path']

        print(f"  - 상품 ID '{product_id}' 처리 중...")
        try:
            # 텍스트 처리
            product_text = get_text_from_local_file(text_path)
            text_vector = get_text_embedding(product_text)

            # 이미지 처리 (이미지 경로가 있을 때만 임베딩 생성)
            image_vector = []
            if image_path:
                image_vector = get_image_embedding(image_path)
            else:
                print("    - 이미지 경로가 없어 이미지 임베딩을 건너뜁니다.")

            # Firestore에 저장할 데이터 구성
            product_data = {
                "product_id": product_id,
                "text_content": product_text,
                "image_path": image_path,
                "text_embedding": text_vector,
                "image_embedding": image_vector # 이미지가 없으면 빈 리스트가 저장됨
            }
            
            doc_ref = db.collection(FIRESTORE_COLLECTION).document(product_id)
            batch.set(doc_ref, product_data)
            batch_count += 1
            
            # batch 크기가 최대값에 도달하면 commit하고 새 batch 시작
            if batch_count >= max_batch_size:
                batch.commit()
                batch = db.batch()
                batch_count = 0
                print(f"    - Batch committed ({max_batch_size}개 처리 완료)")

        except Exception as e:
            print(f"    - ❗️ 오류 발생: {product_id} 상품 처리 실패 - {e}")

    # 남은 데이터가 있으면 최종 commit
    if batch_count > 0:
        batch.commit()
    print(f"\n✅ Firestore에 {len(products_df)}개 상품 정보 저장이 완료되었습니다.")


def reciprocal_rank_fusion(search_results: List[List[firestore.DocumentSnapshot]], k: int = 60) -> Dict[str, float]:
    """Reciprocal Rank Fusion (RRF)을 사용하여 검색 결과를 융합합니다."""
    fused_scores = {}
    for result_list in search_results:
        for rank, doc_snapshot in enumerate(result_list):
            doc_id = doc_snapshot.id
            if doc_id not in fused_scores:
                fused_scores[doc_id] = 0
            fused_scores[doc_id] += 1 / (k + rank + 1)

    reranked_results = {
        id: score
        for id, score in sorted(fused_scores.items(), key=lambda item: item[1], reverse=True)
    }
    return reranked_results


def find_similar_products_with_firestore(query_text: str, query_image_local_path: Optional[str] = None, num_neighbors: int = 10):
    """Firestore에서 검색 후 결과를 융합합니다. 이미지는 선택사항입니다."""
    print(f"\n🔍 Firestore에서 유사 상품 검색...")
    if query_image_local_path:
        print("  - 검색 방식: 텍스트 + 이미지")
    else:
        print("  - 검색 방식: 텍스트 전용")

    try:
        collection_ref = db.collection(FIRESTORE_COLLECTION)
        # 컬렉션에 저장된 문서 수 확인
        docs = list(collection_ref.limit(10).stream())
        print(f"  - 컬렉션에 저장된 문서 수: {len(docs)}")
        if docs:
            doc_data = docs[0].to_dict()
            print(f"  - 첫 번째 문서의 text_embedding 길이: {len(doc_data.get('text_embedding', []))}")
            print(f"  - 첫 번째 문서의 필드들: {list(doc_data.keys())}")
        search_results_to_fuse = []
    except Exception as e:
        print(f"❌ Firestore 컬렉션 접근 실패: {e}")
        return

    # 1. 텍스트 검색은 항상 수행
    print("  - 텍스트 임베딩으로 검색 중...")
    query_text_embedding = get_text_embedding(query_text)
    if query_text_embedding:
        try:
            # 먼저 일반 문서 검색으로 테스트
            all_docs = list(collection_ref.limit(5).stream())
            print(f"    - 전체 문서 검색 결과: {len(all_docs)}개")
            
            # 벡터 검색 시도 - 다른 접근 방식
            try:
                vector_query = collection_ref.find_nearest(
                    vector_field="text_embedding",
                    query_vector=query_text_embedding,
                    limit=num_neighbors,
                    distance_measure=DistanceMeasure.COSINE
                )
                text_search_results = list(vector_query.stream())  # stream() 방식으로 시도
                print(f"    - stream() 방식 결과: {len(text_search_results)}개")
                
                if len(text_search_results) == 0:
                    # get() 방식으로도 시도
                    text_search_results = vector_query.get()
                    print(f"    - get() 방식 결과: {len(text_search_results)}개")
            except Exception as vector_e:
                print(f"    - 벡터 검색 상세 오류: {vector_e}")
                text_search_results = []
            print(f"    - 벡터 검색 결과 개수: {len(text_search_results)}")
            
            # 벡터 검색 결과가 없으면 일반 문서를 사용
            if len(text_search_results) == 0 and len(all_docs) > 0:
                print("    - 벡터 검색 결과가 없어 일반 문서를 사용합니다.")
                search_results_to_fuse.append(all_docs)
            else:
                search_results_to_fuse.append(text_search_results)
        except Exception as e:
            print(f"    - 텍스트 검색 실패: {e}")
            # 오류 발생 시 일반 검색으로 대체
            try:
                all_docs = list(collection_ref.limit(num_neighbors).stream())
                if all_docs:
                    print(f"    - 대체 검색으로 {len(all_docs)}개 문서 반환")
                    search_results_to_fuse.append(all_docs)
            except Exception as fallback_e:
                print(f"    - 대체 검색도 실패: {fallback_e}")

    # 2. 이미지 검색은 이미지 경로가 있을 때만 수행
    if query_image_local_path:
        print("  - 이미지 임베딩으로 검색 중...")
        query_image_embedding = get_image_embedding(query_image_local_path)
        if query_image_embedding:
            try:
                image_search_results = collection_ref.find_nearest(
                    vector_field="image_embedding",
                    query_vector=query_image_embedding,
                    limit=num_neighbors,
                    distance_measure=DistanceMeasure.EUCLIDEAN
                ).get()  # VectorQuery를 실행하여 결과 가져오기
                search_results_to_fuse.append(image_search_results)
            except Exception as e:
                print(f"    - 이미지 검색 실패: {e}")

    # 3. RRF로 결과 융합 (결과가 하나 이상 있을 때만)
    if not search_results_to_fuse:
        print("검색 결과가 없습니다.")
        return

    print("  - 검색 결과 융합 (RRF) 중...")
    fused_results = reciprocal_rank_fusion(search_results_to_fuse)

    # 4. 최종 결과 출력
    print("\n--- 📊 최종 융합 검색 결과 ---")
    if not fused_results:
        print("유사한 상품을 찾지 못했습니다.")
        return
    
    for i, (doc_id, score) in enumerate(list(fused_results.items())[:num_neighbors]):
        print(f"  - 최종 순위 {i+1}: 상품 ID: {doc_id}, RRF 점수: {score:.6f}")


if __name__ == "__main__":
    # --- 실행 단계 ---

    # 1. 상품 데이터 처리 및 Firestore에 저장
    #    (최초 1회 또는 데이터 업데이트 시 실행)
    process_and_upsert_products_to_firestore(PRODUCT_DATA_CSV)

    # 2. 특정 쿼리로 유사 상품 검색
    
    # 예시 1: 텍스트와 이미지를 모두 사용하여 검색 (임시로 이미지 없이 테스트)
    print("\n" + "="*50)
    print("예시 1: 텍스트 + 이미지 검색 (이미지 파일 없음으로 텍스트만)")
    print("="*50)
    find_similar_products_with_firestore(
        query_text="여름에 시원하게 입을 수 있는 파란색 반팔 티셔츠",
        query_image_local_path=None,  # 이미지 파일이 없으므로 None으로 변경
        num_neighbors=5
    )

    # 예시 2: 저장된 텍스트와 동일한 내용으로 검색 (테스트)
    print("\n" + "="*50)
    print("예시 2: 저장된 텍스트 내용으로 검색 (테스트)")
    print("="*50)
    with open("./products_data.csv", 'r', encoding='utf-8') as f:
        stored_text = f.read()[:100]  # 처음 100자만 사용
    find_similar_products_with_firestore(
        query_text=stored_text,
        query_image_local_path=None,
        num_neighbors=5
    )
    
    # 예시 3: 텍스트만 사용하여 검색
    print("\n" + "="*50)
    print("예시 3: 텍스트 전용 검색")
    print("="*50)
    find_similar_products_with_firestore(
        query_text="가죽으로 된 겨울 부츠",
        query_image_local_path=None, # 이미지 경로를 제공하지 않음
        num_neighbors=5
    )