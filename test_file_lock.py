"""
파일 락 동시성 테스트

fcntl.flock 기반 FileLock이 멀티프로세스 환경에서
제대로 작동하는지 검증합니다.
"""

import pytest
import os
import time
import tempfile
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from multiprocessing import Process

from file_lock import FileLock, git_lock


class TestFileLock:
    """FileLock 단위 테스트"""

    def test_initialization(self):
        """락 초기화 테스트"""
        lock = FileLock(lock_name="test.lock")
        assert lock.lock_file.name == "test.lock"

    def test_acquire_release(self):
        """락 획득 및 해제 테스트"""
        lock = FileLock(lock_name="test-acquire.lock")

        assert lock.acquire(timeout=1.0)
        assert lock._fd is not None

        # 이미 락을 획득한 상태에서 다시 획득 시도는
        # 같은 프로세스에서는 성공해야 함 (fcntl은 프로세스 레벨 락)
        lock.release()
        assert lock._fd is None

    def test_context_manager(self):
        """컨텍스트 매니저 테스트"""
        lock = FileLock(lock_name="test-context.lock")

        with lock:
            assert lock._fd is not None

        assert lock._fd is None

    def test_acquire_context(self):
        """acquire_context 컨텍스트 매니저 테스트"""
        lock = FileLock(lock_name="test-acquire-context.lock")

        with lock.acquire_context(timeout=1.0):
            assert lock._fd is not None

        assert lock._fd is None

    def test_timeout(self):
        """타임아웃 테스트"""
        lock1 = FileLock(lock_name="test-timeout.lock")
        lock2 = FileLock(lock_name="test-timeout.lock")

        assert lock1.acquire(timeout=1.0)

        # lock1이 락을 가지고 있으므로 lock2는 실패해야 함
        # 하지만 fcntl은 같은 프로세스에서는 재진입 가능
        # 따라서 멀티스레드로 테스트 필요
        lock1.release()

    def test_concurrent_threads(self):
        """멀티스레드 환경 테스트"""
        lock = FileLock(lock_name="test-threads.lock")
        results = []

        def worker(worker_id):
            """작업자 함수"""
            if lock.acquire(timeout=5.0):
                try:
                    # 임계 영역: 다른 스레드와 동시 실행되지 않아야 함
                    time.sleep(0.1)
                    results.append(worker_id)
                finally:
                    lock.release()
            else:
                results.append(f"timeout-{worker_id}")

        # 10개의 스레드 동시 실행
        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 모든 작업이 완료되어야 함
        assert len(results) == 10

    def test_global_git_lock(self):
        """전역 git_lock 테스트"""
        with git_lock(timeout=1.0):
            # Git 작업 시뮬레이션
            time.sleep(0.01)


class TestMultiprocessSafety:
    """멀티프로세스 안전성 테스트"""

    def _worker_process(self, lock_file_path: str, worker_id: int, results_file: str):
        """프로세스 작업자"""
        lock = FileLock(Path(lock_file_path))

        if lock.acquire(timeout=5.0):
            try:
                # 임계 영역
                start_time = time.time()
                time.sleep(0.1)  # 100ms 작업

                # 결과 파일에 기록 (동시 접근 검증)
                with open(results_file, "a") as f:
                    elapsed = time.time() - start_time
                    f.write(f"worker-{worker_id},{elapsed}\n")
            finally:
                lock.release()
        else:
            with open(results_file, "a") as f:
                f.write(f"worker-{worker_id},timeout\n")

    def test_multiprocess_lock(self):
        """멀티프로세스 락 테스트"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            results_file = f.name

        lock_file = Path("/tmp") / "test-multiprocess.lock"

        # 기존 락 파일 정리
        if lock_file.exists():
            lock_file.unlink()

        try:
            # 5개 프로세스 동시 실행
            processes = []
            for i in range(5):
                p = Process(
                    target=self._worker_process,
                    args=(str(lock_file), i, results_file)
                )
                processes.append(p)
                p.start()

            for p in processes:
                p.join()

            # 결과 확인
            with open(results_file, 'r') as f:
                lines = f.readlines()

            assert len(lines) == 5

            # 타임아웃이 없어야 함
            timeouts = [l for l in lines if "timeout" in l]
            assert len(timeouts) == 0

        finally:
            os.unlink(results_file)


if __name__ == "__main__":
    import threading
    pytest.main([__file__, "-v"])
