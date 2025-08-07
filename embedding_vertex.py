import pandas as pd
from typing import List, Dict
from google.cloud import aiplatform, storage
from vertexai.language_models import TextEmbeddingModel
from vertexai.vision_models import Image, MultiModalEmbeddingModel

# --- ⚙️ 설정 (사용자 환경에 맞게 수정) ---
PROJECT_ID = "ferrous-amphora-466402-i9"
LOCATION = "asia-northeast3"
#us-central1 

# --- 텍스트 인덱스 정보 ---
TEXT_INDEX_ID = "4887973499278196736"
TEXT_INDEX_ENDPOINT_ID = "1750319157326381056"
DEPLOYED_TEXT_INDEX_ID = f"deployed_{TEXT_INDEX_ID}"

# --- 이미지 인덱스 정보 ---
IMAGE_INDEX_ID = "3398407922525405184"
IMAGE_INDEX_ENDPOINT_ID = "2581233288576237568"
DEPLOYED_IMAGE_INDEX_ID = f"deployed_{IMAGE_INDEX_ID}"

# --- 데이터 정보 ---
PRODUCT_DATA_CSV = "products_data.csv"

# --- 초기화 ---
aiplatform.init(project=PROJECT_ID, location=LOCATION)
# storage_client는 더 이상 필요하지 않습니다.
# storage_client = storage.Client(project=PROJECT_ID)
print("✅ Vertex AI SDK가 초기화되었습니다.")

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
    """텍스트로부터 임베딩을 생성합니다 (3,072차원)."""
    embeddings = text_embedding_model.get_embeddings([text])
    return embeddings[0].values

def get_image_embedding(local_image_path: str) -> List[float]:
    """로컬 이미지로부터 임베딩을 생성합니다 (1,408차원)."""
    # Image.load_from_file은 로컬 경로도 지원합니다.
    image = Image.load_from_file(local_image_path)
    embeddings = multimodal_embedding_model.get_embeddings(
        image=image,
        dimension=1408
    )
    return embeddings.image_embedding

def process_and_upsert_products(csv_file_path: str):
    """상품 정보를 읽고, 각각의 인덱스에 임베딩을 업서트합니다."""
    try:
        products_df = pd.read_csv(csv_file_path)
    except FileNotFoundError:
        print(f"오류: CSV 파일을 찾을 수 없습니다. 경로를 확인하세요: {csv_file_path}")
        return
        
    text_embeddings_to_upsert = []
    image_embeddings_to_upsert = []

    print(f"\n🚀 총 {len(products_df)}개의 상품 정보 처리를 시작합니다...")

    for _, row in products_df.iterrows():
        product_id = str(row['product_id'])
        # CSV에서 로컬 경로를 읽어옵니다.
        text_path = row['text_file_local_path']
        image_path = row['image_file_local_path']

        print(f"  - 상품 ID '{product_id}' 처리 중...")
        try:
            # 텍스트 처리
            product_text = get_text_from_local_file(text_path)
            if product_text:
                text_vector = get_text_embedding(product_text)
                text_embeddings_to_upsert.append({"id": product_id, "embedding": text_vector})

            # 이미지 처리
            image_vector = get_image_embedding(image_path)
            image_embeddings_to_upsert.append({"id": product_id, "embedding": image_vector})

        except Exception as e:
            print(f"    - ❗️ 오류 발생: {product_id} 상품 처리 실패 - {e}")

    # 텍스트 인덱스에 업서트
    if text_embeddings_to_upsert:
        print(f"\n💾 텍스트 인덱스에 {len(text_embeddings_to_upsert)}개 업서트 중...")
        text_index_endpoint = aiplatform.MatchingEngineIndexEndpoint(index_endpoint_name=TEXT_INDEX_ENDPOINT_ID)
        text_index_endpoint.upsert_datapoints(datapoints=text_embeddings_to_upsert, deployed_index_id=DEPLOYED_TEXT_INDEX_ID)
        print("✅ 텍스트 인덱스 업서트 완료.")

    # 이미지 인덱스에 업서트
    if image_embeddings_to_upsert:
        print(f"\n💾 이미지 인덱스에 {len(image_embeddings_to_upsert)}개 업서트 중...")
        image_index_endpoint = aiplatform.MatchingEngineIndexEndpoint(index_endpoint_name=IMAGE_INDEX_ENDPOINT_ID)
        image_index_endpoint.upsert_datapoints(datapoints=image_embeddings_to_upsert, deployed_index_id=DEPLOYED_IMAGE_INDEX_ID)
        print("✅ 이미지 인덱스 업서트 완료.")

