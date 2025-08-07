#!/usr/bin/env python3
"""
기존 시스템과의 호환성 테스트 스크립트
"""

import sys
import os
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

# Fix relative imports by importing directly
import config.settings as settings_module
import modules.embedding as embedding_module
import modules.storage as storage_module
import config.logging_config as logging_module

config = settings_module.config
EmbeddingGenerator = embedding_module.EmbeddingGenerator
CloudStorage = storage_module.CloudStorage
setup_logging = logging_module.setup_logging
get_logger = logging_module.get_logger

def test_embedding_dimensions():
    """임베딩 차원이 기존 시스템과 동일한지 테스트"""
    print("🧪 임베딩 차원 테스트 시작...")
    
    try:
        embedding_generator = EmbeddingGenerator()
        
        # 테스트 텍스트 임베딩
        test_text = "테스트 상품입니다. 파란색 티셔츠"
        text_embedding = embedding_generator.generate_text_embedding(test_text, "TEST001")
        
        print(f"✅ 텍스트 임베딩 차원: {len(text_embedding)} (기대값: 1536)")
        assert len(text_embedding) == 1536, f"텍스트 임베딩 차원이 맞지 않습니다: {len(text_embedding)}"
        
        # 테스트 이미지 임베딩 (이미지 파일이 있는 경우)
        test_image_path = "../web_app/static/uploads/test_tshirt.png"
        if os.path.exists(test_image_path):
            image_embedding = embedding_generator.generate_image_embedding(test_image_path, "TEST001")
            print(f"✅ 이미지 임베딩 차원: {len(image_embedding)} (기대값: 1408)")
            assert len(image_embedding) == 1408, f"이미지 임베딩 차원이 맞지 않습니다: {len(image_embedding)}"
        else:
            print("⚠️  테스트 이미지 파일이 없어 이미지 임베딩 테스트를 건너뜁니다.")
        
        print("✅ 임베딩 차원 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ 임베딩 테스트 실패: {e}")
        return False

def test_firestore_data_structure():
    """Firestore 데이터 구조가 기존 시스템과 호환되는지 테스트"""
    print("\n🧪 Firestore 데이터 구조 테스트 시작...")
    
    try:
        storage = CloudStorage()
        
        # 테스트 상품 정보
        test_product_info = {
            "product_id": "TEST001",
            "name": "테스트 상품",
            "description": "테스트용 상품입니다",
            "category": "의류",
            "price": 29900,
            "currency": "KRW",
            "brand": "테스트브랜드",
            "attributes": {
                "color": "파란색",
                "size": "M"
            },
            "images": []
        }
        
        # 테스트 임베딩
        test_embeddings = {
            "text_embedding": [0.1] * 1536,  # 1536차원
            "image_embedding": [0.2] * 1408  # 1408차원
        }
        
        # 데이터 준비
        firestore_data = storage._prepare_firestore_data(test_product_info, test_embeddings)
        
        # 기존 시스템과 동일한 필드 확인
        required_fields = ["product_id", "text_content", "image_path", "text_embedding", "image_embedding"]
        for field in required_fields:
            assert field in firestore_data, f"필수 필드 누락: {field}"
        
        # 임베딩 차원 확인
        assert len(firestore_data["text_embedding"]) == 1536, "텍스트 임베딩 차원 오류"
        assert len(firestore_data["image_embedding"]) == 1408, "이미지 임베딩 차원 오류"
        
        print("✅ Firestore 데이터 구조:")
        print(f"  - product_id: {firestore_data['product_id']}")
        print(f"  - text_content 길이: {len(firestore_data['text_content'])}")
        print(f"  - text_embedding 차원: {len(firestore_data['text_embedding'])}")
        print(f"  - image_embedding 차원: {len(firestore_data['image_embedding'])}")
        print("✅ Firestore 데이터 구조 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ Firestore 데이터 구조 테스트 실패: {e}")
        return False

def test_configuration():
    """설정이 기존 시스템과 호환되는지 테스트"""
    print("\n🧪 설정 호환성 테스트 시작...")
    
    try:
        # 모델명 확인
        assert config.TEXT_EMBEDDING_MODEL == "gemini-embedding-001", "텍스트 임베딩 모델명이 다릅니다"
        assert config.IMAGE_EMBEDDING_MODEL == "multimodalembedding", "이미지 임베딩 모델명이 다릅니다"
        
        # 차원 확인
        assert config.TEXT_EMBEDDING_DIMENSION == 1536, "텍스트 임베딩 차원이 다릅니다"
        assert config.IMAGE_EMBEDDING_DIMENSION == 1408, "이미지 임베딩 차원이 다릅니다"
        
        # Firestore 컬렉션명 확인 (기존 시스템이 "firestore" 사용)
        expected_collection = "products"  # 배치 프로그램은 "products" 사용 (분리)
        print(f"✅ Firestore 컬렉션: {config.FIRESTORE_COLLECTION}")
        
        print("✅ 설정 호환성 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ 설정 테스트 실패: {e}")
        return False

def main():
    """메인 테스트 실행"""
    print("🚀 기존 시스템과의 호환성 테스트 시작\n")
    
    # 로깅 설정
    setup_logging()
    
    # 테스트 실행
    tests = [
        test_configuration,
        test_firestore_data_structure,
        test_embedding_dimensions
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__} 실행 중 오류: {e}")
    
    print(f"\n📊 테스트 결과: {passed}/{total} 통과")
    
    if passed == total:
        print("🎉 모든 호환성 테스트 통과! 기존 시스템과 완전히 호환됩니다.")
        return True
    else:
        print("⚠️  일부 테스트 실패. 호환성 문제가 있을 수 있습니다.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)