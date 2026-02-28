"""
파일 기반 프로세스 간 락 (fcntl.flock)

threading.Lock의 멀티프로세스 환경 문제를 해결하기 위해
파일 디스크립터 기반 락을 제공합니다.
"""

import fcntl
import os
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)


class FileLock:
    """
    프로세스 간 안전한 파일 기반 락

    fcntl.flock()을 사용하여 멀티프로세스 환경에서도
    안전한 상호 배제를 제공합니다.
    """

    def __init__(
        self,
        lock_path: Optional[Path] = None,
        lock_name: str = "blog-git.lock",
        default_timeout: float = 60.0
    ):
        """
        Args:
            lock_path: 락 파일 생성 경로 (None이면 /tmp 사용)
            lock_name: 락 파일 이름
            default_timeout: 컨텍스트 매니저 사용时的 기본 타임아웃 (초)
        """
        if lock_path is None:
            lock_path = Path("/tmp")
        self.lock_file = lock_path / lock_name
        self._fd: Optional[int] = None
        self._default_timeout = default_timeout
        self._acquired = False  # 락 획득 여부 추적

    def acquire(self, timeout: float = 60.0) -> bool:
        """
        락 획득 (블로킹)

        Args:
            timeout: 타임아웃 (초)

        Returns:
            락 획득 성공 여부
        """
        import time

        start_time = time.time()

        try:
            # 락 파일 열기 (생성되지 않으면 생성)
            fd = os.open(self.lock_file, os.O_CREAT | os.O_WRONLY, 0o644)

            while True:
                try:
                    # 비블로킹으로 시도
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self._fd = fd
                    self._acquired = True
                    logger.debug(f"Lock acquired: {self.lock_file}")
                    return True
                except BlockingIOError:
                    # 락이 풀릴 때까지 대기
                    if time.time() - start_time >= timeout:
                        os.close(fd)
                        logger.warning(f"Lock acquisition timeout: {self.lock_file}")
                        return False
                    time.sleep(0.1)  # 100ms 대기

        except OSError as e:
            logger.error(f"Lock file error: {e}")
            return False

    def release(self) -> None:
        """락 해제"""
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
                self._fd = None
                self._acquired = False
                logger.debug(f"Lock released: {self.lock_file}")

                # 락 파일은 유지 (다른 프로세스에서 사용 중일 수 있음)
            except OSError as e:
                logger.error(f"Lock release error: {e}")

    def __enter__(self):
        if not self.acquire(self._default_timeout):
            raise TimeoutError(f"Could not acquire lock: {self.lock_file} (timeout: {self._default_timeout}s)")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        # 예외가 발생해도 락은 해제되었으므로 False를 반환하여 예외 전파
        return False

    @contextmanager
    def acquire_context(self, timeout: float = 60.0):
        """
        컨텍스트 매니저로서의 락 획득/해제

        Usage:
            with file_lock.acquire_context():
                # 임계 영역
                pass
        """
        if self.acquire(timeout):
            try:
                yield
            finally:
                self.release()
        else:
            raise TimeoutError(f"Could not acquire lock: {self.lock_file}")


# 전역 락 인스턴스 (기존 코드와 호환성 유지)
_git_lock = FileLock(lock_name="blog-git.lock")


def acquire_git_lock(timeout: float = 60.0) -> bool:
    """Git 작업용 전역 락 획득"""
    return _git_lock.acquire(timeout)


def release_git_lock() -> None:
    """Git 작업용 전역 락 해제"""
    _git_lock.release()


@contextmanager
def git_lock(timeout: float = 60.0):
    """
    Git 작업용 컨텍스트 매니저 락

    Usage:
        with git_lock():
            # Git 작업
            pass
    """
    if _git_lock.acquire(timeout):
        try:
            yield
        finally:
            _git_lock.release()
    else:
        raise TimeoutError("Could not acquire git lock")
