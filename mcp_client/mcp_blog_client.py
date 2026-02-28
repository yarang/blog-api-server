#!/usr/bin/env python3
"""
Blog MCP Client - Remote Blog Management

Claude Code에서 블로그를 관리하기 위한 MCP 클라이언트입니다.
API Server를 통해 원격으로 블로그 포스트를 작성/수정/삭제할 수 있습니다.

설치:
  pip install mcp httpx

사용법:
  1. API Key를 환경 변수에 설정:
     export BLOG_API_KEY=your_api_key

  2. Claude Code 설정 파일에 추가:
     {
       "mcpServers": {
         "blog": {
           "command": "python3",
           "args": ["/path/to/mcp_blog_client.py"],
           "env": {
             "BLOG_API_URL": "https://blog.fcoinfup.com",
             "BLOG_API_KEY": "your_api_key"
           }
         }
       }
     }

환경 변수:
  BLOG_LOG_LEVEL: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  BLOG_LOG_FORMAT: 로그 포맷 (text, json)
"""

import os
import sys
import json
import httpx
import logging
from typing import List, Dict, Optional
from datetime import datetime

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ============================================================
# Logging Setup
# ============================================================

class MCPLogger:
    """간단한 MCP 클라이언트용 로거"""

    def __init__(self):
        self.level = os.getenv("BLOG_LOG_LEVEL", "INFO").upper()
        self.format_type = os.getenv("BLOG_LOG_FORMAT", "text").lower()
        self._setup_logging()

    def _setup_logging(self):
        """로깅 설정"""
        level = getattr(logging, self.level, logging.INFO)

        # 핸들러 설정
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)

        if self.format_type == "json":
            import json as json_mod
            class JSONFormatter(logging.Formatter):
                def format(self, record):
                    return json_mod.dumps({
                        "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                        "level": record.levelname,
                        "logger": "mcp-blog-client",
                        "message": record.getMessage(),
                        "module": record.module,
                        "function": record.funcName,
                        "line": record.lineno,
                    }, ensure_ascii=False)
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

        handler.setFormatter(formatter)

        # 루트 로거 설정
        root = logging.getLogger()
        root.setLevel(level)
        root.handlers.clear()
        root.addHandler(handler)

    def get_logger(self, name: str) -> logging.Logger:
        return logging.getLogger(name)


# 로깅 초기화
_mcp_logger_setup = MCPLogger()
logger = _mcp_logger_setup.get_logger(__name__)

# ============================================================
# Configuration
# ============================================================

API_URL = os.getenv("BLOG_API_URL", "https://blog.fcoinfup.com")
API_BASE_PATH = os.getenv("BLOG_API_BASE_PATH", "/api")  # API 경로 접두사
API_KEY = os.getenv("BLOG_API_KEY", "blog_0a6PyEL4S6lhoyZCMTbEOdUAJZpGsr2wAscfAWr2vZg")  # 기본 API 키

# ============================================================
# API Client
# ============================================================

