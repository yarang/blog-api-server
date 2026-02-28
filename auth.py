"""
API 인증 모듈
API Key 기반 인증을 제공합니다.
"""

import os
import secrets
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from logger_config import get_logger

logger = get_logger(__name__)

# API Key 헤더 정의
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# API Keys (환경 변수에서 로드, 여러 키 지원)
def get_valid_api_keys() -> set:
    """유효한 API 키 목록 반환"""
    keys_str = os.getenv("BLOG_API_KEYS", "")
    if not keys_str:
        return set()

    # 쉼표로 구분된 여러 키 지원
    keys = [k.strip() for k in keys_str.split(",") if k.strip()]
    logger.debug(f"Loaded {len(keys)} API keys")
    return set(keys)


def generate_api_key() -> str:
    """새 API 키 생성"""
    return f"blog_{secrets.token_urlsafe(32)}"


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """
    API Key 검증

    Usage:
        @app.get("/protected")
        async def protected_route(api_key: str = Depends(verify_api_key)):
            return {"message": "Authenticated"}
    """
    valid_keys = get_valid_api_keys()

    # API 키가 설정되지 않은 경우
    if not valid_keys:
        logger.error("No API keys configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication not configured"
        )

    # API 키가 제공되지 않은 경우
    if not api_key:
        logger.warning("API request without key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key required. Provide X-API-Key header."
        )

    # API 키 검증
    if api_key not in valid_keys:
        logger.warning("Invalid API key provided", extra={
            "key_prefix": api_key[:10] if api_key else "None"
        })
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key"
        )

    logger.debug("API key verified successfully")
    return api_key


# 선택적 인증 (읽기 전용 엔드포인트용)
async def optional_api_key(api_key: Optional[str] = Security(api_key_header)) -> Optional[str]:
    """선택적 API Key 검증 (공개 읽기 허용 시 사용)"""
    if not api_key:
        return None

    valid_keys = get_valid_api_keys()
    if api_key in valid_keys:
        return api_key

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid API Key"
    )
