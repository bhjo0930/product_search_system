# 먼저 필요한 라이브러리를 설치해야 합니다.
# pip install google-cloud-aiplatform Pillow requests

import vertexai
from vertexai.generative_models import GenerativeModel, Part, Image
import requests
from PIL import Image as PILImage
from io import BytesIO
import argparse # 명령줄 인자를 처리하기 위해 argparse를 임포트합니다.

def generate_image_description(project_id: str, location: str, image_source: str):
    """
    Vertex AI Gemini 모델을 사용하여 이미지에 대한 설명을 생성합니다.

    Args:
        project_id (str): Google Cloud 프로젝트 ID.
        location (str): Google Cloud 리소스 위치 (예: "us-central1").
        image_source (str): 로컬 이미지 파일 경로 또는 이미지의 웹 URL.
    """
    # Vertex AI SDK 초기화
    vertexai.init(project=project_id, location=location)

    # 사용할 멀티모달 모델 로드 (최신 gemini-2.5-flash 모델로 변경)
    # 최신 모델 버전을 확인하고 사용할 수 있습니다. 예: "gemini-1.5-flash-001"
    multimodal_model = GenerativeModel("gemini-2.5-flash")

    # 이미지 소스가 URL인지 로컬 파일인지 확인
    if image_source.startswith("http://") or image_source.startswith("https://"):
        # URL에서 이미지 데이터 로드
        try:
            response = requests.get(image_source)
            response.raise_for_status()
            image_bytes = response.content
            PILImage.open(BytesIO(image_bytes))
        except requests.exceptions.RequestException as e:
            print(f"URL에서 이미지를 다운로드하는 데 실패했습니다: {e}")
            return
        except PILImage.UnidentifiedImageError:
            print("다운로드한 파일이 유효한 이미지가 아닙니다.")
            return
    else:
        # 로컬 파일에서 이미지 데이터 로드
        try:
            with open(image_source, "rb") as f:
                image_bytes = f.read()
        except FileNotFoundError:
            print(f"파일을 찾을 수 없습니다: {image_source}")
            return

    # Vertex AI가 처리할 수 있는 이미지 객체 생성
    image = Image.from_bytes(image_bytes)

    # 모델에 전달할 프롬프트 정의
    prompt_text = """
이 이미지를 바탕으로 아래 항목에 대한 정보를 명확하고 구체적으로 추출하여 JSON형식으로 회신 주세요. 
명확한 추정이 어려운 항목은 "추정불가"라고 답변해주세요.

IF 가전제품 이미지이면 THEN 

1. 제품명 또는 추정되는 제품 종류:
2. 제품의 주된 용도 및 기능:
3. 주요 구성 요소 (예: 디스플레이, 버튼, 포트 등):
4. 브랜드나 로고 식별 여부:
5. 제품의 디자인 특징 (색상, 형태, 크기 등):
6. 제품이 사용되는 공간 추정 (예: 주방, 거실, 사무실 등):
7. 작동 여부 또는 전원 상태 추정:
8. 기타 주목할 만한 특징:

IF 의류 이미지이면 THEN

1. 의류 종류 (예: 티셔츠, 자켓, 바지 등):
2. 성별 및 연령대 대상 추정:
3. 주된 소재(소재 식별 가능 시):
4. 색상 및 패턴 특징:
5. 스타일 및 계절 감성 (예: 캐주얼/포멀, 여름/겨울용):
6. 의류에 표시된 브랜드 또는 로고 유무:
7. 촬영 방식 (마네킹/평면/모델 착용 여부 등):
8. 기타 주목할 디자인 요소 또는 부속품(지퍼, 단추 등):

IF 식품 이미지면 THEN
1. 식품명 또는 제품 종류:
2. 포장 형태 (예: 캔, 팩, 봉지 등):
3. 주요 재료 또는 맛 특징 (가능할 경우 추정):
4. 브랜드 및 로고 식별 여부:
5. 유통기한 또는 제조일자 표시 여부:
6. 열량, 영양 정보 또는 건강 관련 문구 (표시된 경우):
7. 이미지 속 문구 및 강조 메시지 (예: 무설탕, 저칼로리 등):
8. 해당 제품이 놓인 환경(진열대, 배경 소품 등)에 따른 마케팅 요소 해석:
    """

    # 이미지와 텍스트 프롬프트를 모델에 전달
    try:
        response = multimodal_model.generate_content([image, prompt_text])
        # 생성된 텍스트 설명 출력
        print("--- Vertex AI 이미지 설명 ---")
        print(response.text)
        print("--------------------------")

    except Exception as e:
        print(f"Vertex AI API 호출 중 오류가 발생했습니다: {e}")


# --- 사용 예시 ---
if __name__ == "__main__":
    # 명령줄 인자 파서 설정
    parser = argparse.ArgumentParser(
        description="Vertex AI를 사용하여 이미지 파일 또는 URL에 대한 설명을 생성합니다."
    )
    # 이미지 경로 또는 URL을 필수로 받도록 설정
    parser.add_argument(
        "image_source",
        type=str,
        help="분석할 이미지의 로컬 파일 경로 또는 웹 URL."
    )
    args = parser.parse_args()

    # 중요: 이 코드를 실행하기 전에 Google Cloud 인증을 완료해야 합니다.
    # 터미널에서 `gcloud auth application-default login` 명령을 실행하세요.

    # 여기에 자신의 Google Cloud 프로젝트 ID와 위치를 입력하세요.
    PROJECT_ID = "ferrous-amphora-466402-i9"
    LOCATION = "asia-northeast1"

    # 스크립트 실행 시 파라미터로 받은 이미지 소스를 사용합니다.
    print(f"'{args.image_source}' 이미지에 대한 설명을 생성합니다...")
    generate_image_description(PROJECT_ID, LOCATION, args.image_source)

