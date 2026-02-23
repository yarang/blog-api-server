"""
Blog Manager - Git 기반 블로그 포스트 관리

독립적으로 Git 저장소를 관리합니다.
"""

import os
import re
import json
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# 설정
BLOG_REPO_URL = os.getenv("BLOG_REPO_URL", "https://github.com/yarang/blogs.git")
BLOG_REPO_PATH = Path(os.getenv("BLOG_REPO_PATH", "/var/www/blog-repo"))
CONTENT_DIR = BLOG_REPO_PATH / "content" / "post"

# 지원하는 언어
SUPPORTED_LANGUAGES = ["ko", "en"]

# 동기화 락
_lock = threading.Lock()


class GitManager:
    """Git 저장소 관리자"""

    def __init__(self, repo_path: Path = BLOG_REPO_PATH, repo_url: str = BLOG_REPO_URL):
        self.repo_path = repo_path
        self.repo_url = repo_url

    def ensure_repo(self) -> bool:
        """저장소가 있으면 pull, 없으면 clone"""
        if self.repo_path.exists():
            return self.pull()
        else:
            return self.clone()

    def clone(self) -> bool:
        """저장소 클론"""
        try:
            self.repo_path.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["git", "clone", self.repo_url, str(self.repo_path)],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                logger.info(f"Cloned repo to {self.repo_path}")
                return True
            logger.error(f"Clone failed: {result.stderr}")
            return False
        except Exception as e:
            logger.error(f"Clone error: {e}")
            return False

    def pull(self) -> bool:
        """최신 내용 가져오기"""
        try:
            result = subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=self.repo_path, capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                logger.info("Pulled latest changes")
                return True
            logger.error(f"Pull failed: {result.stderr}")
            return False
        except Exception as e:
            logger.error(f"Pull error: {e}")
            return False

    def commit_and_push(self, message: str, files: List[str] = None) -> Dict:
        """커밋하고 푸시"""
        with _lock:
            try:
                # 파일 추가
                if files:
                    for f in files:
                        subprocess.run(
                            ["git", "add", f],
                            cwd=self.repo_path, capture_output=True
                        )
                else:
                    subprocess.run(
                        ["git", "add", "content/", "static/"],
                        cwd=self.repo_path, capture_output=True
                    )

                # 변경사항 확인
                result = subprocess.run(
                    ["git", "diff", "--cached", "--quiet"],
                    cwd=self.repo_path, capture_output=True
                )
                if result.returncode == 0:
                    return {"success": True, "message": "변경사항 없음"}

                # 커밋
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                full_msg = f"{message}\n\nBy Blog API at {timestamp}"
                result = subprocess.run(
                    ["git", "commit", "-m", full_msg],
                    cwd=self.repo_path, capture_output=True, text=True
                )
                if result.returncode != 0:
                    return {"success": False, "error": f"Commit 실패: {result.stderr}"}

                # 푸시
                result = subprocess.run(
                    ["git", "push", "origin", "main"],
                    cwd=self.repo_path, capture_output=True, text=True, timeout=60
                )
                if result.returncode != 0:
                    return {"success": False, "error": f"Push 실패: {result.stderr}"}

                return {"success": True, "message": "커밋 및 푸시 완료"}

            except Exception as e:
                return {"success": False, "error": str(e)}


