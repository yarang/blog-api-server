"""
Logging Configuration Module

구조화된 로깅 시스템을 제공합니다.
- 로그 레벨 환경 변수로 제어 (LOG_LEVEL)
- JSON 형식 로그 지원 (LOG_FORMAT=json)
- 파일 및 콘솔 출력 지원 (LOG_FILE)
"""

import os
import sys
import logging
import logging.config
from typing import Optional
from datetime import datetime

# 환경 변수
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "text").lower()  # text, json
LOG_FILE = os.getenv("LOG_FILE", "")  # 비어있으면 파일 미사용


class JSONFormatter(logging.Formatter):
    """JSON 형식 로그 포매터 - 상세 정보 포함"""

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "timezone": datetime.now().astimezone().tzname(datetime.now()),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "file": record.filename,
            "pathname": record.pathname,
        }

        # 예외 정보가 있으면 추가
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            log_data["exception_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None

        # 추가 컨텍스트가 있으면 추가
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        # 프로세스/스레드 정보 추가
        log_data["process_id"] = record.process
        log_data["thread_name"] = record.threadName

        return json.dumps(log_data, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """컬러 콘솔 포매터 - 타임존 및 호출자 정보 포함"""

    # ANSI 색상 코드
    COLORS = {
        "DEBUG": "\033[36m",      # 청록색
        "INFO": "\033[32m",       # 녹색
        "WARNING": "\033[33m",    # 노란색
        "ERROR": "\033[31m",      # 빨간색
        "CRITICAL": "\033[35m",   # 자주색
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        # 타임존 정보 추가
        record.timezone = datetime.now().astimezone().tzinfo.tzname(datetime.now())
        return super().format(record)


def get_log_format() -> str:
    """로그 포맷 반환 - 상세 정보 포함"""
    return "%(asctime)s %(timezone)s [%(levelname)s] %(name)s:%(filename)s:%(lineno)d - %(message)s"


def setup_logging(
    name: Optional[str] = None,
    level: Optional[str] = None,
    log_format: Optional[str] = None,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    로거 설정 및 반환

    Args:
        name: 로거 이름 (모듈 __name__ 권장)
        level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: 로그 포맷 (text, json)
        log_file: 로그 파일 경로

    Returns:
        설정된 logging.Logger 인스턴스
    """
    # 환경 변수 우선, 없으면 매개변수 사용
    log_level = (level or LOG_LEVEL).upper()
    format_type = (log_format or LOG_FORMAT).lower()
    file_path = log_file or LOG_FILE

    # 로그 레벨 검증
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if log_level not in valid_levels:
        log_level = "INFO"

    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))

    # 기존 핸들러 제거 (중복 방지)
    root_logger.handlers.clear()

    # 포매터 생성
    if format_type == "json":
        formatter = JSONFormatter()
    else:
        formatter = ColoredFormatter(get_log_format())

    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, log_level))
    root_logger.addHandler(console_handler)

    # 파일 핸들러 (옵션)
    if file_path:
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file_handler = logging.FileHandler(file_path, encoding="utf-8")
            # 파일은 항상 텍스트 포맷 (가독성)
            file_handler.setFormatter(logging.Formatter(get_log_format()))
            file_handler.setLevel(getattr(logging, log_level))
            root_logger.addHandler(file_handler)
        except (OSError, IOError) as e:
            # 파일 생성 실패시 무시하고 콘솔만 사용
            pass

    # 요청한 로거 반환
    return logging.getLogger(name) if name else root_logger


def get_logger(name: str) -> logging.Logger:
    """
    모듈에서 사용할 로거 반환

    Usage:
        from logger_config import get_logger
        logger = get_logger(__name__)
        logger.info("Message")
    """
    return logging.getLogger(name)


def log_with_context(logger: logging.Logger, level: str, msg: str, **extra):
    """
    추가 컨텍스트와 함께 로그 기록

    Usage:
        log_with_context(logger, "INFO", "Post created",
                        post_id="123", title="Test Post")
    """
    log_func = getattr(logger, level.lower(), logger.info)
    extra_data = {"extra_data": extra} if extra else {}
    log_func(msg, extra=extra_data)


# 초기화 (모듈 임포트 시 자동 호출)
setup_logging()