def reciprocal_rank_fusion(search_results: List[List[aiplatform.matching_engine.matching_engine_index_endpoint.MatchNeighbor]], k: int = 60) -> Dict[str, float]:
    """Reciprocal Rank Fusion (RRF)을 사용하여 검색 결과를 융합합니다."""
    fused_scores = {}
    for result_list in search_results:
        for rank, match in enumerate(result_list):
            doc_id = match.id
            if doc_id not in fused_scores:
                fused_scores[doc_id] = 0
            fused_scores[doc_id] += 1 / (k + rank + 1)

    reranked_results = {
        id: score
        for id, score in sorted(fused_scores.items(), key=lambda item: item[1], reverse=True)
    }
    return reranked_results

def find_similar_products_with_fusion(query_text: str, query_image_local_path: str, num_neighbors: int = 10):
    """두 인덱스에서 병렬 검색 후 RRF로 결과를 융합합니다."""
    print(f"\n🔍 쿼리로 유사 상품 검색 (Fusion 방식)...")

    # 1. 쿼리 임베딩 생성
    query_text_embedding = get_text_embedding(query_text)
    query_image_embedding = get_image_embedding(query_image_local_path)

    # 2. 각 인덱스에서 병렬 검색
    text_index_endpoint = aiplatform.MatchingEngineIndexEndpoint(index_endpoint_name=TEXT_INDEX_ENDPOINT_ID)
    image_index_endpoint = aiplatform.MatchingEngineIndexEndpoint(index_endpoint_name=IMAGE_INDEX_ENDPOINT_ID)

    print("  - 텍스트 인덱스 검색 중...")
    text_search_results = text_index_endpoint.find_neighbors(
        deployed_index_id=DEPLOYED_TEXT_INDEX_ID,
        queries=[query_text_embedding],
        num_neighbors=num_neighbors,
    )

    print("  - 이미지 인덱스 검색 중...")
    image_search_results = image_index_endpoint.find_neighbors(
        deployed_index_id=DEPLOYED_IMAGE_INDEX_ID,
        queries=[query_image_embedding],
        num_neighbors=num_neighbors,
    )

    # 3. RRF로 결과 융합
    print("  - 검색 결과 융합 (RRF) 중...")
    fused_results = reciprocal_rank_fusion([text_search_results[0], image_search_results[0]])

    # 4. 최종 결과 출력
    print("\n--- 📊 최종 융합 검색 결과 ---")
    if not fused_results:
        print("유사한 상품을 찾지 못했습니다.")
        return
    
    for i, (doc_id, score) in enumerate(list(fused_results.items())[:num_neighbors]):
        print(f"  - 최종 순위 {i+1}: 상품 ID: {doc_id}, RRF 점수: {score:.6f}")


if __name__ == "__main__":
    # --- 실행 단계 ---

    # 1. 상품 데이터 처리 및 각 Matching Engine 인덱스에 저장
    #    (최초 1회 또는 데이터 업데이트 시 실행)
    process_and_upsert_products(PRODUCT_DATA_CSV)

    # 2. 특정 쿼리로 유사 상품 검색 (융합 방식)
    #    (실제 서비스에서 사용될 기능)
    search_query_text = "여름에 시원하게 입을 수 있는 파란색 반팔 티셔츠"
    # 검색에 사용할 이미지의 로컬 경로를 지정합니다.
    search_query_image = "./query_data/query_tshirt.jpg" 

    find_similar_products_with_fusion(
        query_text=search_query_text,
        query_image_local_path=search_query_image,
        num_neighbors=5 # 최종적으로 보여줄 상위 5개 상품
    )
