"""
Git 작업 핸들러
자동 commit 및 push를 처리합니다.
"""

import os
import subprocess
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 블로그 루트 경로
BLOG_ROOT = Path(os.getenv("BLOG_REPO_PATH", os.getenv("BLOG_ROOT", Path(__file__).parent.parent)))


class GitHandler:
    """Git 작업 핸들러"""

    def __init__(self, repo_path: Path = BLOG_ROOT):
        self.repo_path = repo_path
        self._lock = threading.Lock()

    def _run_git(self, *args) -> tuple:
        """Git 명령어 실행"""
        try:
            result = subprocess.run(
                ["git"] + list(args),
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Git command timed out"
        except Exception as e:
            return -1, "", str(e)

    def get_status(self) -> Dict[str, Any]:
        """Git 상태 확인"""
        code, stdout, stderr = self._run_git("status", "--porcelain")

        if code != 0:
            return {"error": stderr, "clean": False}

        changes = stdout.strip().split("\n") if stdout.strip() else []
        return {
            "clean": len(changes) == 0,
            "changes": changes,
            "change_count": len(changes)
        }

    def sync_from_remote(self) -> Dict[str, Any]:
        """원격 저장소에서 동기화 (pull)"""
        with self._lock:
            # 먼저 fetch
            code, stdout, stderr = self._run_git("fetch", "origin")
            if code != 0:
                return {"success": False, "error": f"Fetch failed: {stderr}"}

            # pull
            code, stdout, stderr = self._run_git("pull", "origin", "main")
            if code != 0:
                # 충돌이나 다른 문제
                return {"success": False, "error": stderr, "output": stdout}

            return {
                "success": True,
                "message": "Successfully synced from remote",
                "output": stdout
            }

    def commit_and_push(
        self,
        message: str,
        files: list = None,
        author_name: str = "Blog API",
        author_email: str = "blog-api@fcoinfup.com"
    ) -> Dict[str, Any]:
        """
        변경사항을 commit하고 push

        Args:
            message: 커밋 메시지
            files: 특정 파일 목록 (None이면 모든 변경사항)
            author_name: 커밋 작성자 이름
            author_email: 커밋 작성자 이메일

        Returns:
            결과 딕셔너리
        """
        with self._lock:
            # 변경사항 확인
            status = self.get_status()
            if status["clean"]:
                return {"success": True, "message": "No changes to commit"}

            # 파일 추가
            if files:
                for file in files:
                    code, _, stderr = self._run_git("add", file)
                    if code != 0:
                        return {"success": False, "error": f"Failed to add {file}: {stderr}"}
            else:
                # content와 static만 추가 (설정 파일 제외)
                code, _, stderr = self._run_git("add", "content/", "static/")
                if code != 0:
                    return {"success": False, "error": f"Failed to add files: {stderr}"}

            # 변경사항이 있는지 다시 확인
            code, stdout, stderr = self._run_git("diff", "--cached", "--quiet")
            if code == 0:  # 변경사항 없음
                return {"success": True, "message": "No changes to commit after staging"}

            # 커밋
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            full_message = f"{message}\n\nCommitted by Blog API at {timestamp}"

            code, stdout, stderr = self._run_git(
                "-c", f"user.name={author_name}",
                "-c", f"user.email={author_email}",
                "commit", "-m", full_message
            )

            if code != 0:
                return {"success": False, "error": f"Commit failed: {stderr}"}

            # Push
            code, stdout, stderr = self._run_git("push", "origin", "main")

            if code != 0:
                return {
                    "success": False,
                    "error": f"Push failed: {stderr}",
                    "committed": True,
                    "commit_message": full_message
                }

            return {
                "success": True,
                "message": "Successfully committed and pushed",
                "commit_message": full_message,
                "changes": status["changes"]
            }

    def get_recent_commits(self, limit: int = 5) -> Dict[str, Any]:
        """최근 커밋 목록 조회"""
        code, stdout, stderr = self._run_git(
            "log", f"-{limit}", "--oneline", "--format=%h %s %ci"
        )

        if code != 0:
            return {"error": stderr}

        commits = []
        for line in stdout.strip().split("\n"):
            if line:
                parts = line.split(" ", 2)
                if len(parts) >= 3:
                    commits.append({
                        "hash": parts[0],
                        "message": parts[1] if len(parts) > 1 else "",
                        "date": parts[2] if len(parts) > 2 else ""
                    })

        return {"commits": commits}


# 전역 인스턴스
git_handler = GitHandler()


def auto_commit_push(message: str, files: list = None) -> Dict[str, Any]:
    """
    자동 커밋 및 푸시 (편의 함수)

    백그라운드에서 실행하거나 즉시 실행
    """
    return git_handler.commit_and_push(message, files)
