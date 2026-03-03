"""
API Utilities - 엔드포인트용 데코레이터 및 헬퍼 함수
"""

import time
from functools import wraps
from typing import Callable, Any, Optional
from fastapi import Request, HTTPException
from logger_config import get_logger

logger = get_logger(__name__)


def log_endpoint(
    operation_name: Optional[str] = None,
    log_args: bool = False,
    slow_threshold_ms: float = 1000
):
    """
    엔드포인트 실행 시간 및 로깅 데코레이터

    Args:
        operation_name: 작업 이름 (기본값: 함수명)
        log_args: 인자 로깅 여부
        slow_threshold_ms: 느린 요청 기준 (ms)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            start_time = time.time()

            # 요청 로깅
            log_data = {"operation": op_name}
            if log_args:
                log_data["args_count"] = len(args)
                log_data["kwargs"] = list(kwargs.keys())

            logger.info(f"[API] {op_name} started", extra=log_data)

            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start_time
                elapsed_ms = round(elapsed * 1000, 2)

                # 완료 로그
                logger.info(f"[API] {op_name} completed", extra={
                    "duration_ms": elapsed_ms,
                    "slow": elapsed_ms > slow_threshold_ms
                })

                return result

            except HTTPException:
                elapsed = time.time() - start_time
                logger.warning(f"[API] {op_name} HTTP error", extra={
                    "duration_ms": round(elapsed * 1000, 2),
                    "status_code": "HTTPException"
                })
                raise
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"[API] {op_name} failed", extra={
                    "duration_ms": round(elapsed * 1000, 2),
                    "error": str(e)
                }, exc_info=True)
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            start_time = time.time()

            log_data = {"operation": op_name}
            if log_args:
                log_data["args_count"] = len(args)
                log_data["kwargs"] = list(kwargs.keys())

            logger.info(f"[API] {op_name} started", extra=log_data)

            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                elapsed_ms = round(elapsed * 1000, 2)

                logger.info(f"[API] {op_name} completed", extra={
                    "duration_ms": elapsed_ms,
                    "slow": elapsed_ms > slow_threshold_ms
                })

                return result

            except HTTPException:
                elapsed = time.time() - start_time
                logger.warning(f"[API] {op_name} HTTP error", extra={
                    "duration_ms": round(elapsed * 1000, 2)
                })
                raise
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"[API] {op_name} failed", extra={
                    "duration_ms": round(elapsed * 1000, 2),
                    "error": str(e)
                }, exc_info=True)
                raise

        # async 함수인지 확인
        if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:
            return async_wrapper
        return sync_wrapper

    return decorator


class ApiResponse:
    """표준 API 응답 헬퍼"""

    @staticmethod
    def success(data: Any = None, message: str = None) -> dict:
        """성공 응답"""
        response = {"success": True}
        if data is not None:
            response["data"] = data
        if message:
            response["message"] = message
        return response

    @staticmethod
    def error(message: str, status_code: int = 500, detail: Any = None) -> dict:
        """에러 응답"""
        response = {"success": False, "error": message}
        if detail is not None:
            response["detail"] = detail
        return response

    @staticmethod
    def paginated(items: list, total: int, limit: int, offset: int) -> dict:
        """페이지네이션 응답"""
        return {
            "success": True,
            "data": items,
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total
            }
        }
