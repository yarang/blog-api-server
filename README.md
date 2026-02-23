# Blog API Server

FastAPI 기반 블로그 관리 API 서버입니다.

## 보안

모든 API 요청에는 `X-API-Key` 헤더가 필요합니다.

```bash
curl -H "X-API-Key: your_api_key" https://api.blog.fcoinfup.com/posts
```

## API 엔드포인트

### Posts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/posts` | 포스트 목록 조회 |
| GET | `/posts/{filename}` | 특정 포스트 조회 |
| POST | `/posts` | 새 포스트 생성 |
| PUT | `/posts/{filename}` | 포스트 수정 |
| DELETE | `/posts/{filename}` | 포스트 삭제 |

### Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/search?q=query` | 포스트 검색 |
| POST | `/search` | 포스트 검색 (Body) |

### Git

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/git/status` | Git 상태 확인 |
| POST | `/git/sync` | 원격 동기화 |
| POST | `/git/commit` | 커밋 및 푸시 |
| GET | `/git/commits` | 최근 커밋 목록 |

## 사용 예시

### 포스트 생성

```bash
curl -X POST https://api.blog.fcoinfup.com/posts \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "새 포스트 제목",
    "content": "# 내용\n\n포스트 내용입니다.",
    "tags": ["tag1", "tag2"],
    "categories": ["Development"],
    "draft": false
  }'
```

### 포스트 검색

```bash
curl -X GET "https://api.blog.fcoinfup.com/search?q=python" \
  -H "X-API-Key: your_api_key"
```

## 배포

```bash
# OCI 서버에서 실행
./deploy-api.sh
```

## API Key 관리

### 새 키 생성

```bash
python -c "import secrets; print(f'blog_{secrets.token_urlsafe(32)}')"
```

### 키 등록

`.env` 파일의 `BLOG_API_KEYS`에 추가:

```
BLOG_API_KEYS=blog_key1,blog_key2,blog_key3
```