class BlogManager:
    """블로그 포스트 관리자"""

    def __init__(self):
        self.git = GitManager()
        self._ensure_ready()

    def _ensure_ready(self):
        """저장소 준비 확인"""
        if not CONTENT_DIR.exists():
            self.git.ensure_repo()

    def _get_content_dir(self, language: str = "ko") -> Path:
        """언어별 컨텐츠 디렉토리 반환"""
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {language}. Supported: {SUPPORTED_LANGUAGES}")
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
        with _lock:
            # 언어 유효성 검사
            if language not in SUPPORTED_LANGUAGES:
                return {
                    "success": False,
                    "error": f"Unsupported language: {language}. Supported: {SUPPORTED_LANGUAGES}"
                }

            # 동기화
            self.git.pull()

            tags = tags or []
            categories = categories or ["Development"]
            content_dir = self._get_content_dir(language)
            filename = self._generate_filename(title, language)

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

            relative_path = f"content/{language}/post/{filename}"

            result = {
                "success": True,
                "filename": filename,
                "language": language,
                "path": relative_path,
                "message": f"포스트 생성: {filename}"
            }

            # 자동 푸시
            if auto_push:
                git_result = self.git.commit_and_push(
                    f"Add post: {title}",
                    [relative_path]
                )
                result["git"] = git_result

            return result

    def list_posts(self, limit: int = 20, offset: int = 0, language: str = None) -> Dict:
        """포스트 목록"""
        self.git.pull()

        posts = []

        # 언어 필터링
        if language:
            if language not in SUPPORTED_LANGUAGES:
                return {"error": f"Unsupported language: {language}", "posts": [], "total": 0}
            content_dirs = [self._get_content_dir(language)]
        else:
            content_dirs = [self._get_content_dir(lang) for lang in SUPPORTED_LANGUAGES]

        for content_dir in content_dirs:
            if not content_dir.exists():
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
                    lang = f.parent.parent.name  # ko or en

                    posts.append({
                        "filename": f.name,
                        "title": title,
                        "language": lang
                    })
                except:
                    pass

        return {"posts": posts[offset:offset+limit], "total": len(posts)}

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
        with _lock:
            # 언어가 지정되면 해당 언어 디렉토리에서 검색
            if language:
                if language not in SUPPORTED_LANGUAGES:
                    return {"success": False, "error": f"Unsupported language: {language}"}
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
                    return {"success": False, "error": "파일 없음"}

            if not filepath.exists():
                return {"success": False, "error": "파일 없음"}

            if content:
                filepath.write_text(content, encoding="utf-8")

            lang = filepath.parent.parent.name
            relative_path = f"content/{lang}/post/{filename}"

            result = {"success": True, "filename": filename, "language": lang}

            if auto_push:
                result["git"] = self.git.commit_and_push(
                    f"Update post: {filename}",
                    [relative_path]
                )

            return result

    def delete_post(self, filename: str, auto_push: bool = True, language: str = None) -> Dict:
        """포스트 삭제"""
        with _lock:
            # 언어가 지정되면 해당 언어 디렉토리에서 검색
            if language:
                if language not in SUPPORTED_LANGUAGES:
                    return {"success": False, "error": f"Unsupported language: {language}"}
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
                    return {"success": False, "error": "파일 없음"}

            if not filepath.exists():
                return {"success": False, "error": "파일 없음"}

            lang = filepath.parent.parent.name
            relative_path = f"content/{lang}/post/{filename}"

            filepath.unlink()

            result = {"success": True, "message": "삭제 완료", "language": lang}

            if auto_push:
                result["git"] = self.git.commit_and_push(
                    f"Delete post: {filename}"
                )

            return result

    def search_posts(self, query: str) -> Dict:
        """포스트 검색"""
        self.git.pull()

        results = []
        query_lower = query.lower()

        for f in CONTENT_DIR.glob("*.md"):
            content = f.read_text(encoding="utf-8").lower()
            if query_lower in content:
                results.append({
                    "filename": f.name,
                    "relevance": content.count(query_lower)
                })

        results.sort(key=lambda x: x["relevance"], reverse=True)
        return {"results": results[:20], "query": query}

    def get_translation_status(self) -> Dict:
        """번역 상태 확인"""
        self.git.pull()

        ko_dir = BLOG_REPO_PATH / "content" / "ko" / "post"
        en_dir = BLOG_REPO_PATH / "content" / "en" / "post"

        ko_posts = set(f.stem for f in ko_dir.glob("*.md")) if ko_dir.exists() else set()
        en_posts = set(f.stem for f in en_dir.glob("*.md")) if en_dir.exists() else set()

        # 번역 필요한 포스트 (한국어에만 있는 것)
        needs_translation = ko_posts - en_posts

        # 영어에만 있는 포스트
        en_only = en_posts - ko_posts

        return {
            "korean_posts": len(ko_posts),
            "english_posts": len(en_posts),
            "needs_translation": list(needs_translation),
            "needs_translation_count": len(needs_translation),
            "english_only": list(en_only),
            "synced": len(needs_translation) == 0 and len(en_only) == 0
        }

    def sync_translations(self) -> Dict:
        """한국어/영어 포스트 동기화"""
        from translator import translator

        self.git.pull()

        status = self.get_translation_status()
        results = {
            "translated": [],
            "failed": [],
            "skipped": []
        }

        ko_dir = BLOG_REPO_PATH / "content" / "ko" / "post"
        en_dir = BLOG_REPO_PATH / "content" / "en" / "post"
        en_dir.mkdir(parents=True, exist_ok=True)

        for filename in status["needs_translation"]:
            ko_file = ko_dir / f"{filename}.md"
            en_file = en_dir / f"{filename}.md"

            if not ko_file.exists():
                results["skipped"].append(filename)
                continue

            # 한국어 포스트 읽기
            ko_content = ko_file.read_text(encoding="utf-8")

            # 번역
            logger.info(f"Translating {filename}...")
            trans_result = translator.translate(
                content=ko_content,
                source="ko",
                target="en"
            )

            if trans_result.get("success"):
                # 영어 포스트 저장
                en_file.write_text(trans_result["translated"], encoding="utf-8")
                results["translated"].append(filename)
                logger.info(f"Translated: {filename}")
            else:
                results["failed"].append({
                    "filename": filename,
                    "error": trans_result.get("error")
                })
                logger.error(f"Translation failed for {filename}: {trans_result.get('error')}")

        # Git 커밋
        if results["translated"]:
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

        return results


# 전역 인스턴스
blog_manager = BlogManager()
