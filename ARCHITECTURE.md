# Blog API Server 아키텍처 문서

## 1. 프로젝트 개요

Blog API Server는 Git 기반으로 블로그 포스트를 관리하는 RESTful API 서버입니다. Hugo Stack 테마를 사용하는 블로그를 원격에서 관리할 수 있으며, 다국어(한국어/영어) 지원과 AI 기반 번역 기능을 제공합니다.

### 주요 기능
- 블로그 포스트 CRUD (생성, 조회, 수정, 삭제)
- Git 기반 버전 관리 및 자동 동기화
- 다국어 지원 (한국어/영어)
- LLM 기반 콘텐츠 번역
- Mermaid 다이어그램 렌더링
- API 모니터링 및 메트릭 수집

---

## 2. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client (MCP/AI Agent)                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI Server                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   main.py   │  │ middleware  │  │      auth.py            │  │
│  │ (Endpoints) │  │ (Monitoring)│  │   (API Key Auth)        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ blog_manager  │     │   translator    │     │  git_handler    │
│ (Post CRUD)   │     │ (LLM Translation)│    │ (Git Operations)│
└───────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                ▼
                    ┌─────────────────────────┐
                    │     Git Repository      │
                    │  (Hugo Blog Content)    │
                    └─────────────────────────┘
```

---

## 3. 모듈 상세 설명

### 3.1 main.py - 메인 애플리케이션

FastAPI 애플리케이션의 진입점입니다.

#### 주요 구성요소

| 구성요소 | 설명 |
|---------|------|
| `lifespan` | 앱 시작/종료 시 초기화 및 정리 작업 |
| `PostCreate` | 포스트 생성 요청 모델 |
| `PostUpdate` | 포스트 수정 요청 모델 |
| `TranslateRequest` | 번역 요청 모델 |

#### API 엔드포인트

| Method | Path | 설명 | 인증 |
|--------|------|------|------|
| GET | `/` | API 정보 | 불필요 |
| GET | `/health` | 서버 상태 확인 | 불필요 |
| GET | `/metrics` | 서버 메트릭 조회 | 필요 |
| POST | `/metrics/reset` | 메트릭 초기화 | 필요 |
| GET | `/posts` | 포스트 목록 조회 | 필요 |
| GET | `/posts/{filename}` | 포스트 상세 조회 | 필요 |
| POST | `/posts` | 포스트 생성 | 필요 |
| PUT | `/posts/{filename}` | 포스트 수정 | 필요 |
| DELETE | `/posts/{filename}` | 포스트 삭제 | 필요 |
| GET | `/search` | 포스트 검색 | 필요 |
| POST | `/sync` | Git 원격 동기화 | 필요 |
| GET | `/status` | Git 상태 확인 | 필요 |
| POST | `/translate` | 콘텐츠 번역 | 필요 |
| POST | `/translate/sync` | 번역 동기화 | 필요 |
| GET | `/translate/status` | 번역 상태 확인 | 필요 |
| POST | `/mermaid/render` | Mermaid 렌더링 | 필요 |
| POST | `/mermaid/render-markdown` | 마크다운 내 Mermaid 변환 | 필요 |
| GET | `/mermaid/status` | Mermaid CLI 상태 | 필요 |

---

### 3.2 auth.py - 인증 모듈

API Key 기반 인증을 제공합니다.

#### 주요 함수

| 함수 | 설명 |
|------|------|
| `get_valid_api_keys()` | 환경 변수에서 유효한 API 키 목록 로드 |
| `generate_api_key()` | 새 API 키 생성 (`blog_` 접두사 + 32바이트 토큰) |
| `verify_api_key()` | API 키 검증 (FastAPI Dependency) |
| `optional_api_key()` | 선택적 인증 (공개 읽기 허용) |

#### 환경 변수
- `BLOG_API_KEYS`: 쉼표로 구분된 API 키 목록

---

### 3.3 blog_manager.py - 블로그 관리 모듈

Git 기반 블로그 포스트 관리의 핵심 모듈입니다.

#### 클래스 구조

```
BlogManager
├── GitManager (내부 클래스)
│   ├── ensure_repo()
│   ├── clone()
│   ├── pull()
│   └── commit_and_push()
├── create_post()
├── list_posts()
├── get_post()
├── update_post()
├── delete_post()
├── search_posts()
├── get_translation_status()
└── sync_translations()
```

#### 디렉토리 구조 (Hugo Stack 테마)

```
blog-repo/
├── content/
│   ├── post/           # 한국어 포스트 (기본 언어)
│   │   └── YYYY-MM-DD-NNN-slug.md
│   └── en/
│       └── post/       # 영어 포스트
│           └── YYYY-MM-DD-NNN-slug.md
└── static/
    └── images/
