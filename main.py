"""
Blog API Server - Block 1: 독립 Git 관리

다른 모듈과 Git을 통해서만 동기화됩니다.
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from auth import verify_api_key
from blog_manager import blog_manager
from git_handler import git_handler
from translator import translator

# 로깅
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()


# ============================================================
# Lifespan
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Blog API Server starting...")
    logger.info(f"Repo: {blog_manager.git.repo_path}")

    # 초기 동기화
    blog_manager.git.pull()

    yield

    logger.info("Blog API Server shutting down...")


# ============================================================
# FastAPI App
# ============================================================

app = FastAPI(
    title="Blog API",
    description="독립 Git 기반 블로그 관리 API",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Request Models
# ============================================================

class PostCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    tags: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=lambda: ["Development"])
    draft: bool = False
    auto_push: bool = True
    language: str = Field(default="ko", pattern="^(ko|en)$")


class PostUpdate(BaseModel):
    content: str = Field(..., min_length=1)
    auto_push: bool = True


class TranslateRequest(BaseModel):
    content: str = Field(..., min_length=1)
    source: str = Field(default="ko", pattern="^(ko|en)$")
    target: str = Field(default="en", pattern="^(ko|en)$")


# ============================================================
# Endpoints: System
# ============================================================

@app.get("/health", tags=["System"])
async def health():
    """서버 상태 (인증 불필요)"""
    return {"status": "healthy", "version": "2.0.0"}


@app.get("/", tags=["System"])
async def root():
    """API 정보"""
    return {
        "service": "Blog API",
        "version": "2.0.0",
        "architecture": "Independent Git-based",
        "docs": "/docs"
    }


# ============================================================
# Endpoints: Posts
# ============================================================

@app.get("/posts", tags=["Posts"])
async def list_posts(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    language: Optional[str] = Query(None, pattern="^(ko|en)$"),
    api_key: str = Depends(verify_api_key)
):
    """포스트 목록"""
    return blog_manager.list_posts(limit=limit, offset=offset, language=language)


@app.get("/posts/{filename}", tags=["Posts"])
async def get_post(
    filename: str,
    language: Optional[str] = Query(None, pattern="^(ko|en)$"),
    api_key: str = Depends(verify_api_key)
):
    """포스트 조회"""
    result = blog_manager.get_post(filename, language=language)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.post("/posts", tags=["Posts"])
async def create_post(post: PostCreate, api_key: str = Depends(verify_api_key)):
    """포스트 생성 + Git 동기화"""
    result = blog_manager.create_post(
        title=post.title,
        content=post.content,
        tags=post.tags,
        categories=post.categories,
        draft=post.draft,
        auto_push=post.auto_push,
        language=post.language
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))

    return result


@app.put("/posts/{filename}", tags=["Posts"])
async def update_post(
    filename: str,
    post: PostUpdate,
    language: Optional[str] = Query(None, pattern="^(ko|en)$"),
    api_key: str = Depends(verify_api_key)
):
    """포스트 수정"""
    result = blog_manager.update_post(
        filename=filename,
        content=post.content,
        auto_push=post.auto_push,
        language=language
    )

    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))

    return result


@app.delete("/posts/{filename}", tags=["Posts"])
async def delete_post(
    filename: str,
    language: Optional[str] = Query(None, pattern="^(ko|en)$"),
    api_key: str = Depends(verify_api_key)
):
    """포스트 삭제"""
    result = blog_manager.delete_post(filename, language=language)

    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))

    return result


# ============================================================
# Endpoints: Search
# ============================================================

@app.get("/search", tags=["Search"])
async def search(
    q: str = Query(..., min_length=1),
    api_key: str = Depends(verify_api_key)
):
    """포스트 검색"""
    return blog_manager.search_posts(q)


# ============================================================
# Endpoints: Git Sync
# ============================================================

@app.post("/sync", tags=["Git"])
async def sync(api_key: str = Depends(verify_api_key)):
    """Git 원격 동기화"""
    return blog_manager.sync()


@app.get("/status", tags=["Git"])
async def status(api_key: str = Depends(verify_api_key)):
    """Git 상태"""
    return git_handler.get_status()


# ============================================================
# Endpoints: Translation
# ============================================================

@app.post("/translate", tags=["Translation"])
async def translate(request: TranslateRequest, api_key: str = Depends(verify_api_key)):
    """LLM 기반 마크다운 번역"""
    if request.source == request.target:
        raise HTTPException(
            status_code=400,
            detail="Source and target languages must be different"
        )

    result = translator.translate(
        content=request.content,
        source=request.source,
        target=request.target
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))

    return result


# ============================================================
# Error Handlers
# ============================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"}
    )


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
