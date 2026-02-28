"""
Blog API Server - Block 1: 독립 Git 관리

다른 모듈과 Git을 통해서만 동기화됩니다.
"""

import os
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from logger_config import setup_logging, get_logger, log_with_context
from auth import verify_api_key
from blog_manager import blog_manager
from git_handler import git_handler
from translator import translator, mermaid_renderer
from middleware import MonitoringMiddleware
from api_utils import log_endpoint, ApiResponse

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logger = setup_logging(__name__)


# ============================================================
# Lifespan
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Blog API Server starting...", extra={"repo_path": str(blog_manager.git.repo_path)})
    log_with_context(logger, "INFO", "Blog API Server starting",
                    repo_path=str(blog_manager.git.repo_path),
                    version="2.0.0")

    # 초기 동기화
    sync_result = blog_manager.git.pull()
    if sync_result:
        logger.info("Initial git sync completed")
    else:
        logger.warning("Initial git sync failed")

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

# 모니터링 미들웨어
app.add_middleware(MonitoringMiddleware)

# 미들웨어 인스턴스 (메트릭 조회용)
_metrics_collector = None


def get_metrics_collector():
    """메트릭 수집기 인스턴스 반환 (지연 초기화)"""
    global _metrics_collector
    if _metrics_collector is None:
        # 첫 번째 미들웨어 인스턴스 찾기
        for middleware in app.user_middleware:
            if hasattr(middleware, 'cls') and middleware.cls == MonitoringMiddleware:
                # 미들웨어가 이미 추가되었으므로 상태 저장용 인스턴스 생성
                _metrics_collector = MonitoringMiddleware(app)
                break
    return _metrics_collector


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


@app.get("/metrics", tags=["Monitoring"])
@log_endpoint("metrics")
async def metrics(api_key: str = Depends(verify_api_key)):
    """
    서버 메트릭 (인증 필요)

    반환:
    - total_requests: 총 요청 수
    - error_count: 에러 수
    - slow_request_count: 느린 요청 수 (>1초)
    - error_rate_percent: 에러율
    - slow_request_rate_percent: 느린 요청 비율
    """
    collector = get_metrics_collector()
    if collector:
        return collector.get_stats()
    return {"error": "Metrics collector not available"}


@app.post("/metrics/reset", tags=["Monitoring"])
@log_endpoint("reset_metrics")
async def reset_metrics(api_key: str = Depends(verify_api_key)):
    """
    메트릭 초기화 (인증 필요)
    """
    collector = get_metrics_collector()
    if collector:
        collector.reset_stats()
        return {"success": True, "message": "Metrics reset"}
    return {"success": False, "error": "Metrics collector not available"}


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
@log_endpoint("list_posts", log_args=True)
async def list_posts(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    language: Optional[str] = Query(None, pattern="^(ko|en)$"),
    api_key: str = Depends(verify_api_key)
):
    """포스트 목록"""
    result = blog_manager.list_posts(limit=limit, offset=offset, language=language)

    logger.debug("list_posts result", extra={
        "returned_count": len(result.get("posts", [])),
        "total_count": result.get("total", 0)
    })

    return result


@app.get("/posts/{filename}", tags=["Posts"])
@log_endpoint("get_post", log_args=True)
async def get_post(
    filename: str,
    language: Optional[str] = Query(None, pattern="^(ko|en)$"),
    api_key: str = Depends(verify_api_key)
):
    """포스트 조회"""
    result = blog_manager.get_post(filename, language=language)

    if "error" in result:
        logger.warning("Post not found", extra={"filename": filename, "language": language})
        raise HTTPException(status_code=404, detail=result["error"])

    logger.debug("get_post result", extra={
        "filename": filename,
        "content_length": len(result.get("content", ""))
    })

    return result


@app.post("/posts", tags=["Posts"])
@log_endpoint("create_post", slow_threshold_ms=5000)
async def create_post(post: PostCreate, api_key: str = Depends(verify_api_key)):
    """포스트 생성 + Git 동기화"""
    logger.info("[API] Creating post", extra={
        "title": post.title[:100],
        "language": post.language,
        "draft": post.draft,
        "auto_push": post.auto_push,
        "content_length": len(post.content),
        "tags": post.tags,
        "categories": post.categories
    })

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
        logger.error("[API] Create post failed", extra={"error": result.get("error")})
        raise HTTPException(status_code=500, detail=result.get("error"))

    logger.info("[API] Post created successfully", extra={
        "filename": result.get("filename"),
        "git_success": result.get("git", {}).get("success", False)
    })

    return result


@app.put("/posts/{filename}", tags=["Posts"])
@log_endpoint("update_post", log_args=True)
async def update_post(
    filename: str,
    post: PostUpdate,
    language: Optional[str] = Query(None, pattern="^(ko|en)$"),
    api_key: str = Depends(verify_api_key)
):
    """포스트 수정"""
    logger.debug("update_post request", extra={
        "filename": filename,
        "language": language,
        "auto_push": post.auto_push,
        "content_length": len(post.content)
    })

    result = blog_manager.update_post(
        filename=filename,
        content=post.content,
        auto_push=post.auto_push,
        language=language
    )

    if not result.get("success"):
        logger.warning("update_post failed", extra={
            "error": result.get("error"),
            "filename": filename
        })
        raise HTTPException(status_code=404, detail=result.get("error"))

    return result