```

#### 포스트 파일명 생성 규칙
- 형식: `YYYY-MM-DD-NNN-slug.md`
- 예: `2024-02-28-001-hello-world.md`

#### Front Matter 형식 (TOML)

```toml
+++
title = "포스트 제목"
date = 2024-02-28T10:00:00+09:00
draft = false
tags = ["tag1", "tag2"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

포스트 내용...
```

---

### 3.4 git_handler.py - Git 작업 핸들러

Git 명령어를 안전하게 실행하는 모듈입니다.

#### 주요 메서드

| 메서드 | 설명 |
|--------|------|
| `_run_git(*args)` | Git 명령어 실행 (타임아웃 60초) |
| `get_status()` | Git 상태 확인 |
| `sync_from_remote()` | 원격 저장소에서 동기화 (fetch + pull) |
| `commit_and_push()` | 변경사항 커밋 및 푸시 |
| `get_recent_commits()` | 최근 커밋 목록 조회 |

#### 특징
- 모든 Git 작업은 `git_lock`을 통해 동기화
- 상세한 로깅 (명령어, 실행 시간, 결과)
- 타임아웃 처리 (60초)

---

### 3.5 translator.py - 번역 모듈

LLM 기반 번역 및 Mermaid 렌더링을 제공합니다.

#### Translator 클래스

| 메서드 | 설명 |
|--------|------|
| `translate()` | 마크다운 콘텐츠 번역 |
| `translate_title_only()` | 제목만 번역 |
| `_extract_front_matter()` | Front matter와 본문 분리 |
| `_parse_front_matter()` | TOML Front matter 파싱 |

#### 지원 API
- **ZAI API** (우선): OpenAI 호환 엔드포인트
- **Anthropic API**: Claude 모델 사용

#### 환경 변수
- `ZAI_API_KEY`: ZAI API 키
- `ZAI_BASE_URL`: ZAI API 엔드포인트
- `ZAI_MODEL`: 사용할 모델 (기본: gpt-4o-mini)
- `ANTHROPIC_API_KEY`: Anthropic API 키

#### MermaidRenderer 클래스

| 메서드 | 설명 |
|--------|------|
| `render()` | Mermaid 코드를 SVG로 렌더링 |
| `render_from_markdown()` | 마크다운 내 Mermaid 블록 변환 |

#### 의존성
- Mermaid CLI: `npm install -g @mermaid-js/mermaid-cli`

---

### 3.6 middleware.py - 모니터링 미들웨어

API 요청/응답 모니터링을 제공합니다.

#### 기능
- 요청/응답 시간 측정
- UUID 기반 요청 추적
- 느린 요청 감지 (기본 1초 이상)
- 에러 추적
- 민감 정보 마스킹

#### 통계 수집
- `total_requests`: 총 요청 수
- `error_count`: 에러 수
- `slow_request_count`: 느린 요청 수
- `error_rate_percent`: 에러율
- `slow_request_rate_percent`: 느린 요청 비율

#### 환경 변수
- `SLOW_REQUEST_THRESHOLD`: 느린 요청 임계값 (ms, 기본 1000)
- `VERY_SLOW_THRESHOLD`: 매우 느린 요청 임계값 (ms, 기본 3000)
- `MAX_BODY_LOG_LENGTH`: 바디 로그 최대 길이 (기본 1000)

---

### 3.7 logger_config.py - 로깅 설정

구조화된 로깅 시스템을 제공합니다.

#### 기능
- JSON/텍스트 포맷 지원
- 컬러 콘솔 출력
- 파일 로깅 지원
- 타임존 정보 포함

#### 환경 변수
- `LOG_LEVEL`: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `LOG_FORMAT`: 로그 포맷 (text, json)
- `LOG_FILE`: 로그 파일 경로

#### 사용 예시

```python
from logger_config import get_logger, log_with_context

logger = get_logger(__name__)
logger.info("Message")

# 컨텍스트와 함께 로깅
log_with_context(logger, "INFO", "Post created",
                 post_id="123", title="Test Post")
```

---

### 3.8 file_lock.py - 파일 기반 락

멀티프로세스 환경에서 안전한 상호 배제를 제공합니다.

#### 특징
- `fcntl.flock()` 기반 파일 락
- 타임아웃 지원 (기본 60초)
- 컨텍스트 매니저 지원

#### 사용 예시

```python
from file_lock import git_lock

with git_lock():
    # Git 작업 (임계 영역)
    pass
```

---

## 4. 환경 변수 요약

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `BLOG_API_KEYS` | API 키 목록 (쉼표 구분) | - |
| `BLOG_REPO_URL` | Git 저장소 URL | `https://github.com/yarang/blogs.git` |
| `BLOG_REPO_PATH` | 로컬 저장소 경로 | `/var/www/blog-repo` |
| `PORT` | 서버 포트 | `8000` |
| `LOG_LEVEL` | 로그 레벨 | `INFO` |
| `LOG_FORMAT` | 로그 포맷 (text/json) | `text` |
| `LOG_FILE` | 로그 파일 경로 | - |
| `ZAI_API_KEY` | ZAI API 키 | - |
| `ZAI_BASE_URL` | ZAI API 엔드포인트 | `https://api.zukijourney.com/v1` |
| `ZAI_MODEL` | ZAI 모델명 | `gpt-4o-mini` |
| `ANTHROPIC_API_KEY` | Anthropic API 키 | - |
| `MERMAID_CLI` | Mermaid CLI 경로 | `mmdc` |
| `SLOW_REQUEST_THRESHOLD` | 느린 요청 임계값 (ms) | `1000` |
| `VERY_SLOW_THRESHOLD` | 매우 느린 요청 임계값 (ms) | `3000` |

---

## 5. 의존성

```
fastapi
uvicorn
httpx
pydantic
python-dotenv
```

---

## 6. 실행 방법

```bash
# 환경 변수 설정
export BLOG_API_KEYS=your_api_key
export BLOG_REPO_PATH=/path/to/blog/repo

# 서버 실행
python main.py

# 또는 uvicorn으로 실행
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 7. API 사용 예시

### 포스트 생성

```bash
curl -X POST https://blog.example.com/api/posts \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Hello World",
    "content": "# Hello\n\nThis is my first post.",
    "tags": ["hello", "first"],
    "categories": ["Development"],
    "draft": false,
    "language": "ko"
  }'
```

### 포스트 목록 조회

```bash
curl https://blog.example.com/api/posts?limit=10&offset=0 \
  -H "X-API-Key: your_api_key"
```

### 번역

```bash
curl -X POST https://blog.example.com/api/translate \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "# 안녕하세요\n\n이것은 테스트입니다.",
    "source": "ko",
    "target": "en"
  }'
```
