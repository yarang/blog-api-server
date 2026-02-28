# MCP Blog Client 아키텍처 문서

## 1. 개요

MCP Blog Client는 Claude Code에서 블로그를 관리하기 위한 MCP(Model Context Protocol) 클라이언트입니다. 원격 API Server를 통해 블로그 포스트를 작성, 수정, 삭제할 수 있습니다.

### 주요 기능
- 블로그 포스트 CRUD 작업
- Mermaid 다이어그램 렌더링
- API 서버 상태 모니터링
- 연결 풀링을 통한 효율적인 HTTP 통신

---

## 2. 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                    Claude Code (AI Agent)                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ MCP Protocol (stdio)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Blog Client                             │
│  ┌─────────────────┐     ┌─────────────────┐                   │
│  │  MCPLogger      │     │   BlogClient    │                   │
│  │  (Logging)      │     │  (HTTP Client)  │                   │
│  └─────────────────┘     └─────────────────┘                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    MCP Server                            │   │
│  │  - list_tools()                                          │   │
│  │  - call_tool()                                           │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ HTTP/REST
                                ▼
                    ┌─────────────────────────┐
                    │      Blog API Server    │
                    │   (blog.fcoinfup.com)   │
                    └─────────────────────────┘
```

---

## 3. 모듈 상세 설명

### 3.1 MCPLogger 클래스

MCP 클라이언트 전용 로깅 시스템입니다.

#### 기능
- 로그 레벨 제어 (환경 변수)
- JSON/텍스트 포맷 지원
- stderr 출력 (stdout은 MCP 통신용)

#### 환경 변수
| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `BLOG_LOG_LEVEL` | 로그 레벨 | `INFO` |
| `BLOG_LOG_FORMAT` | 로그 포맷 (text/json) | `text` |

---

### 3.2 BlogClient 클래스

Blog API HTTP 클라이언트입니다.

#### 기능
- 연결 풀링 (Keep-Alive)
- 타임아웃 처리 (30초)
- 자동 재연결
- 인증 헤더 관리

#### 연결 풀 설정
```python
httpx.Limits(
    max_keepalive_connections=10,  # 최대 Keep-Alive 연결
    max_connections=20,            # 최대 연결 수
    keepalive_expiry=30.0          # Keep-Alive 만료 시간
)
```

#### 주요 메서드

| 메서드 | 설명 |
|--------|------|
| `_get_client()` | HTTP 클라이언트 인스턴스 반환 (지연 초기화) |
| `close()` | 클라이언트 리소스 해제 |
| `request(method, path, data, params)` | HTTP 요청 실행 |

#### 요청 처리 흐름
1. URL 조립: `{base_url}{API_BASE_PATH}{path}`
2. HTTP 요청 실행
3. 상태 코드 확인 (401, 403, 4xx)
4. JSON 응답 반환

---

### 3.3 MCP Server 구현

MCP 프로토콜을 구현한 서버입니다.

#### 제공 도구 (Tools)

| 도구명 | 설명 | 필수 파라미터 |
|--------|------|---------------|
| `blog_create` | 블로그 포스트 생성 | `title`, `content` |
| `blog_list` | 포스트 목록 조회 | - |
| `blog_get` | 특정 포스트 조회 | `filename` |
| `blog_update` | 포스트 수정 | `filename`, `content` |
| `blog_delete` | 포스트 삭제 | `filename` |
| `blog_search` | 포스트 검색 | `query` |
| `blog_status` | API 서버 상태 확인 | - |
| `blog_mermaid_render` | Mermaid 다이어그램 렌더링 | `code` |
| `blog_mermaid_render_markdown` | 마크다운 내 Mermaid 변환 | `content` |
| `blog_mermaid_status` | Mermaid CLI 상태 확인 | - |

#### 도구 스키마 예시

**blog_create**
```json
{
  "type": "object",
  "properties": {
    "title": {"type": "string", "description": "포스트 제목"},
    "content": {"type": "string", "description": "포스트 내용 (Markdown)"},
    "tags": {"type": "array", "items": {"type": "string"}, "description": "태그 목록"},
    "categories": {"type": "array", "items": {"type": "string"}, "description": "카테고리 목록"},
    "draft": {"type": "boolean", "description": "초안 여부 (기본값: false)"}
  },
  "required": ["title", "content"]
}
```

---

## 4. 환경 변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `BLOG_API_URL` | API 서버 URL | `https://blog.fcoinfup.com` |
| `BLOG_API_BASE_PATH` | API 경로 접두사 | `/api` |
| `BLOG_API_KEY` | API 인증 키 | (내장 기본값) |
| `BLOG_LOG_LEVEL` | 로그 레벨 | `INFO` |
| `BLOG_LOG_FORMAT` | 로그 포맷 | `text` |

