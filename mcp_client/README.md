# Blog MCP Client

Claude Code에서 블로그를 관리하기 위한 MCP 클라이언트입니다.

## 다른 Claude Code에서 사용하기 (원격 설치)

한 줄로 설치:

```bash
curl -fsSL https://raw.githubusercontent.com/yarang/blogs/main/mcp_client/remote-install.sh | bash
```

또는 설치 경로 지정:

```bash
curl -fsSL https://raw.githubusercontent.com/yarang/blogs/main/mcp_client/remote-install.sh | bash -s -- ~/.blog-mcp
```

설치 후 프로젝트에 `.mcp.json` 복사:

```bash
cp ~/.blog-mcp-client/.mcp.json /your/project/.mcp.json
```

## 저장소에서 설치 (개발자)

```bash
git clone https://github.com/yarang/blogs.git
cd blogs/mcp_client
./install.sh
```

## 수동 설정

### 1. 클라이언트 다운로드

```bash
mkdir -p ~/.blog-mcp-client
cd ~/.blog-mcp-client

# 클라이언트 스크립트 다운로드
curl -O https://raw.githubusercontent.com/yarang/blogs/main/mcp_client/mcp_blog_client.py

# uv로 의존성 설치
uv venv
uv pip install mcp httpx
```

### 2. 프로젝트 .mcp.json 설정

프로젝트 루트에 `.mcp.json` 생성:

```json
{
  "mcpServers": {
    "blog": {
      "command": "/Users/사용자/.blog-mcp-client/.venv/bin/python",
      "args": ["/Users/사용자/.blog-mcp-client/mcp_blog_client.py"],
      "env": {
        "BLOG_API_URL": "http://130.162.133.47",
        "BLOG_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

### 3. Claude Code 설정

`~/.claude/settings.json`에 추가:

```json
{
  "enableAllProjectMcpServers": true
}
```

## API Key 발급

블로그 관리자(yarang)에게 API Key를 요청하세요.

## 사용 가능한 도구

| 도구 | 설명 |
|------|------|
| `blog_create` | 새 포스트 작성 (제목, 내용 필수) |
| `blog_list` | 포스트 목록 조회 |
| `blog_get` | 특정 포스트 조회 (파일명 필요) |
| `blog_update` | 포스트 수정 (파일명, 내용 필요) |
| `blog_delete` | 포스트 삭제 (파일명 필요) |
| `blog_search` | 포스트 검색 (검색어 필요) |
| `blog_status` | 서버 상태 확인 |

## 사용 예시

```
블로그에 새 포스트 작성해줘.
제목: "Python으로 MCP 서버 만들기"
내용: MCP 프로토콜 소개와 예제 코드를 포함해.
태그: Python, MCP, Tutorial
```

```
블로그 포스트 목록 보여줘
```

```
"Python" 키워드로 블로그 검색해줘
```

## 파일 구조

```
mcp_client/
├── mcp_blog_client.py   # MCP 클라이언트
├── install.sh           # 로컬 설치 스크립트
├── remote-install.sh    # 원격 설치 스크립트
├── pyproject.toml       # 패키지 설정
└── README.md            # 이 파일
```
