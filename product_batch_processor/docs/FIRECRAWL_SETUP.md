# 🔥 Firecrawl 설정 가이드

Product Batch Processor에서 동적 웹페이지를 처리하기 위한 Firecrawl 설정 방법입니다.

## 🌟 Firecrawl이 필요한 이유

- **동적 콘텐츠**: JavaScript로 로드되는 콘텐츠 추출
- **SPA (Single Page Application)** 지원
- **더 정확한 정보 추출**: 완전히 렌더링된 페이지에서 데이터 추출
- **자동 폴백**: Firecrawl 실패 시 기존 HTTP 크롤링으로 자동 전환

## 🚀 설정 방법

### 1. Firecrawl 계정 생성 및 API 키 발급

1. [Firecrawl 웹사이트](https://firecrawl.dev) 방문
2. 계정 생성 및 로그인
3. Dashboard에서 API 키 발급

### 2. 환경 변수 설정

`.env` 파일에 Firecrawl API 키 추가:

```bash
# Google Cloud Configuration
PROJECT_ID="your-google-cloud-project"
LOCATION="asia-northeast3"
GCS_BUCKET="your-storage-bucket"
FIRESTORE_DATABASE="firestore"
FIRESTORE_COLLECTION="products"

# Logging Configuration
LOG_LEVEL=INFO

# Firecrawl Configuration (동적 웹페이지 처리용)
FIRECRAWL_API_KEY=fc-your-api-key-here
```

### 3. 패키지 설치 확인

```bash
pip install firecrawl-py
```

## 🔧 동작 방식

### 크롤링 우선순위

1. **Firecrawl 시도**: API 키가 설정된 경우 우선 사용
2. **HTTP 폴백**: Firecrawl 실패 시 기존 HTTP 크롤링 사용
3. **에러 처리**: 두 방법 모두 실패 시 에러 리포트

### 로그 예시

```json
// Firecrawl 성공
{
  "message": "Firecrawl request successful",
  "method": "firecrawl",
  "wait_time": 5000,
  "content_length": 45123
}

// Firecrawl 실패 → HTTP 폴백
{
  "message": "Firecrawl failed, falling back to traditional HTTP crawling",
  "method": "http_fallback"
}
```

## ⚙️ 고급 설정

### config/settings.py에서 Firecrawl 옵션 조정

```python
# Firecrawl Settings
FIRECRAWL_API_KEY: str = os.getenv("FIRECRAWL_API_KEY", "")
FIRECRAWL_TIMEOUT: int = 60
FIRECRAWL_WAIT_FOR: int = 5000  # 동적 콘텐츠 대기 시간 (ms)
```

### 대기 시간 조정

동적 콘텐츠가 많은 사이트의 경우 대기 시간을 늘릴 수 있습니다:

```bash
# .env 파일에 추가 (선택사항)
FIRECRAWL_WAIT_FOR=10000  # 10초 대기
```

## 💰 비용 고려사항

### Firecrawl 요금제

- **Free Tier**: 월 500 크레딧
- **Pro Plan**: 더 많은 크레딧 및 고급 기능

### 비용 최적화 팁

1. **선택적 사용**: 동적 콘텐츠가 확실한 사이트만 Firecrawl 사용
2. **폴백 활용**: API 키 없이도 기본 HTTP 크롤링으로 동작
3. **스크린샷 비활성화**: 설정에서 `screenshot: false`로 크레딧 절약

## 🧪 테스트

### API 키 없이 테스트 (HTTP 폴백)

```bash
python main.py --url "https://example.com/product/123"
```

로그에서 "Using traditional HTTP crawling" 메시지 확인

### API 키로 테스트 (Firecrawl 사용)

```bash
# .env에 FIRECRAWL_API_KEY 설정 후
python main.py --url "https://spa-website.com/product/123"
```

로그에서 "Firecrawl request successful" 메시지 확인

## 🔍 문제 해결

### 일반적인 문제

1. **API 키 오류**
   ```
   Error: Invalid API key
   ```
   → `.env` 파일의 API 키 확인

2. **크레딧 부족**
   ```
   Error: Insufficient credits
   ```
   → Firecrawl 대시보드에서 크레딧 확인

3. **타임아웃**
   ```
   Error: Request timeout
   ```
   → `FIRECRAWL_TIMEOUT` 값 증가

### 로그 확인

```bash
# Firecrawl 관련 로그 필터링
grep "firecrawl\|Firecrawl" data/logs/batch_processor.log
```

## 📊 성능 비교

| 항목 | HTTP 크롤링 | Firecrawl |
|------|-------------|-----------|
| 속도 | 빠름 (200ms) | 보통 (2-5초) |
| 동적 콘텐츠 | 제한적 | 완전 지원 |
| SPA 지원 | 없음 | 완전 지원 |
| 비용 | 무료 | 유료 (크레딧) |
| 안정성 | 높음 | 높음 + 폴백 |

## 🎯 권장사항

1. **시작**: API 키 없이 HTTP 크롤링으로 시작
2. **평가**: 동적 콘텐츠 필요성 확인 후 Firecrawl 도입
3. **모니터링**: 로그를 통해 성공률 및 비용 모니터링
4. **최적화**: 필요한 사이트만 선별적으로 Firecrawl 사용

이제 동적 웹페이지와 SPA 사이트에서도 정확한 상품 정보 추출이 가능합니다! 🚀