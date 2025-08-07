# Firecrawl 개선 사항 요약

## 🎯 개선 목표
Firecrawl playground 수준의 콘텐츠 추출을 위한 설정 최적화

## 📊 변경 사항

### 1. 설정 파일 개선 (config/settings.py)

**추가된 설정:**
```python
FIRECRAWL_BLOCK_ADS: bool = True          # 광고 및 팝업 차단
FIRECRAWL_MOBILE: bool = False            # 모바일 뷰 에뮬레이션
FIRECRAWL_SCREENSHOT: bool = False        # 스크린샷 캡처
FIRECRAWL_INCLUDE_TAGS: List[str]         # 포함할 HTML 태그
FIRECRAWL_EXCLUDE_TAGS: List[str]         # 제외할 HTML 태그  
FIRECRAWL_ACTIONS_ENABLED: bool = True    # 동적 액션 활성화
```

**기본 태그 설정:**
- **포함**: main, article, section, div, p, h1-h6, img, meta
- **제외**: script, style, nav, footer, aside, advertisement, banner

### 2. 크롤러 모듈 개선 (modules/crawler.py)

#### A. 향상된 Firecrawl 파라미터
```python
scrape_params = {
    'formats': ['html', 'markdown'],      # 다중 포맷 추출
    'onlyMainContent': False,             # 전체 페이지 포함
    'includeTags': config.FIRECRAWL_INCLUDE_TAGS,
    'excludeTags': config.FIRECRAWL_EXCLUDE_TAGS,
    'blockAds': True,                     # 광고 차단
    'removeBase64Images': False,          # 이미지 데이터 보존
}
```

#### B. 동적 콘텐츠 처리 액션
```python
actions = [
    {"type": "wait", "milliseconds": 2000},        # 초기 로딩 대기
    {"type": "scroll", "direction": "down", "amount": 3},  # 지연 로딩 트리거
    {"type": "wait", "milliseconds": 1000},        # 스크롤 후 대기
    {"type": "scrape"}                             # 최종 스크래핑
]
```

#### C. 콘텐츠 추출 우선순위
1. **rawHtml** (가장 완전한 콘텐츠)
2. **html** (표준 HTML)
3. **markdown → HTML 변환** (구조화된 변환)

#### D. 향상된 로깅
- 콘텐츠 소스 추적 (rawHtml/html/markdown_converted)
- 상세한 메타데이터 수집
- 응답 구조 디버깅 정보

## 🚀 기대 효과

### 1. 콘텐츠 추출량 증가
- **광고 차단**: 불필요한 노이즈 제거
- **동적 액션**: 지연 로딩 콘텐츠 포함
- **다중 포맷**: HTML + Markdown 병행 추출
- **전체 페이지**: 헤더, 메타 태그 포함

### 2. 품질 개선
- **구조화된 태그 필터링**: 의미 있는 콘텐츠 집중
- **스크롤 액션**: SPA 및 무한 스크롤 지원
- **에러 처리**: 상세한 실패 원인 분석

### 3. 디버깅 향상
- **콘텐츠 소스 추적**: 어떤 방식으로 추출되었는지 확인
- **응답 구조 분석**: 빈 콘텐츠 원인 파악
- **성능 메트릭**: 처리 시간 및 성공률 모니터링

## 🧪 테스트 방법

### 1. 개선 사항 테스트
```bash
cd product_batch_processor
python test_firecrawl_enhancement.py
```

### 2. 실제 URL 테스트
```bash
# 단일 URL 테스트
python main.py --url "https://example.com" --mode single --log-level DEBUG

# 배치 테스트
python main.py --file urls.txt --mode batch --workers 1 --log-level INFO
```

### 3. 로그 분석
```bash
# 실시간 로그 모니터링
tail -f data/logs/batch_processor.log | grep "firecrawl"

# 성공/실패 분석
grep "Enhanced Firecrawl request" data/logs/batch_processor.log
```

## 📈 성능 비교

**이전 설정:**
- 기본 HTML 포맷만 사용
- 정적 대기 시간만 설정
- 제한적인 오류 처리

**개선된 설정:**
- HTML + Markdown 다중 포맷
- 동적 액션 시퀀스 (스크롤, 대기)
- 광고 차단 및 태그 필터링
- 상세한 콘텐츠 소스 추적

## 🔧 추가 최적화 옵션

환경변수로 세밀한 조정 가능:
```bash
# .env 파일에 추가
FIRECRAWL_MOBILE=true          # 모바일 뷰로 크롤링
FIRECRAWL_WAIT_FOR=10000       # 더 긴 대기 시간
FIRECRAWL_ACTIONS_ENABLED=false # 액션 비활성화
```

## 🔍 문제 해결

### 1. 여전히 적은 콘텐츠가 추출되는 경우
- 로그에서 `content_source` 확인
- `FIRECRAWL_WAIT_FOR` 증가 (10000ms)
- 특정 사이트용 커스텀 액션 추가

### 2. 크롤링 속도가 느린 경우
- `FIRECRAWL_ACTIONS_ENABLED=false` 설정
- `FIRECRAWL_WAIT_FOR` 감소
- 배치 크기 축소

### 3. 특정 사이트 최적화
- 사이트별 `includeTags` 커스터마이징
- 모바일 뷰 활성화 고려
- 스크린샷 활성화로 시각적 확인

이제 Firecrawl playground와 유사한 수준의 콘텐츠 추출이 가능해야 합니다!