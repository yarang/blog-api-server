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

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | 서버 상태 |
| GET | `/posts` | 포스트 목록 |
| POST | `/posts` | 포스트 생성 |
| GET | `/posts/{filename}` | 포스트 조회 |
| PUT | `/posts/{filename}` | 포스트 수정 |
| DELETE | `/posts/{filename}` | 포스트 삭제 |
| POST | `/translate` | LLM 번역 |

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
