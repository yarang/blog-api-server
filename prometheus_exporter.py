"""
Prometheus Metrics Exporter for Blog API Server

Prometheus 형식의 메트릭을 노출합니다.
- Counter: 총 요청 수, 에러 수
- Histogram: 요청 처리 시간 분포
- Gauge: 현재 활성 요청 수
"""

import time
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from functools import wraps
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from logger_config import get_logger

logger = get_logger(__name__)


# Prometheus Metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

http_errors_total = Counter(
    'http_errors_total',
    'Total HTTP errors',
    ['method', 'endpoint', 'status']
)

active_requests_gauge = Gauge(
    'active_requests',
    'Number of active requests'
)

git_operations_total = Counter(
    'git_operations_total',
    'Total Git operations',
    ['operation', 'status']
)

git_operation_duration_seconds = Histogram(
    'git_operation_duration_seconds',
    'Git operation latency',
    ['operation']
)

translation_requests_total = Counter(
    'translation_requests_total',
    'Total translation requests',
    ['source_lang', 'target_lang', 'status']
)

translation_duration_seconds = Histogram(
    'translation_duration_seconds',
    'Translation request latency'
)

post_operations_total = Counter(
    'post_operations_total',
    'Total post operations',
    ['operation', 'language', 'status']
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    Prometheus 메트릭 수집 미들웨어
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.start_time = time.time()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """요청 처리 및 Prometheus 메트릭 수집"""

        # 메트릭스 레이블 준비
        method = request.method
        path = request.url.path

        # health, metrics 경로는 메트릭에서 제외
        if path in ["/health", "/metrics", "/metrics/prometheus"]:
            return await call_next(request)

        # 활성 요청 수 증가
        active_requests_gauge.inc()

        # 요청 시작 시간
        start_time = time.time()

        try:
            response = await call_next(request)

            # 처리 시간 기록
            duration = time.time() - start_time
            status = response.status_code

            # 메트릭 기록
            http_requests_total.labels(
                method=method,
                endpoint=path,
                status=status
            ).inc()

            http_request_duration_seconds.labels(
                method=method,
                endpoint=path
            ).observe(duration)

            # 에러 메트릭
            if status >= 400:
                http_errors_total.labels(
                    method=method,
                    endpoint=path,
                    status=status
                ).inc()

            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Request failed: {e}")

            http_requests_total.labels(
                method=method,
                endpoint=path,
                status=500
            ).inc()

            http_request_duration_seconds.labels(
                method=method,
                endpoint=path
            ).observe(duration)

            http_errors_total.labels(
                method=method,
                endpoint=path,
                status=500
            ).inc()

            raise

        finally:
            # 활성 요청 수 감소
            active_requests_gauge.dec()


def track_git_operation(operation: str):
    """Git 작업 메트릭 데코레이터"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                logger.error(f"Git operation failed: {operation} - {e}")
                raise
            finally:
                duration = time.time() - start_time
                git_operations_total.labels(
                    operation=operation,
                    status=status
                ).inc()
                git_operation_duration_seconds.labels(
                    operation=operation
                ).observe(duration)
        return wrapper
    return decorator


def track_translation(source_lang: str = "ko", target_lang: str = "en"):
    """번역 작업 메트릭 데코레이터"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"

            try:
                result = func(*args, **kwargs)
                if not result.get("success"):
                    status = "error"
                return result
            except Exception as e:
                status = "error"
                logger.error(f"Translation failed: {e}")
                raise
            finally:
                duration = time.time() - start_time
                translation_requests_total.labels(
                    source_lang=source_lang,
                    target_lang=target_lang,
                    status=status
                ).inc()
                translation_duration_seconds.observe(duration)
        return wrapper
    return decorator


def track_post_operation(operation: str, language: str = "ko"):
    """포스트 작업 메트릭 데코레이터"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            status = "success"

            try:
                result = func(*args, **kwargs)
                if not result.get("success"):
                    status = "error"
                return result
            except Exception as e:
                status = "error"
                logger.error(f"Post operation failed: {operation} - {e}")
                raise
            finally:
                post_operations_total.labels(
                    operation=operation,
                    language=language,
                    status=status
                ).inc()
        return wrapper
    return decorator


def get_metrics_text() -> bytes:
    """Prometheus 텍스트 형식 메트릭 반환"""
    return generate_latest()


def get_metrics_content_type() -> str:
    """Prometheus 메트릭 Content-Type 반환"""
    return CONTENT_TYPE_LATEST