class BlogClient:
    """Blog API HTTP 클라이언트 (연결 풀링 지원)"""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
        logger.info(f"BlogClient initialized", extra={"api_url": base_url})

    async def _get_client(self) -> httpx.AsyncClient:
        """연결 풀링을 위한 HTTP 클라이언트 가져오기"""
        if self._client is None or self._client.is_closed:
            # 연결 풀 설정 최적화
            limits = httpx.Limits(
                max_keepalive_connections=10,
                max_connections=20,
                keepalive_expiry=30.0
            )
            self._client = httpx.AsyncClient(
                timeout=30.0,
                limits=limits,
                http2=False  # API 서버가 HTTP/2를 지원하지 않을 수 있음
            )
        return self._client

    async def close(self):
        """클라이언트 리소스 해제"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def request(self, method: str, path: str, data: Dict = None, params: Dict = None) -> Dict:
        url = f"{self.base_url}{API_BASE_PATH}{path}"
        client = await self._get_client()

        logger.debug(f"API request: {method} {url}", extra={
            "method": method,
            "path": path,
            "has_data": data is not None
        })

        try:
            if method == "GET":
                resp = await client.get(url, headers=self.headers, params=params)
            elif method == "POST":
                resp = await client.post(url, headers=self.headers, json=data)
            elif method == "PUT":
                resp = await client.put(url, headers=self.headers, json=data)
            elif method == "DELETE":
                resp = await client.delete(url, headers=self.headers, params=params)
            else:
                return {"success": False, "error": f"Unknown method: {method}"}

            if resp.status_code == 401:
                logger.error(f"Authentication failed: {method} {path}")
                return {"success": False, "error": "인증 실패: API Key 확인"}
            if resp.status_code == 403:
                logger.error(f"Authorization failed: {method} {path}")
                return {"success": False, "error": "권한 없음: API Key 확인"}

            if resp.status_code >= 400:
                logger.warning(f"API error response: {resp.status_code}", extra={
                    "status_code": resp.status_code,
                    "path": path
                })

            result = resp.json()
            logger.debug(f"API response: {method} {path} -> {resp.status_code}", extra={
                "status_code": resp.status_code,
                "success": result.get("success", True)
            })
            return result

        except httpx.TimeoutException:
            logger.error(f"API timeout: {method} {url}")
            return {"success": False, "error": "API 타임아웃"}
        except Exception as e:
            logger.error(f"API request error: {method} {url}", extra={"error": str(e)})
            return {"success": False, "error": str(e)}


# ============================================================
# MCP Server
# ============================================================

client = BlogClient(API_URL, API_KEY)
server = Server("blog-client")

TOOLS = [
    Tool(
        name="blog_create",
        description="블로그 포스트 생성. 제목과 내용(Markdown)을 입력하면 포스트가 생성되고 Git에 커밋/푸시됩니다.",
        inputSchema={
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
    ),
    Tool(
        name="blog_list",
        description="블로그 포스트 목록 조회",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "number", "description": "조회할 개수 (기본값: 20)"},
                "offset": {"type": "number", "description": "시작 위치 (기본값: 0)"}
            }
        }
    ),
    Tool(
        name="blog_get",
        description="특정 포스트 내용 조회",
        inputSchema={
            "type": "object",
            "properties": {"filename": {"type": "string", "description": "파일명"}},
            "required": ["filename"]
        }
    ),
    Tool(
        name="blog_update",
        description="포스트 내용 수정",
        inputSchema={
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "파일명"},
                "content": {"type": "string", "description": "수정할 내용 (전체)"}
            },
            "required": ["filename", "content"]
        }
    ),
    Tool(
        name="blog_delete",
        description="포스트 삭제",
        inputSchema={
            "type": "object",
            "properties": {"filename": {"type": "string", "description": "파일명"}},
            "required": ["filename"]
        }
    ),
    Tool(
        name="blog_search",
        description="포스트 검색",
        inputSchema={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "검색어"}},
            "required": ["query"]
        }
    ),
    Tool(
        name="blog_status",
        description="API 서버 및 Git 상태 확인",
        inputSchema={"type": "object", "properties": {}}
    ),
    Tool(
        name="blog_mermaid_render",
        description="Mermaid 다이어그램을 SVG로 렌더링합니다. Mermaid CLI가 설치되어 있어야 합니다.",
        inputSchema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Mermaid 다이어그램 코드"},
                "filename": {"type": "string", "description": "저장할 파일명 (선택)"}
            },
            "required": ["code"]
        }
    ),
    Tool(
        name="blog_mermaid_render_markdown",
        description="마크다운 내의 Mermaid 코드블록을 SVG로 변환하고 이미지 참조로 대체합니다.",
        inputSchema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "마크다운 콘텐츠"}
            },
            "required": ["content"]
        }
    ),
    Tool(
        name="blog_mermaid_status",
        description="Mermaid CLI 설치 상태 확인",
        inputSchema={"type": "object", "properties": {}}
    ),
]


@server.list_tools()
async def list_tools() -> List[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: Dict) -> List[TextContent]:
    logger.info(f"MCP tool called: {name}", extra={"tool": name, "arguments_keys": list(arguments.keys())})

    if name == "blog_create":
        result = await client.request("POST", "/posts", data={
            "title": arguments["title"],
            "content": arguments["content"],
            "tags": arguments.get("tags", []),
            "categories": arguments.get("categories", ["Development"]),
            "draft": arguments.get("draft", False),
            "auto_push": True
        })
        if result.get("success"):
            logger.info(f"Post created: {result.get('filename')}", extra={"post_filename": result.get("filename")})

    elif name == "blog_list":
        result = await client.request("GET", "/posts", params={
            "limit": arguments.get("limit", 20),
            "offset": arguments.get("offset", 0)
        })

    elif name == "blog_get":
        result = await client.request("GET", f"/posts/{arguments['filename']}")

    elif name == "blog_update":
        result = await client.request("PUT", f"/posts/{arguments['filename']}", data={
            "content": arguments["content"],
            "auto_push": True
        })

    elif name == "blog_delete":
        result = await client.request("DELETE", f"/posts/{arguments['filename']}")

    elif name == "blog_search":
        result = await client.request("GET", "/search", params={"q": arguments["query"]})

    elif name == "blog_status":
        result = await client.request("GET", "/status")

    elif name == "blog_mermaid_render":
        result = await client.request("POST", "/mermaid/render", data={
            "code": arguments["code"],
            "filename": arguments.get("filename")
        })

    elif name == "blog_mermaid_render_markdown":
        result = await client.request("POST", "/mermaid/render-markdown", data={
            "content": arguments["content"],
            "output_filename": arguments.get("output_filename")
        })

    elif name == "blog_mermaid_status":
        result = await client.request("GET", "/mermaid/status")

    else:
        result = {"success": False, "error": f"알 수 없는 도구: {name}"}

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def main():
    if not API_KEY:
        logger.critical("BLOG_API_KEY 환경 변수가 필요합니다")
        sys.stderr.write("ERROR: BLOG_API_KEY 환경 변수가 필요합니다\n")
        return

    logger.info("MCP Blog Client starting", extra={
        "api_url": API_URL,
        "log_level": _mcp_logger_setup.level
    })

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        # 클라이언트 리소스 해제
        await client.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
