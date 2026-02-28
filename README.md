# Blog API Server

Hugo 블로그 관리를 위한 API 서버와 MCP 클라이언트입니다.

## 저장소 구조

| 저장소 | 내용 |
|--------|------|
| [yarang/blogs](https://github.com/yarang/blogs) | Hugo 블로그 콘텐츠 |
| [yarang/blog-api-server](https://github.com/yarang/blog-api-server) | API 서버 + MCP 클라이언트 (이 저장소) |

## 구성

```
blog-api-server/
├── main.py               # FastAPI 엔드포인트
├── blog_manager.py       # 블로그 + Git 관리
├── translator.py         # LLM 번역 (Claude API)
├── auth.py               # API Key 인증
├── git_handler.py        # Git 작업
├── mcp_client/           # MCP 클라이언트
│   ├── mcp_blog_client.py
│   ├── install.sh
│   └── remote-install.sh
└── requirements.txt
```

## MCP 클라이언트 설치

### 방법 1: 저장소 클론

```bash
git clone https://github.com/yarang/blog-api-server.git
cd blog-api-server/mcp_client
./install.sh
```

### 방법 2: 원격 설치

```bash
curl -fsSL https://raw.githubusercontent.com/yarang/blog-api-server/main/mcp_client/remote-install.sh | bash
```

## API 서버 배포

```bash
# OCI 서버에서
git clone https://github.com/yarang/blog-api-server.git
cd blog-api-server
./deploy-api.sh
```

## API 엔드포인트

### 시스템
| Method | Endpoint | Description | 인증 |
|--------|----------|-------------|------|
| GET | `/` | API 정보 | 불필요 |
| GET | `/health` | 서버 상태 | 불필요 |
| GET | `/metrics` | 서버 메트릭 조회 | 필요 |
| POST | `/metrics/reset` | 메트릭 초기화 | 필요 |

### 포스트 관리
| Method | Endpoint | Description | 인증 |
|--------|----------|-------------|------|
| GET | `/posts` | 포스트 목록 | 필요 |
| POST | `/posts` | 포스트 생성 | 필요 |
| GET | `/posts/{filename}` | 포스트 조회 | 필요 |
| PUT | `/posts/{filename}` | 포스트 수정 | 필요 |
| DELETE | `/posts/{filename}` | 포스트 삭제 | 필요 |
| GET | `/search` | 포스트 검색 | 필요 |

### Git 관리
| Method | Endpoint | Description | 인증 |
|--------|----------|-------------|------|
| POST | `/sync` | Git 원격 동기화 | 필요 |
| GET | `/status` | Git 상태 확인 | 필요 |

### 번역
| Method | Endpoint | Description | 인증 |
|--------|----------|-------------|------|
| POST | `/translate` | LLM 기반 번역 | 필요 |
| POST | `/translate/sync` | 번역 동기화 | 필요 |
| GET | `/translate/status` | 번역 상태 확인 | 필요 |

### Mermaid 다이어그램
| Method | Endpoint | Description | 인증 |
|--------|----------|-------------|------|
| POST | `/mermaid/render` | 다이어그램 렌더링 | 필요 |
| POST | `/mermaid/render-markdown` | 마크다운 내 Mermaid 변환 | 필요 |
| GET | `/mermaid/status` | Mermaid CLI 상태 | 필요 |

## 사용 예시

### 포스트 생성

```bash
curl -X POST http://130.162.133.47:8000/posts \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "새 포스트 제목",
    "content": "# 내용\n\n포스트 내용입니다.",
    "tags": ["tag1", "tag2"],
    "categories": ["Development"],
    "language": "ko"
  }'
```

### 포스트 목록 조회

```bash
curl "http://130.162.133.47:8000/posts?limit=10&offset=0&language=ko" \
  -H "X-API-Key: your_api_key"
```

### 포스트 검색

```bash
curl "http://130.162.133.47:8000/search?q=FastAPI" \
  -H "X-API-Key: your_api_key"
```

### Git 동기화

```bash
curl -X POST http://130.162.133.47:8000/sync \
  -H "X-API-Key: your_api_key"
```

### 콘텐츠 번역

```bash
curl -X POST http://130.162.133.47:8000/translate \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "# 안녕하세요\n\n이것은 테스트입니다.",
    "source": "ko",
    "target": "en"
  }'
```

### 번역 동기화

```bash
curl -X POST http://130.162.133.47:8000/translate/sync \
  -H "X-API-Key: your_api_key"
```

### 서버 메트릭 조회

```bash
curl http://130.162.133.47:8000/metrics \
  -H "X-API-Key: your_api_key"
```

## 환경 변수

```bash
# API 서버 (.env)
BLOG_API_KEYS=blog_xxx,blog_yyy
BLOG_REPO_URL=https://github.com/yarang/blogs.git
BLOG_REPO_PATH=/var/www/blog-repo
ANTHROPIC_API_KEY=sk-ant-xxx

# MCP 클라이언트
BLOG_API_URL=http://130.162.133.47
BLOG_API_KEY=blog_xxx
BLOG_LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR, CRITICAL
BLOG_LOG_FORMAT=text          # text, json
```

## API Key 관리

### 새 키 생성

```bash
python -c "import secrets; print(f'blog_{secrets.token_urlsafe(32)}')"
```

### 서버에서 키 관리

```bash
ssh ubuntu@130.162.133.47 "/var/www/blog-api/manage-keys.sh"
```

## 로깅

API 서버와 MCP 클라이언트는 구조화된 로깅 시스템을 제공합니다.

### 로그 레벨

- `DEBUG`: 상세한 디버깅 정보
- `INFO`: 일반적인 정보 (기본값)
- `WARNING`: 경고 메시지
- `ERROR`: 에러 메시지
- `CRITICAL`: 심각한 에러

### API 서버 로그 설정

```bash
# .env 파일
LOG_LEVEL=DEBUG           # 로그 레벨
LOG_FORMAT=json           # 포맷: text, json
LOG_FILE=/var/log/blog-api.log  # 로그 파일 (선택)
```

### MCP 클라이언트 로그 설정

```bash
# 환경 변수
export BLOG_LOG_LEVEL=DEBUG
export BLOG_LOG_FORMAT=json
```

### 로그 예시

**텍스트 포맷:**
```
2026-02-24 10:30:45 - main - INFO - Blog API Server starting...
2026-02-24 10:30:46 - main - INFO - Post created: 2026-02-24-001-test-post.md
```

**JSON 포맷:**
```json
{"timestamp": "2026-02-24T10:30:45", "level": "INFO", "logger": "main", "message": "Post created", "filename": "2026-02-24-001-test-post.md"}
```

## Mermaid 다이어그램 렌더링

Mermaid 코드를 SVG 이미지로 변환합니다.

### 설치

```bash
npm install -g @mermaid-js/mermaid-cli
```

### 환경 변수

```bash
# .env 파일
MERMAID_CLI=mmdc              # Mermaid CLI 경로 (기본값)
```

### 사용 예시

**다이어그램 렌더링:**
```bash
curl -X POST http://130.162.133.47:8000/mermaid/render \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "graph TD\n    A[Start] --> B[End]"
  }'
```

**마크다운 내 Mermaid 렌더링:**
```bash
curl -X POST http://130.162.133.47:8000/mermaid/render-markdown \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "# My Post\n\n```mermaid\ngraph TD\n    A[Start] --> B[End]\n```\n\nSome text."
  }'
```
