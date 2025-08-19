# 채용공고 자동생성 GenAI 서비스

LangGraph를 활용한 채용공고 자동생성 GenAI 서비스입니다.

## 🎯 프로젝트 목표

- 기업 정보 + 기존 채용공고 데이터 + 사용자 질의를 바탕으로 채용공고를 자동생성
- LLM Hallucination 및 민감정보 처리 문제 해결
- 응답 지연 최소화 및 사용자 경험 향상

## 🏗️ 아키텍처

```
사용자 입력 → 데이터 검색 → 구조화 → [필수필드 체크] → 
초안 생성 → 검증 에이전트들 → [민감성 체크] → 최종 출력
```

## 🚀 기술 스택

- **AI Framework**: LangGraph (StateGraph 기반 워크플로우)
- **Backend**: FastAPI (RESTful API)
- **Frontend**: Streamlit (사용자 인터페이스)
- **Database**: PostgreSQL + Redis (데이터 저장 및 캐싱)
- **Container**: Docker Compose (마이크로서비스 환경)

## 📦 서비스 구성

- **api**: FastAPI 백엔드 서비스 (포트 8000)
- **frontend**: Streamlit 프론트엔드 (포트 8501)
- **database**: PostgreSQL 데이터베이스 (포트 5432)
- **redis**: 캐싱 및 세션 관리 (포트 6379)
- **nginx**: 리버스 프록시 (포트 80)

## 🛠️ 개발 환경 설정

### 1. UV 패키지 매니저 설치

```bash
# Linux/Mac
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.sh | iex"
```

### 2. 환경변수 설정

```bash
cp .env.example .env
# .env 파일을 편집하여 실제 API 키 등을 입력하세요
```

### 3. 개발 환경 구성

```bash
# 프로젝트 의존성 동기화 (가상환경 자동 생성)
uv sync --dev

# 가상환경 활성화
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# 또는 uv run으로 직접 실행
uv run python -m src.api.main
```

### 4. Docker Compose 실행

```bash
# 전체 서비스 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 서비스 중지
docker-compose down
```

### 5. 개발 모드 실행

```bash
# API 서버 실행
uv run uvicorn src.api.main:app --reload

# Frontend 실행 (별도 터미널)
uv run streamlit run frontend/main.py
```

## 📋 주요 기능

### 1순위 기능 (MVP)
- ✅ DB 구축 및 검색 시스템
- ✅ Pydantic 템플릿 모델
- ✅ LangGraph 워크플로우
- ✅ Human-in-the-Loop 플로우
- ✅ 검증 에이전트 (초안검증 + 민감성검증)
- ✅ FastAPI + Streamlit UI/UX

### 2순위 기능 (성능 최적화)
- ⚡ 실시간 스트리밍 응답
- 🔄 Redis 프롬프트 캐싱
- 🛡️ Circuit Breaker & Fallback 전략

## 🎛️ 주요 엔드포인트

- `POST /api/v1/generate`: 채용공고 생성 요청
- `GET /api/v1/companies/{company_id}`: 기업 정보 조회
- `POST /api/v1/feedback`: Human-in-the-Loop 피드백 처리
- `GET /api/v1/status/{task_id}`: 생성 작업 상태 조회
- `GET /api/v1/stream`: 스트리밍 응답 엔드포인트

## 📁 프로젝트 구조

```
job-opening-autogen/
├── src/
│   ├── agents/          # LangGraph 검증 에이전트들
│   ├── components/      # 핵심 비즈니스 로직 컴포넌트
│   ├── models/          # Pydantic 데이터 모델
│   ├── database/        # DB 접근 및 검색 로직
│   ├── workflows/       # LangGraph 워크플로우 정의
│   ├── api/            # FastAPI 라우터 및 엔드포인트
│   └── utils/          # 공통 유틸리티
├── frontend/           # Streamlit 프론트엔드
├── config/            # 설정 파일 (환경변수, 프롬프트 템플릿)
├── data/             # 초기 데이터 및 샘플
├── tests/            # 테스트 코드
├── docker-compose.yml # 서비스 오케스트레이션
├── pyproject.toml    # 프로젝트 설정 및 의존성
└── uv.lock          # 의존성 잠금 파일
```

## 🔧 구성 파일

- `config/settings.py`: 중앙화된 설정 관리
- `config/nginx.conf`: Nginx 리버스 프록시 설정
- `docker-compose.yml`: Docker 서비스 정의
- `Dockerfile.api`: API 서비스 컨테이너 이미지
- `Dockerfile.frontend`: Frontend 서비스 컨테이너 이미지

## 🛡️ 보안 및 품질

- **LLM Hallucination 방지**: 참조 ID 추적 검증
- **민감정보 처리**: 차별적 표현 자동 감지
- **응답 지연 최소화**: 스트리밍 + 캐싱
- **시스템 안정성**: Primary/Secondary LLM 전환
- **보안**: 환경변수 분리, 입력 검증, 비루트 컨테이너 실행

## 📊 모니터링 및 로깅

- **로깅**: structlog를 활용한 구조화된 로깅
- **헬스체크**: 모든 서비스의 상태 모니터링
- **성능**: Redis 캐시 히트율 추적

## 🧪 테스트

```bash
# 단위 테스트
uv run pytest tests/unit/

# 통합 테스트
uv run pytest tests/integration/

# E2E 테스트
uv run pytest tests/e2e/

# 전체 테스트 (커버리지 포함)
uv run pytest --cov=src

# 코드 품질 검사
uv run ruff check src/
uv run black --check src/
uv run mypy src/
```

## 📝 개발 가이드

프로젝트 개발 규칙과 아키텍처 가이드는 `shrimp-rules.md` 파일을 참조하세요.

## 📜 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.