---

## 5. Claude Code 설정

### 5.1 설정 파일 위치

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

### 5.2 설정 예시

```json
{
  "mcpServers": {
    "blog": {
      "command": "python3",
      "args": ["/path/to/mcp_blog_client.py"],
      "env": {
        "BLOG_API_URL": "https://blog.fcoinfup.com",
        "BLOG_API_KEY": "your_api_key_here",
        "BLOG_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

---

## 6. 사용 예시

### Claude Code에서의 사용

```
User: 새 블로그 포스트를 작성해줘. 제목은 "Python Tips"이고 내용은...

Claude: 블로그 포스트를 생성하겠습니다.
[blog_create 도구 호출]

포스트가 성공적으로 생성되었습니다:
- 파일명: 2024-02-28-001-python-tips.md
- URL: https://blog.example.com/post/2024-02-28-001-python-tips
```

### 직접 실행 (테스트용)

```bash
# 환경 변수 설정
export BLOG_API_KEY=your_api_key

# 클라이언트 실행 (MCP 통신 시작)
python3 mcp_blog_client.py
```

---

## 7. API 매핑

| MCP 도구 | HTTP Method | API 경로 |
|----------|-------------|----------|
| `blog_create` | POST | `/api/posts` |
| `blog_list` | GET | `/api/posts` |
| `blog_get` | GET | `/api/posts/{filename}` |
| `blog_update` | PUT | `/api/posts/{filename}` |
| `blog_delete` | DELETE | `/api/posts/{filename}` |
| `blog_search` | GET | `/api/search` |
| `blog_status` | GET | `/api/status` |
| `blog_mermaid_render` | POST | `/api/mermaid/render` |
| `blog_mermaid_render_markdown` | POST | `/api/mermaid/render-markdown` |
| `blog_mermaid_status` | GET | `/api/mermaid/status` |

---

## 8. 에러 처리

### 클라이언트 측 에러

| 상황 | 처리 방식 |
|------|-----------|
| 인증 실패 (401) | `{"success": false, "error": "인증 실패: API Key 확인"}` |
| 권한 없음 (403) | `{"success": false, "error": "권한 없음: API Key 확인"}` |
| 타임아웃 | `{"success": false, "error": "API 타임아웃"}` |
| 네트워크 오류 | `{"success": false, "error": "{exception_message}"}` |

### 서버 측 에러

서버에서 반환되는 에러는 그대로 클라이언트에 전달됩니다.

---

## 9. 의존성

```
mcp>=1.0.0
httpx>=0.25.0
```

### 설치

```bash
pip install mcp httpx
```

또는

```bash
# mcp_client 디렉토리에서
./install.sh
```

---

## 10. 파일 구조

```
mcp_client/
├── mcp_blog_client.py    # 메인 클라이언트 코드
├── README.md             # 기본 문서
├── pyproject.toml        # 프로젝트 설정
├── install.sh            # 설치 스크립트
├── remote-install.sh     # 원격 설치 스크립트
└── uv.lock               # 의존성 락 파일
```

---

## 11. 로깅

### 로그 포맷

**텍스트 포맷**
```
2024-02-28 10:00:00 - mcp-blog-client - INFO - Message
```

**JSON 포맷**
```json
{
  "timestamp": "2024-02-28T10:00:00",
  "level": "INFO",
  "logger": "mcp-blog-client",
  "message": "Message",
  "module": "mcp_blog_client",
  "function": "call_tool",
  "line": 313
}
```

### 로그 위치

모든 로그는 stderr로 출력되며, stdout은 MCP 프로토콜 통신을 위해 예약되어 있습니다.

---

## 12. 보안 고려사항

1. **API Key 보호**
   - API Key는 환경 변수로 관리
   - 코드에 하드코딩 금지
   - 로그에서 마스킹 처리

2. **HTTPS 사용**
   - 모든 통신은 HTTPS로 암호화
   - 인증서 검증 활성화

3. **최소 권한 원칙**
   - 필요한 권한만 가진 API Key 사용
   - 읽기 전용 작업에는 읽기 전용 키 사용
