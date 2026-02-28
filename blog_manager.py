"""
Blog Manager - Git 기반 블로그 포스트 관리

독립적으로 Git 저장소를 관리합니다.
"""

import os
import re
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from functools import wraps

from logger_config import get_logger
from file_lock import git_lock
from git_handler import GitHandler

logger = get_logger(__name__)


def log_execution_time(func):
    """함수 실행 시간 로깅 데코레이터"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        func_name = func.__name__

        # 함수 진입 로그
        logger.debug(f"{func_name} started", extra={
            "function": func_name,
            "args_count": len(args),
            "kwargs": list(kwargs.keys())
        })

        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time

            # 성공 로그
            log_level = "info" if elapsed < 1.0 else "warning"
            getattr(logger, log_level)(f"{func_name} completed", extra={
                "function": func_name,
                "duration_ms": round(elapsed * 1000, 2),
                "success": result.get("success", True)
            })

            return result

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"{func_name} failed", extra={
                "function": func_name,
                "duration_ms": round(elapsed * 1000, 2),
                "error": str(e)
            }, exc_info=True)
            raise

    return wrapper

# 설정
BLOG_REPO_URL = os.getenv("BLOG_REPO_URL", "https://github.com/yarang/blogs.git")
BLOG_REPO_PATH = Path(os.getenv("BLOG_REPO_PATH", "/var/www/blog-repo"))
CONTENT_DIR = BLOG_REPO_PATH / "content" / "post"

# 지원하는 언어
SUPPORTED_LANGUAGES = ["ko", "en"]


class BlogManager:
    """블로그 포스트 관리자"""

    def __init__(self):
        # git_handler의 GitHandler 사용 (GitManager 대신)
        self.git = GitHandler(repo_path=BLOG_REPO_PATH)
        self._ensure_ready()
        logger.info("BlogManager initialized", extra={
            "repo_path": str(self.git.repo_path),
            "content_dir": str(CONTENT_DIR)
        })

    def _ensure_ready(self):
        """저장소 준비 확인"""
        logger.debug("Ensuring repository is ready")
        if not CONTENT_DIR.exists():
            logger.info("Content directory not found, initializing repository", extra={
                "content_dir": str(CONTENT_DIR)
            })
            self.git.ensure_repo()

    def _get_content_dir(self, language: str = "ko") -> Path:
        """언어별 컨텐츠 디렉토리 반환

        Hugo Stack 테마 규칙:
        - defaultContentLanguageInSubdir = false일 때
        - 기본 언어(ko): content/post/
        - 다른 언어(en): content/en/post/
        """
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {language}. Supported: {SUPPORTED_LANGUAGES}")

        # 모든 언어는 content/{lang}/post/ 구조 사용
        # hugo.toml에서 contentDir = "content/ko", "content/en" 등으로 설정됨
        return BLOG_REPO_PATH / "content" / language / "post"

    def _generate_filename(self, title: str, language: str = "ko") -> str:
        """파일명 생성"""
        content_dir = self._get_content_dir(language)
        today = datetime.now().strftime("%Y-%m-%d")
        slug = re.sub(r'[^\w\s-]', '', title.lower())
        slug = re.sub(r'[\s]+', '-', slug)[:50]

        existing = list(content_dir.glob(f"{today}-*.md"))
        num = len(existing) + 1

        while True:
            filename = f"{today}-{num:03d}-{slug}.md"
            if not (content_dir / filename).exists():
                return filename
            num += 1

    def sync(self) -> Dict:
        """Git 동기화"""
        if self.git.pull():
            return {"success": True, "message": "동기화 완료"}
        return {"success": False, "error": "동기화 실패"}

    def create_post(
        self,
        title: str,
        content: str,
        tags: List[str] = None,
        categories: List[str] = None,
        draft: bool = False,
        auto_push: bool = True,
        language: str = "ko"
    ) -> Dict:
        """포스트 생성"""
        start_time = time.time()

        logger.info("[BLOG_MANAGER] ========== CREATE POST START ==========")
        logger.info("[BLOG_MANAGER] Creating post", extra={
            "title": title[:100],
            "language": language,
            "draft": draft,
            "auto_push": auto_push,
            "tags_count": len(tags or []),
            "categories": categories
        })

        logger.info("[BLOG_MANAGER] Acquiring git lock...")
        with git_lock():
            logger.info("[BLOG_MANAGER] Git lock acquired")
            try:
                # 언어 유효성 검사
                if language not in SUPPORTED_LANGUAGES:
                    logger.warning("[BLOG_MANAGER] Unsupported language requested", extra={
                        "requested_language": language,
                        "supported_languages": SUPPORTED_LANGUAGES
                    })
                    return {
                        "success": False,
                        "error": f"Unsupported language: {language}. Supported: {SUPPORTED_LANGUAGES}"
                    }

                # Step 1: 동기화
                logger.info("[BLOG_MANAGER] Step 1: Syncing repository...")
                sync_start = time.time()
                self.git.pull()
                sync_elapsed = time.time() - sync_start
                logger.info(f"[BLOG_MANAGER] Sync completed ({round(sync_elapsed * 1000, 2)}ms)")

                # Step 2: 파일명 생성
                logger.info("[BLOG_MANAGER] Step 2: Generating filename...")
                tags = tags or []
                categories = categories or ["Development"]
                content_dir = self._get_content_dir(language)
                filename = self._generate_filename(title, language)

                logger.info("[BLOG_MANAGER] Generated filename", extra={"post_filename": filename, "content_dir": str(content_dir)})

                # Step 3: 파일 작성
                logger.info("[BLOG_MANAGER] Step 3: Writing file...")
                front_matter = f'''+++
title = "{title}"
date = {datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")}
draft = {str(draft).lower()}
tags = {json.dumps(tags)}
categories = {json.dumps(categories)}
ShowToc = true
TocOpen = true
+++

{content}'''

                content_dir.mkdir(parents=True, exist_ok=True)
                filepath = content_dir / filename
                filepath.write_text(front_matter, encoding="utf-8")

                content_length = len(content)
                logger.info("[BLOG_MANAGER] File written", extra={
                    "post_filename": filename,
                    "filepath": str(filepath),
                    "content_length": content_length
                })

                # 모든 언어는 content/{language}/post/ 사용
                relative_path = f"content/{language}/post/{filename}"

                result = {
                    "success": True,
                    "filename": filename,
                    "language": language,
                    "path": relative_path,
                    "message": f"포스트 생성: {filename}"
                }

                # Step 4: 자동 푸시
                if auto_push:
                    logger.info("[BLOG_MANAGER] Step 4: Auto-pushing new post...")
                    git_result = self.git.commit_and_push(
                        f"Add post: {title}",
                        [relative_path]
                    )
                    result["git"] = git_result
                    logger.info("[BLOG_MANAGER] Git result received", extra={"git_success": git_result.get("success")})
                else:
                    logger.info("[BLOG_MANAGER] Step 4: Skipping auto-push")

                elapsed = time.time() - start_time
                elapsed_ms = round(elapsed * 1000, 2)
                logger.info(f"[BLOG_MANAGER] ========== CREATE POST SUCCESS ({elapsed_ms}ms) ==========")
                logger.info("[BLOG_MANAGER] Post created successfully", extra={
                    "post_filename": filename,
                    "language": language,
                    "duration_ms": elapsed_ms,
                    "auto_pushed": auto_push and result.get("git", {}).get("success")
                })

                return result

            except Exception as e:
                elapsed = time.time() - start_time
                elapsed_ms = round(elapsed * 1000, 2)
                logger.error(f"[BLOG_MANAGER] ========== CREATE POST FAILED ({elapsed_ms}ms) ==========")
                logger.error("[BLOG_MANAGER] Failed to create post", extra={
                    "title": title[:100],
                    "duration_ms": elapsed_ms,
                    "error": str(e)
                }, exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

    def list_posts(self, limit: int = 20, offset: int = 0, language: str = None) -> Dict:
        """포스트 목록"""
        start_time = time.time()

        logger.debug("Listing posts", extra={
            "limit": limit,
            "offset": offset,
            "language": language
        })

        self.git.pull()

        posts = []

        # 언어 필터링
        if language:
            if language not in SUPPORTED_LANGUAGES:
                logger.warning("Unsupported language requested for list", extra={
                    "requested_language": language
                })
                return {"error": f"Unsupported language: {language}", "posts": [], "total": 0}
            content_dirs = [self._get_content_dir(language)]
        else:
            content_dirs = [self._get_content_dir(lang) for lang in SUPPORTED_LANGUAGES]

        for content_dir in content_dirs:
            if not content_dir.exists():
                logger.debug("Content directory not found", extra={"content_dir": str(content_dir)})
                continue

            for f in sorted(content_dir.glob("*.md"), reverse=True):
                try:
                    content = f.read_text(encoding="utf-8")
                    title = "Unknown"
                    for line in content.split("\n")[1:10]:
                        if line.startswith('title = '):
                            title = line.split('"')[1]
                            break

                    # 언어 감지
                    # 모든 언어: content/{lang}/post/ 구조
                    # f.parent.parent.name이 언어 코드 ("ko", "en")
                    parent_name = f.parent.parent.name
                    lang = parent_name if parent_name in SUPPORTED_LANGUAGES else "ko"

                    posts.append({
                        "filename": f.name,
                        "title": title,
                        "language": lang
                    })
                except Exception as e:
                    logger.warning("Failed to read post file", extra={
                        "post_filename": f.name,
                        "error": str(e)
                    })

        elapsed = time.time() - start_time
        result = {"posts": posts[offset:offset+limit], "total": len(posts)}

        logger.info("Posts listed", extra={
            "returned_count": len(result["posts"]),
            "total_count": result["total"],
            "duration_ms": round(elapsed * 1000, 2)
        })

        return result

    def get_post(self, filename: str, language: str = None) -> Dict:
        """포스트 조회"""
        # 언어가 지정되면 해당 언어 디렉토리에서 검색
        if language:
            if language not in SUPPORTED_LANGUAGES:
                return {"error": f"Unsupported language: {language}"}
            filepath = self._get_content_dir(language) / filename
        else:
            # 언어가 지정되지 않으면 모든 언어 디렉토리에서 검색
            filepath = None
            for lang in SUPPORTED_LANGUAGES:
                path = self._get_content_dir(lang) / filename
                if path.exists():
                    filepath = path
                    break

            if not filepath:
                return {"error": "파일 없음"}

        if not filepath.exists():
            return {"error": "파일 없음"}
        return {
            "filename": filename,
            "content": filepath.read_text(encoding="utf-8"),
            "language": language or filepath.parent.parent.name
        }

    def update_post(self, filename: str, content: str = None, auto_push: bool = True, language: str = None) -> Dict:
        """포스트 수정"""
        start_time = time.time()

        logger.info("Updating post", extra={
            "post_filename": filename,
            "language": language,
            "auto_push": auto_push,
            "content_provided": content is not None
        })

        with git_lock():
            try:
                # 언어가 지정되면 해당 언어 디렉토리에서 검색
                if language:
                    if language not in SUPPORTED_LANGUAGES:
                        logger.warning("Unsupported language for update", extra={
                            "post_filename": filename,
                            "requested_language": language
                        })
                        return {"success": False, "error": f"Unsupported language: {language}"}
                    filepath = self._get_content_dir(language) / filename
                else:
                    # 언어가 지정되지 않으면 모든 언어 디렉토리에서 검색
                    filepath = None
                    for lang in SUPPORTED_LANGUAGES:
                        path = self._get_content_dir(lang) / filename
                        if path.exists():
                            filepath = path
                            language = lang
                            break

                    if not filepath:
                        logger.warning("Post file not found for update", extra={"post_filename": filename})
                        return {"success": False, "error": "파일 없음"}

                if not filepath.exists():
                    logger.warning("Post file not found", extra={"filepath": str(filepath)})
                    return {"success": False, "error": "파일 없음"}

                if content:
                    filepath.write_text(content, encoding="utf-8")
                    logger.debug("Post content updated", extra={
                        "post_filename": filename,
                        "content_length": len(content)
                    })

                lang = filepath.parent.parent.name
                relative_path = f"content/{lang}/post/{filename}"

                result = {"success": True, "filename": filename, "language": lang}

                if auto_push:
                    logger.debug("Auto-pushing updated post", extra={"post_filename": filename})
                    result["git"] = self.git.commit_and_push(
                        f"Update post: {filename}",
                        [relative_path]
                    )

                elapsed = time.time() - start_time
                logger.info("Post updated successfully", extra={
                    "post_filename": filename,
                    "language": lang,
                    "duration_ms": round(elapsed * 1000, 2)
                })

                return result

            except Exception as e:
                elapsed = time.time() - start_time
                logger.error("Failed to update post", extra={
                    "post_filename": filename,
                    "duration_ms": round(elapsed * 1000, 2),
                    "error": str(e)
                }, exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

    def delete_post(self, filename: str, auto_push: bool = True, language: str = None) -> Dict:
        """포스트 삭제"""
        start_time = time.time()

        logger.info("Deleting post", extra={
            "post_filename": filename,
            "language": language,
            "auto_push": auto_push
        })

        with git_lock():
            try:
                # 언어가 지정되면 해당 언어 디렉토리에서 검색
                if language:
                    if language not in SUPPORTED_LANGUAGES:
                        logger.warning("Unsupported language for delete", extra={
                            "post_filename": filename,
                            "requested_language": language
                        })
                        return {"success": False, "error": f"Unsupported language: {language}"}
                    filepath = self._get_content_dir(language) / filename
                else:
                    # 언어가 지정되지 않으면 모든 언어 디렉토리에서 검색
                    filepath = None
                    for lang in SUPPORTED_LANGUAGES:
                        path = self._get_content_dir(lang) / filename
                        if path.exists():
                            filepath = path
                            language = lang
                            break

                    if not filepath:
                        logger.warning("Post file not found for delete", extra={"post_filename": filename})
                        return {"success": False, "error": "파일 없음"}

                if not filepath.exists():
                    logger.warning("Post file not found", extra={"filepath": str(filepath)})
                    return {"success": False, "error": "파일 없음"}

                lang = filepath.parent.parent.name
                relative_path = f"content/{lang}/post/{filename}"

                filepath.unlink()
                logger.debug("Post file deleted", extra={"post_filename": filename, "language": lang})

                result = {"success": True, "message": "삭제 완료", "language": lang}

                if auto_push:
                    logger.debug("Auto-pushing after delete", extra={"post_filename": filename})
                    result["git"] = self.git.commit_and_push(
                        f"Delete post: {filename}"
                    )

                elapsed = time.time() - start_time
                logger.info("Post deleted successfully", extra={
                    "post_filename": filename,
                    "language": lang,
                    "duration_ms": round(elapsed * 1000, 2)
                })

                return result

            except Exception as e:
                elapsed = time.time() - start_time
                logger.error("Failed to delete post", extra={
                    "post_filename": filename,
                    "duration_ms": round(elapsed * 1000, 2),
                    "error": str(e)
                }, exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }

    def search_posts(self, query: str) -> Dict:
        """
        포스트 검색 (모든 언어 지원)

        한국어와 영어 포스트를 모두 검색합니다.
        """
        start_time = time.time()

        logger.info("Starting post search", extra={
            "query": query,
            "query_length": len(query)
        })

        self.git.pull()

        results = []
        query_lower = query.lower()
        files_scanned = 0

        # 모든 언어 디렉토리 검색
        for lang in SUPPORTED_LANGUAGES:
            content_dir = self._get_content_dir(lang)
            if not content_dir.exists():
                logger.debug("Content directory not found for search", extra={
                    "language": lang,
                    "content_dir": str(content_dir)
                })
                continue

            for f in content_dir.glob("*.md"):
                files_scanned += 1
                try:
                    content = f.read_text(encoding="utf-8").lower()
                    if query_lower in content:
                        results.append({
                            "filename": f.name,
                            "language": lang,
                            "relevance": content.count(query_lower)
                        })
                except Exception as e:
                    logger.warning("Failed to read file for search", extra={
                        "post_filename": f.name,
                        "error": str(e)
                    })

        results.sort(key=lambda x: x["relevance"], reverse=True)

        elapsed = time.time() - start_time
        logger.info("Search completed", extra={
            "query": query,
            "files_scanned": files_scanned,
            "result_count": len(results),
            "returned_count": len(results[:20]),
            "duration_ms": round(elapsed * 1000, 2)
        })

        return {"results": results[:20], "query": query, "total": len(results)}

    def get_translation_status(self) -> Dict:
        """번역 상태 확인"""
        start_time = time.time()

        logger.debug("Getting translation status")

        self.git.pull()

        # Stack 테마 구조: 한국어는 content/post/, 영어는 content/en/post/
        ko_dir = self._get_content_dir("ko")  # content/post/
        en_dir = self._get_content_dir("en")  # content/en/post/

        ko_posts = set(f.stem for f in ko_dir.glob("*.md")) if ko_dir.exists() else set()
        en_posts = set(f.stem for f in en_dir.glob("*.md")) if en_dir.exists() else set()

        # 번역 필요한 포스트 (한국어에만 있는 것)
        needs_translation = ko_posts - en_posts

        # 영어에만 있는 포스트
        en_only = en_posts - ko_posts

        result = {
            "korean_posts": len(ko_posts),
            "english_posts": len(en_posts),
            "needs_translation": list(needs_translation),
            "needs_translation_count": len(needs_translation),
            "english_only": list(en_only),
            "synced": len(needs_translation) == 0 and len(en_only) == 0
        }

        logger.debug("Translation status retrieved", extra={
            "korean_count": len(ko_posts),
            "english_count": len(en_posts),
            "needs_translation": len(needs_translation)
        })

        return result

    def sync_translations(self) -> Dict:
        """한국어/영어 포스트 동기화"""
        from translator import translator

        start_time = time.time()

        logger.info("Starting translation sync")

        self.git.pull()

        status = self.get_translation_status()
        needs_count = len(status["needs_translation"])

        logger.info("Translation sync status", extra={
            "posts_needing_translation": needs_count,
            "korean_posts": status["korean_posts"],
            "english_posts": status["english_posts"]
        })

        results = {
            "translated": [],
            "failed": [],
            "skipped": []
        }

        if needs_count == 0:
            logger.info("No posts need translation")
            return {
                **results,
                "summary": {
                    "translated": 0,
                    "failed": 0,
                    "skipped": 0
                },
                "message": "All posts are already synced"
            }

        # Stack 테마 구조: 한국어는 content/post/, 영어는 content/en/post/
        ko_dir = self._get_content_dir("ko")  # content/post/
        en_dir = self._get_content_dir("en")  # content/en/post/
        en_dir.mkdir(parents=True, exist_ok=True)

        for idx, filename in enumerate(status["needs_translation"], 1):
            ko_file = ko_dir / f"{filename}.md"
            en_file = en_dir / f"{filename}.md"

            if not ko_file.exists():
                logger.warning("Source file not found, skipping", extra={"post_filename": filename})
                results["skipped"].append(filename)
                continue

            # 한국어 포스트 읽기
            ko_content = ko_file.read_text(encoding="utf-8")

            # 번역
            logger.info(f"Translating post", extra={
                "post_filename": filename,
                "progress": f"{idx}/{needs_count}"
            })

            trans_result = translator.translate(
                content=ko_content,
                source="ko",
                target="en"
            )

            if trans_result.get("success"):
                # 영어 포스트 저장
                en_file.write_text(trans_result["translated"], encoding="utf-8")
                results["translated"].append(filename)
                logger.info("Translation successful", extra={"post_filename": filename})
            else:
                results["failed"].append({
                    "filename": filename,
                    "error": trans_result.get("error")
                })
                logger.error("Translation failed", extra={
                    "post_filename": filename,
                    "error": trans_result.get("error")
                })

        # Git 커밋
        if results["translated"]:
            logger.info("Committing translated posts", extra={
                "count": len(results["translated"])
            })
            git_result = self.git.commit_and_push(
                f"Auto-translate {len(results['translated'])} posts to English",
                [f"content/en/post/*.md"]
            )
            results["git"] = git_result

        results["summary"] = {
            "translated": len(results["translated"]),
            "failed": len(results["failed"]),
            "skipped": len(results["skipped"])
        }

        elapsed = time.time() - start_time
        logger.info("Translation sync completed", extra={
            "translated": results["summary"]["translated"],
            "failed": results["summary"]["failed"],
            "skipped": results["summary"]["skipped"],
            "duration_sec": round(elapsed, 2)
        })

        return results


# 전역 인스턴스
blog_manager = BlogManager()