@app.delete("/posts/{filename}", tags=["Posts"])
@log_endpoint("delete_post", log_args=True)
async def delete_post(
    filename: str,
    language: Optional[str] = Query(None, pattern="^(ko|en)$"),
    api_key: str = Depends(verify_api_key)
):
    """포스트 삭제"""
    result = blog_manager.delete_post(filename, language=language)

    if not result.get("success"):
        logger.warning("delete_post failed", extra={
            "error": result.get("error"),
            "filename": filename
        })
        raise HTTPException(status_code=404, detail=result.get("error"))

    return result


# ============================================================
# Endpoints: Search
# ============================================================

@app.get("/search", tags=["Search"])
@log_endpoint("search", log_args=True)
async def search(
    q: str = Query(..., min_length=1),
    api_key: str = Depends(verify_api_key)
):
    """포스트 검색"""
    logger.debug("search request", extra={"query": q, "query_length": len(q)})

    result = blog_manager.search_posts(q)

    logger.debug("search result", extra={
        "query": q,
        "result_count": result.get("total", 0),
        "returned_count": len(result.get("results", []))
    })

    return result


# ============================================================
# Endpoints: Git Sync
# ============================================================

@app.post("/sync", tags=["Git"])
@log_endpoint("sync", slow_threshold_ms=5000)
async def sync(api_key: str = Depends(verify_api_key)):
    """Git 원격 동기화"""
    result = blog_manager.sync()
    return result


@app.get("/status", tags=["Git"])
@log_endpoint("status")
async def status(api_key: str = Depends(verify_api_key)):
    """Git 상태"""
    result = git_handler.get_status()
    return result


# ============================================================
# Endpoints: Translation
# ============================================================

@app.post("/translate", tags=["Translation"])
@log_endpoint("translate", slow_threshold_ms=30000)
async def translate(request: TranslateRequest, api_key: str = Depends(verify_api_key)):
    """LLM 기반 마크다운 번역"""
    if request.source == request.target:
        logger.warning("Same source and target language requested", extra={"language": request.source})
        raise HTTPException(
            status_code=400,
            detail="Source and target languages must be different"
        )

    logger.debug("translate request", extra={
        "source": request.source,
        "target": request.target,
        "content_length": len(request.content)
    })

    result = translator.translate(
        content=request.content,
        source=request.source,
        target=request.target
    )

    if not result.get("success"):
        logger.error("translate failed", extra={"error": result.get("error")})
        raise HTTPException(status_code=500, detail=result.get("error"))

    logger.debug("translate completed", extra={
        "source": request.source,
        "target": request.target,
        "result_length": len(result.get("translated", ""))
    })

    return result


@app.post("/translate/sync", tags=["Translation"])
@log_endpoint("translate_sync", slow_threshold_ms=60000)
async def translate_sync(api_key: str = Depends(verify_api_key)):
    """
    한국어/영어 포스트 동기화
    - 번역되지 않은 포스트 찾기
    - 자동 번역 후 저장
    """
    if not translator.api_key:
        logger.error("Translation service not configured")
        raise HTTPException(
            status_code=503,
            detail="Translation service not configured. Set API key."
        )

    result = blog_manager.sync_translations()

    logger.info("translate_sync completed", extra={
        "translated": result.get("summary", {}).get("translated", 0),
        "failed": result.get("summary", {}).get("failed", 0)
    })

    return result


@app.get("/translate/status", tags=["Translation"])
@log_endpoint("translation_status")
async def translation_status(api_key: str = Depends(verify_api_key)):
    """번역 상태 확인"""
    result = blog_manager.get_translation_status()
    return result


# ============================================================
# Endpoints: Mermaid Diagram
# ============================================================

class MermaidRenderRequest(BaseModel):
    code: str = Field(..., min_length=1, description="Mermaid 다이어그램 코드")
    filename: Optional[str] = Field(None, description="저장할 파일명 (선택)")


class MermaidMarkdownRequest(BaseModel):
    content: str = Field(..., min_length=1, description="마크다운 콘텐츠")
    output_filename: Optional[str] = Field(None, description="결과 마크다운 파일명 (선택)")


@app.post("/mermaid/render", tags=["Mermaid"])
@log_endpoint("render_mermaid", slow_threshold_ms=10000)
async def render_mermaid(request: MermaidRenderRequest, api_key: str = Depends(verify_api_key)):
    """
    Mermaid 코드를 SVG로 렌더링

    Mermaid CLI가 설치되어 있어야 합니다:
    npm install -g @mermaid-js/mermaid-cli
    """
    result = mermaid_renderer.render(request.code, request.filename)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))

    return result


@app.post("/mermaid/render-markdown", tags=["Mermaid"])
@log_endpoint("render_mermaid_in_markdown", slow_threshold_ms=30000)
async def render_mermaid_in_markdown(request: MermaidMarkdownRequest, api_key: str = Depends(verify_api_key)):
    """
    마크다운의 Mermaid 코드블록을 SVG로 변환

    마크다운 내의 ```mermaid ... ``` 코드블록을 찾아
    SVG로 렌더링하고 이미지 참조로 대체합니다.
    """
    result = mermaid_renderer.render_from_markdown(
        request.content,
        request.output_filename
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))

    return {
        "success": True,
        "replaced_count": result["replaced_count"],
        "diagrams": result["diagrams"],
        "content": result["content"][:1000] + "..." if len(result.get("content", "")) > 1000 else result.get("content", "")
    }


@app.get("/mermaid/status", tags=["Mermaid"])
@log_endpoint("mermaid_status")
async def mermaid_status(api_key: str = Depends(verify_api_key)):
    """Mermaid CLI 상태 확인"""
    return {
        "available": mermaid_renderer.cli_available,
        "cli": os.getenv("MERMAID_CLI", "mmdc"),
        "output_dir": str(mermaid_renderer.output_dir)
    }


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
