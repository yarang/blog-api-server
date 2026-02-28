"""
Git 작업 핸들러
자동 commit 및 push를 처리합니다.
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from logger_config import get_logger
from file_lock import git_lock

logger = get_logger(__name__)

# 블로그 루트 경로
BLOG_ROOT = Path(os.getenv("BLOG_REPO_PATH", os.getenv("BLOG_ROOT", Path(__file__).parent.parent)))


class GitHandler:
    """Git 작업 핸들러"""

    def __init__(self, repo_path: Path = BLOG_ROOT):
        self.repo_path = repo_path
        logger.debug("GitHandler initialized", extra={"repo_path": str(repo_path)})

    def _run_git(self, *args) -> Tuple[int, str, str]:
        """Git 명령어 실행"""
        import time
        cmd = ["git"] + list(args)
        start_time = time.time()
        cmd_str = " ".join(cmd)

        logger.info(f"[GIT] Starting command: {cmd_str}", extra={
            "command": cmd_str,
            "args_count": len(args),
            "repo_path": str(self.repo_path)
        })

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )

            elapsed = time.time() - start_time
            elapsed_ms = round(elapsed * 1000, 2)

            if result.returncode != 0:
                logger.warning(f"[GIT] Command FAILED: {cmd_str} ({elapsed_ms}ms)", extra={
                    "command": cmd_str,
                    "returncode": result.returncode,
                    "stderr": result.stderr[:500],
                    "stdout": result.stdout[:200],
                    "duration_ms": elapsed_ms
                })
            else:
                logger.info(f"[GIT] Command OK: {cmd_str} ({elapsed_ms}ms)", extra={
                    "command": cmd_str,
                    "duration_ms": elapsed_ms,
                    "stdout_lines": len(result.stdout.split('\n')) if result.stdout else 0
                })

            return result.returncode, result.stdout, result.stderr

        except subprocess.TimeoutExpired as e:
            elapsed = time.time() - start_time
            logger.error(f"[GIT] TIMEOUT: {cmd_str} (>60s)", extra={
                "command": cmd_str,
                "timeout_sec": 60,
                "duration_ms": round(elapsed * 1000, 2),
                "error_type": "TimeoutExpired"
            })
            return -1, "", "Git command timed out"
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[GIT] ERROR: {cmd_str} - {str(e)}", extra={
                "command": cmd_str,
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": round(elapsed * 1000, 2)
            })
            return -1, "", str(e)

    def ensure_repo(self) -> bool:
        """
        저장소가 있으면 pull, 없으면 clone

        Returns:
            성공 여부
        """
        if self.repo_path.exists():
            return self.pull() is not None
        else:
            return self.clone()

    def clone(self) -> bool:
        """
        저장소 클론

        Returns:
            성공 여부
        """
        start_time = time.time()
        logger.info("[GIT] Starting repository clone", extra={
            "repo_url": os.getenv("BLOG_REPO_URL", ""),
            "target_path": str(self.repo_path)
        })

        try:
            self.repo_path.parent.mkdir(parents=True, exist_ok=True)
            repo_url = os.getenv("BLOG_REPO_URL", "https://github.com/yarang/blogs.git")
            result = subprocess.run(
                ["git", "clone", repo_url, str(self.repo_path)],
                capture_output=True, text=True, timeout=120
            )

            elapsed = time.time() - start_time

            if result.returncode == 0:
                logger.info("[GIT] Repository cloned successfully", extra={
                    "repo_path": str(self.repo_path),
                    "duration_sec": round(elapsed, 2)
                })
                return True

            logger.error("[GIT] Repository clone failed", extra={
                "stderr": result.stderr,
                "duration_sec": round(elapsed, 2)
            })
            return False

        except subprocess.TimeoutExpired:
            logger.error("[GIT] Repository clone timeout", extra={"timeout_sec": 120})
            return False
        except Exception as e:
            logger.error("[GIT] Repository clone error", extra={"error": str(e)}, exc_info=True)
            return False

    def pull(self) -> Optional[bool]:
        """
        최신 내용 가져오기 (pull)

        Returns:
            성공 시 True, 실패 시 False, 에러 시 None
        """
        start_time = time.time()
        logger.info("[GIT] Starting git pull", extra={"repo_path": str(self.repo_path)})

        code, stdout, stderr = self._run_git("pull", "origin", "main")

        elapsed = time.time() - start_time
        elapsed_ms = round(elapsed * 1000, 2)

        if code == 0:
            has_changes = "Already up to date" not in stdout
            logger.info(f"[GIT] Git pull completed ({elapsed_ms}ms)", extra={
                "repo_path": str(self.repo_path),
                "has_changes": has_changes,
                "stdout": stdout[:200] if stdout else ""
            })
            return True

        logger.warning(f"[GIT] Git pull failed ({elapsed_ms}ms)", extra={
            "stderr": stderr,
            "stdout": stdout[:200] if stdout else ""
        })
        return False

    def get_status(self) -> Dict[str, Any]:
        """Git 상태 확인"""
        logger.debug("Getting git status")

        code, stdout, stderr = self._run_git("status", "--porcelain")

        if code != 0:
            logger.error("Failed to get git status", extra={"stderr": stderr})
            return {"error": stderr, "clean": False}

        changes = stdout.strip().split("\n") if stdout.strip() else []
        result = {
            "clean": len(changes) == 0,
            "changes": changes,
            "change_count": len(changes)
        }

        logger.debug("Git status retrieved", extra={
            "clean": result["clean"],
            "change_count": result["change_count"]
        })

        return result

    def sync_from_remote(self) -> Dict[str, Any]:
        """원격 저장소에서 동기화 (pull)"""
        start_time = time.time()
        logger.info("[SYNC] Starting sync from remote")

        logger.info("[SYNC] Acquiring git lock...")
        with git_lock():
            logger.info("[SYNC] Git lock acquired")

            # 먼저 fetch
            logger.info("[SYNC] Step 1: Fetching from origin...")
            code, stdout, stderr = self._run_git("fetch", "origin")
            if code != 0:
                logger.error("[SYNC] Fetch failed", extra={"stderr": stderr})
                return {"success": False, "error": f"Fetch failed: {stderr}"}

            logger.info("[SYNC] Fetch completed")

            # pull
            logger.info("[SYNC] Step 2: Pulling from origin/main...")
            code, stdout, stderr = self._run_git("pull", "origin", "main")
            if code != 0:
                logger.error("[SYNC] Pull failed", extra={"stderr": stderr, "stdout": stdout})
                # 충돌이나 다른 문제
                return {"success": False, "error": stderr, "output": stdout}

            elapsed = time.time() - start_time
            logger.info(f"[SYNC] Sync completed successfully ({round(elapsed * 1000, 2)}ms)", extra={
                "duration_ms": round(elapsed * 1000, 2)
            })

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
        start_time = time.time()

        logger.info(f"[COMMIT] Starting commit and push: {message[:50]}...", extra={
            "message": message[:100],
            "files": files,
            "author": author_name
        })

        logger.info("[COMMIT] Acquiring git lock...")
        with git_lock():
            logger.info("[COMMIT] Git lock acquired")

            # Step 1: 변경사항 확인
            logger.info("[COMMIT] Step 1: Checking git status...")
            status = self.get_status()
            if status["clean"]:
                elapsed = round((time.time() - start_time) * 1000, 2)
                logger.info(f"[COMMIT] No changes to commit ({elapsed}ms)")
                return {"success": True, "message": "No changes to commit"}

            logger.info(f"[COMMIT] Changes detected: {status['change_count']} files", extra={
                "change_count": status["change_count"],
                "changes": status["changes"][:5]
            })

            # Step 2: 파일 추가
            logger.info("[COMMIT] Step 2: Staging files...")
            if files:
                for file in files:
                    logger.info(f"[COMMIT] Staging file: {file}")
                    code, _, stderr = self._run_git("add", file)
                    if code != 0:
                        logger.error(f"[COMMIT] Failed to add file: {file}", extra={"stderr": stderr})
                        return {"success": False, "error": f"Failed to add {file}: {stderr}"}
                logger.info(f"[COMMIT] Files staged: {files}")
            else:
                logger.info("[COMMIT] Staging content/ and static/")
                code, _, stderr = self._run_git("add", "content/", "static/")
                if code != 0:
                    logger.error("[COMMIT] Failed to add directories", extra={"stderr": stderr})
                    return {"success": False, "error": f"Failed to add files: {stderr}"}
                logger.info("[COMMIT] Directories staged")

            # Step 3: 변경사항 확인
            logger.info("[COMMIT] Step 3: Verifying staged changes...")
            code, stdout, stderr = self._run_git("diff", "--cached", "--quiet")
            if code == 0:  # 변경사항 없음
                logger.info("[COMMIT] No changes after staging")
                return {"success": True, "message": "No changes to commit after staging"}

            # Step 4: 커밋
            logger.info("[COMMIT] Step 4: Creating commit...")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            full_message = f"{message}\n\nCommitted by Blog API at {timestamp}"

            code, stdout, stderr = self._run_git(
                "-c", f"user.name={author_name}",
                "-c", f"user.email={author_email}",
                "commit", "-m", full_message
            )

            if code != 0:
                logger.error("[COMMIT] Commit failed", extra={"stderr": stderr})
                return {"success": False, "error": f"Commit failed: {stderr}"}

            logger.info(f"[COMMIT] Commit created: {message[:50]}")

            # Step 5: Push
            logger.info("[COMMIT] Step 5: Pushing to origin/main...")
            push_start = time.time()
            code, stdout, stderr = self._run_git("push", "origin", "main")
            push_elapsed = time.time() - push_start

            if code != 0:
                logger.error("[COMMIT] Push failed", extra={
                    "stderr": stderr,
                    "push_duration_ms": round(push_elapsed * 1000, 2)
                })
                return {
                    "success": False,
                    "error": f"Push failed: {stderr}",
                    "committed": True,
                    "commit_message": full_message
                }

            total_elapsed = time.time() - start_time
            logger.info(f"[COMMIT] SUCCESS: Commit and push completed ({round(total_elapsed * 1000, 2)}ms)", extra={
                "message": message[:100],
                "push_duration_ms": round(push_elapsed * 1000, 2),
                "total_duration_ms": round(total_elapsed * 1000, 2)
            })

            return {
                "success": True,
                "message": "Successfully committed and pushed",
                "commit_message": full_message,
                "changes": status["changes"]
            }

    def get_recent_commits(self, limit: int = 5) -> Dict[str, Any]:
        """최근 커밋 목록 조회"""
        logger.debug("Getting recent commits", extra={"limit": limit})

        code, stdout, stderr = self._run_git(
            "log", f"-{limit}", "--oneline", "--format=%h %s %ci"
        )

        if code != 0:
            logger.error("Failed to get recent commits", extra={"stderr": stderr})
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

        logger.debug("Recent commits retrieved", extra={"count": len(commits)})
        return {"commits": commits}


# 전역 인스턴스
git_handler = GitHandler()


def auto_commit_push(message: str, files: list = None) -> Dict[str, Any]:
    """
    자동 커밋 및 푸시 (편의 함수)

    백그라운드에서 실행하거나 즉시 실행
    """
    return git_handler.commit_and_push(message, files)
