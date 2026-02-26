"""
API Monitoring Middleware

- 요청/응답 시간 모니터링
- 에러 추적
- 상태 코드 모니터링
- 요청/응답 바디 로깅
- UUID 기반 요청 추적
"""

import time
import os
import uuid
import json
import logging
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from logger_config import get_logger

logger = get_logger(__name__)

# 민감한 필드 목록 (마스킹 처리)
SENSITIVE_FIELDS = {"password", "token", "api_key", "secret", "authorization", "credential"}


class MonitoringMiddleware(BaseHTTPMiddleware):
    """
    API 모니터링 미들웨어

    기능:
    - 요청/응답 시간 측정
    - 상태 코드 로깅
    - 에러 추적
    - 느린 요청 경고 (SLA 초과)
    - UUID 기반 요청 추적
    - 요청/응답 바디 로깅 (민감 정보 마스킹)
    - User-Agent 및 호출자 정보 로깅
    """

    # SLA 기준 (밀리초)
    SLOW_REQUEST_THRESHOLD = int(os.getenv("SLOW_REQUEST_THRESHOLD", "1000"))  # 1초
    VERY_SLOW_THRESHOLD = int(os.getenv("VERY_SLOW_THRESHOLD", "3000"))  # 3초
    MAX_BODY_LOG_LENGTH = int(os.getenv("MAX_BODY_LOG_LENGTH", "1000"))  # 최대 바디 로그 길이

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.request_count = 0
        self.error_count = 0
        self.slow_request_count = 0

    def _mask_sensitive_data(self, data: dict) -> dict:
        """민감한 데이터 마스킹"""
        if not isinstance(data, dict):
            return data

        masked = {}
        for key, value in data.items():
            if key.lower() in SENSITIVE_FIELDS:
                masked[key] = "***MASKED***"
            elif isinstance(value, dict):
                masked[key] = self._mask_sensitive_data(value)
            else:
                masked[key] = value
        return masked

    def _truncate_body(self, body: str, max_length: int = None) -> str:
        """바디 내용 자르기"""
        max_length = max_length or self.MAX_BODY_LOG_LENGTH
        if len(body) > max_length:
            return body[:max_length] + "...[TRUNCATED]"
        return body

    async def _get_request_body(self, request: Request) -> Optional[str]:
        """요청 바디 읽기"""
        try:
            body = await request.body()
            if not body:
                return None

            # JSON 파싱 시도
            try:
                body_json = json.loads(body.decode("utf-8"))
                masked = self._mask_sensitive_data(body_json)
                return self._truncate_body(json.dumps(masked, ensure_ascii=False))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # JSON이 아니면 원본 반환
                return self._truncate_body(body.decode("utf-8", errors="replace"))
        except Exception as e:
            logger.debug(f"Failed to read request body: {e}")
            return None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """요청 처리 및 모니터링"""

        # 요청 시작 시간
        start_time = time.time()

        # 요청 정보 수집
        method = request.method
        path = request.url.path
        query_params = dict(request.query_params) if request.query_params else {}
        client_host = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        content_type = request.headers.get("content-type", "")

        # 건너뛸 경로 (health check 등)
        if path in ["/health", "/metrics"]:
            return await call_next(request)

        # UUID 기반 요청 ID 생성
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # 요청 바디 읽기 (POST, PUT, PATCH만)
        request_body = None
        if method in ["POST", "PUT", "PATCH"] and "application/json" in content_type:
            request_body = await self._get_request_body(request)

        # 요청 시작 로그 (상세 정보 포함)
        logger.info("Request started", extra={
            "extra_data": {
                "request_id": request_id,
                "method": method,
                "path": path,
                "query_params": query_params if query_params else None,
                "client_ip": client_host,
                "user_agent": user_agent,
                "content_type": content_type,
                "request_body": request_body
            }
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
                log_level = "info"
                log_msg = f"Request completed: {status_code}"

            # 로그 기록 (상세 정보 포함)
            logger.log(
                getattr(logging, log_level.upper()),
                log_msg,
                extra={
                    "extra_data": {
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "query_params": query_params if query_params else None,
                        "status_code": status_code,
                        "process_time_ms": round(process_time, 2),
                        "client_ip": client_host,
                        "user_agent": user_agent,
                        "response_content_type": response.headers.get("content-type", "")
                    }
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
                    "extra_data": {
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "query_params": query_params if query_params else None,
                        "process_time_ms": round(process_time, 2),
                        "exception_type": type(e).__name__,
                        "exception_message": str(e),
                        "client_ip": client_host,
                        "user_agent": user_agent,
                        "request_body": request_body
                    }
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
