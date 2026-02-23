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
             "BLOG_API_URL": "http://130.162.133.47",
             "BLOG_API_KEY": "your_api_key"
           }
         }
       }
     }
"""

import os
import json
import httpx
from typing import List, Dict

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ============================================================
# Configuration
# ============================================================

API_URL = os.getenv("BLOG_API_URL", "http://130.162.133.47")
API_KEY = os.getenv("BLOG_API_KEY", "")

# ============================================================
# API Client
# ============================================================

class BlogClient:
    """Blog API HTTP 클라이언트"""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }

    async def request(self, method: str, path: str, data: Dict = None, params: Dict = None) -> Dict:
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient(timeout=30.0) as client:
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
                    return {"success": False, "error": "인증 실패: API Key 확인"}
                if resp.status_code == 403:
                    return {"success": False, "error": "권한 없음: API Key 확인"}

                return resp.json()

            except httpx.TimeoutException:
                return {"success": False, "error": "API 타임아웃"}
            except Exception as e:
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
]


@server.list_tools()
async def list_tools() -> List[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: Dict) -> List[TextContent]:
    if name == "blog_create":
        result = await client.request("POST", "/posts", data={
            "title": arguments["title"],
            "content": arguments["content"],
            "tags": arguments.get("tags", []),
            "categories": arguments.get("categories", ["Development"]),
            "draft": arguments.get("draft", False),
            "auto_push": True
        })

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

    else:
        result = {"success": False, "error": f"알 수 없는 도구: {name}"}

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def main():
    if not API_KEY:
        import sys
        print("ERROR: BLOG_API_KEY 환경 변수가 필요합니다", file=sys.stderr)
        return

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
