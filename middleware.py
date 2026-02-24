"""
API Monitoring Middleware

- 요청/응답 시간 모니터링
- 에러 추적
- 상태 코드 모니터링
"""

import time
import os
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from logger_config import get_logger

logger = get_logger(__name__)


class MonitoringMiddleware(BaseHTTPMiddleware):
    """
    API 모니터링 미들웨어

    기능:
    - 요청/응답 시간 측정
    - 상태 코드 로깅
    - 에러 추적
    - 느린 요청 경고 (SLA 초과)
    """

    # SLA 기준 (밀리초)
    SLOW_REQUEST_THRESHOLD = int(os.getenv("SLOW_REQUEST_THRESHOLD", "1000"))  # 1초
    VERY_SLOW_THRESHOLD = int(os.getenv("VERY_SLOW_THRESHOLD", "3000"))  # 3초

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.request_count = 0
        self.error_count = 0
        self.slow_request_count = 0

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """요청 처리 및 모니터링"""

        # 요청 시작 시간
        start_time = time.time()

        # 요청 정보 수집
        method = request.method
        path = request.url.path
        client_host = request.client.host if request.client else "unknown"

        # 건너뛸 경로 (health check 등)
        if path in ["/health", "/metrics"]:
            return await call_next(request)

        # 요청 ID 생성 (추적용)
        request_id = f"{int(start_time * 1000)}-{id(request)}"
        request.state.request_id = request_id

        # 요청 시작 로그
        logger.info(f"Request started", extra={
            "request_id": request_id,
            "method": method,
            "path": path,
            "client": client_host
        })

        try:
            # 요청 처리
            response = await call_next(request)

            # 응답 시간 계산
            process_time = (time.time() - start_time) * 1000  # 밀리초

            # 상태 코드
            status_code = response.status_code

            # 통계 업데이트
            self.request_count += 1
            if status_code >= 400:
                self.error_count += 1
            if process_time > self.SLOW_REQUEST_THRESHOLD:
                self.slow_request_count += 1

            # 응답 시간에 따른 로그 레벨 결정
            if process_time > self.VERY_SLOW_THRESHOLD:
                log_level = "error"
                log_msg = f"VERY SLOW REQUEST: {process_time:.0f}ms"
            elif process_time > self.SLOW_REQUEST_THRESHOLD:
                log_level = "warning"
                log_msg = f"Slow request: {process_time:.0f}ms"
            elif status_code >= 500:
                log_level = "error"
                log_msg = f"Server error: {status_code}"
            elif status_code >= 400:
                log_level = "warning"
                log_msg = f"Client error: {status_code}"
            else:
                log_level = "debug"
                log_msg = f"Request completed: {status_code}"

            # 로그 기록
            logger.log(
                getattr(logging, log_level.upper()),
                log_msg,
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "process_time_ms": round(process_time, 2),
                    "client": client_host
                }
            )

            # 응답 헤더에 처리 시간 추가
            response.headers["X-Process-Time"] = f"{process_time:.2f}"
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # 처리되지 않은 예외
            process_time = (time.time() - start_time) * 1000
            self.request_count += 1
            self.error_count += 1

            logger.error(
                f"Unhandled exception: {str(e)}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "process_time_ms": round(process_time, 2),
                    "exception_type": type(e).__name__,
                    "client": client_host
                },
                exc_info=True
            )
            raise

    def get_stats(self) -> dict:
        """통계 정보 반환"""
        error_rate = (self.error_count / self.request_count * 100) if self.request_count > 0 else 0
        slow_rate = (self.slow_request_count / self.request_count * 100) if self.request_count > 0 else 0

        return {
            "total_requests": self.request_count,
            "error_count": self.error_count,
            "slow_request_count": self.slow_request_count,
            "error_rate_percent": round(error_rate, 2),
            "slow_request_rate_percent": round(slow_rate, 2),
        }

    def reset_stats(self):
        """통계 초기화"""
        self.request_count = 0
        self.error_count = 0
        self.slow_request_count = 0


# 전역 인스턴스
monitoring_middleware = MonitoringMiddleware
