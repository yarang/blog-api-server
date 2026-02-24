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

from dotenv import load_dotenv

from logger_config import setup_logging, get_logger, log_with_context
from auth import verify_api_key
from blog_manager import blog_manager
from git_handler import git_handler
from translator import translator
from middleware import MonitoringMiddleware

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

# 전역 인스턴스 (모니터링 엔드포인트용)
_monitoring_middleware = MonitoringMiddleware(app)


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
    return _monitoring_middleware.get_stats()


@app.post("/metrics/reset", tags=["Monitoring"])
async def reset_metrics(api_key: str = Depends(verify_api_key)):
    """
    메트릭 초기화 (인증 필요)
    """
    _monitoring_middleware.reset_stats()
    return {"success": True, "message": "Metrics reset"}


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
    logger.info(f"Creating post: {post.title[:50]}...", extra={
        "title": post.title,
        "language": post.language,
        "tags": post.tags,
        "draft": post.draft
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
        logger.error(f"Failed to create post: {result.get('error')}", extra={
            "error": result.get("error"),
            "title": post.title
        })
        raise HTTPException(status_code=500, detail=result.get("error"))

    logger.info(f"Post created successfully: {result.get('filename')}", extra={
        "filename": result.get("filename"),
        "language": result.get("language")
    })
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


@app.post("/translate/sync", tags=["Translation"])
async def translate_sync(api_key: str = Depends(verify_api_key)):
    """
    한국어/영어 포스트 동기화
    - 번역되지 않은 포스트 찾기
    - 자동 번역 후 저장
    """
    if not translator.api_key:
        raise HTTPException(
            status_code=503,
            detail="Translation service not configured. Set API key."
        )

    result = blog_manager.sync_translations()
    return result


@app.get("/translate/status", tags=["Translation"])
async def translation_status(api_key: str = Depends(verify_api_key)):
    """번역 상태 확인"""
    return blog_manager.get_translation_status()


# ============================================================
# Endpoints: Mermaid Diagram
# ============================================================

from translator import mermaid_renderer
from pydantic import BaseModel


class MermaidRenderRequest(BaseModel):
    code: str = Field(..., min_length=1, description="Mermaid 다이어그램 코드")
    filename: Optional[str] = Field(None, description="저장할 파일명 (선택)")


class MermaidMarkdownRequest(BaseModel):
    content: str = Field(..., min_length=1, description="마크다운 콘텐츠")
    output_filename: Optional[str] = Field(None, description="결과 마크다운 파일명 (선택)")


@app.post("/mermaid/render", tags=["Mermaid"])
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
