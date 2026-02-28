#!/usr/bin/env python3
"""
검색 기능 테스트 - 다국어 지원 검증

P0 우선순위: search_posts()가 모든 언어 디렉토리(ko, en)를 검색하는지 확인
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from typing import Dict
import tempfile
import shutil

# blog_api_server 디렉토리를 경로에 추가
import sys
sys.path.insert(0, '/Users/yarang/workspaces/agent_dev/blog-api-server')

from blog_manager import BlogManager, SUPPORTED_LANGUAGES


def create_temp_repo_with_posts():
    """테스트용 임시 저장소와 샘플 포스트 생성"""
    temp_dir = tempfile.mkdtemp()
    repo_path = Path(temp_dir)

    # 디렉토리 구조 생성
    # 한국어: content/post/
    # 영어: content/en/post/
    (repo_path / "content" / "post").mkdir(parents=True)
    (repo_path / "content" / "en" / "post").mkdir(parents=True)

    ko_dir = repo_path / "content" / "post"
    en_dir = repo_path / "content" / "en" / "post"

    # 한국어 포스트들
    (ko_dir / "python-tutorial.md").write_text("""+++
title = "Python 튜토리얼"
+++

Python은 강력한 프로그래밍 언어입니다.
이 튜토리얼에서는 Python 기초를 배웁니다.
""", encoding="utf-8")

    (ko_dir / "javascript-guide.md").write_text("""+++
title = "JavaScript 가이드"
+++

JavaScript는 웹 개발에 필수적인 언어입니다.
""", encoding="utf-8")

    (ko_dir / "rust-intro.md").write_text("""+++
title = "Rust 입문"
+++

Rust는 시스템 프로그래밍 언어입니다.
""", encoding="utf-8")

    # 영어 포스트들
    (en_dir / "python-tutorial.md").write_text("""+++
title = "Python Tutorial"
+++

Python is a powerful programming language.
This tutorial covers Python basics.
""", encoding="utf-8")

    (en_dir / "golang-basics.md").write_text("""+++
title = "Go Basics"
+++

Go is a modern programming language.
""", encoding="utf-8")

    return repo_path


def search_posts_with_repo(repo_path: Path, query: str) -> Dict:
    """테스트용 검색 헬퍼 함수 - 지정된 repo_path 사용"""
    results = []
    query_lower = query.lower()

    # 모든 언어 디렉토리 검색
    for lang in SUPPORTED_LANGUAGES:
        if lang == "ko":
            content_dir = repo_path / "content" / "post"
        else:
            content_dir = repo_path / "content" / lang / "post"

        if not content_dir.exists():
            continue

        for f in content_dir.glob("*.md"):
            try:
                content = f.read_text(encoding="utf-8").lower()
                if query_lower in content:
                    results.append({
                        "filename": f.name,
                        "language": lang,
                        "relevance": content.count(query_lower)
                    })
            except Exception:
                pass

    results.sort(key=lambda x: x["relevance"], reverse=True)
    return {"results": results[:20], "query": query, "total": len(results)}


class TestSearchPostsMultiLanguage:
    """search_posts() 다국어 지원 테스트"""

    def test_search_all_languages(self):
        """모든 언어 디렉토리에서 검색하는지 확인"""
        repo_path = create_temp_repo_with_posts()
        try:
            result = search_posts_with_repo(repo_path, "Python")

            # 한국어와 영어 포스트 모두 검색되어야 함
            assert "results" in result
            assert len(result["results"]) >= 2

            # 결과에 언어 정보가 포함되어야 함
            languages = {r["language"] for r in result["results"]}
            assert "ko" in languages
            assert "en" in languages
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)

    def test_search_korean_only(self):
        """한국어 포스트만 검색되는지 확인"""
        repo_path = create_temp_repo_with_posts()
        try:
            result = search_posts_with_repo(repo_path, "튜토리얼")

            # "튜토리얼"은 한국어 포스트에만 있음
            assert "results" in result
            assert len(result["results"]) == 1
            assert result["results"][0]["language"] == "ko"
            assert "python-tutorial.md" in result["results"][0]["filename"]
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)

    def test_search_english_only(self):
        """영어 포스트만 검색되는지 확인"""
        repo_path = create_temp_repo_with_posts()
        try:
            result = search_posts_with_repo(repo_path, "modern")

            # "modern"은 영어 포스트에만 있음
            assert "results" in result
            assert len(result["results"]) == 1
            assert result["results"][0]["language"] == "en"
            assert "golang-basics.md" in result["results"][0]["filename"]
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)

    def test_search_relevance_sorting(self):
        """검색 결과가 relevance 순으로 정렬되는지 확인"""
        repo_path = create_temp_repo_with_posts()
        try:
            result = search_posts_with_repo(repo_path, "Python")

            # relevance 순으로 정렬되어야 함 (내림차순)
            if len(result["results"]) > 1:
                relevances = [r["relevance"] for r in result["results"]]
                assert relevances == sorted(relevances, reverse=True)
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)

    def test_search_empty_query(self):
        """빈 쿼리 처리 확인"""
        repo_path = create_temp_repo_with_posts()
        try:
            result = search_posts_with_repo(repo_path, "")

            # 빈 쿼리도 처리되어야 함 (모든 결과 반환 또는 빈 결과)
            assert "results" in result
            assert isinstance(result["results"], list)
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)

    def test_search_no_results(self):
        """검색 결과가 없는 경우 확인"""
        repo_path = create_temp_repo_with_posts()
        try:
            result = search_posts_with_repo(repo_path, "nonexistentcontent123")

            assert "results" in result
            assert len(result["results"]) == 0
            assert result["total"] == 0
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)

    def test_search_result_structure(self):
        """검색 결과 구조 확인"""
        repo_path = create_temp_repo_with_posts()
        try:
            result = search_posts_with_repo(repo_path, "Python")

            # 필수 필드 확인
            assert "results" in result
            assert "query" in result
            assert "total" in result

            # 결과 항목 구조 확인
            for item in result["results"]:
                assert "filename" in item
                assert "language" in item
                assert "relevance" in item
                assert item["language"] in SUPPORTED_LANGUAGES
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)

    def test_search_case_insensitive(self):
        """대소문자 구분 없이 검색하는지 확인"""
        repo_path = create_temp_repo_with_posts()
        try:
            result_lower = search_posts_with_repo(repo_path, "python")
            result_upper = search_posts_with_repo(repo_path, "PYTHON")
            result_mixed = search_posts_with_repo(repo_path, "PyThOn")

            # 모든 경우 같은 결과가 나와야 함
            assert result_lower["total"] == result_upper["total"]
            assert result_upper["total"] == result_mixed["total"]
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)

    def test_search_both_languages_have_same_filename(self):
        """한국어와 영어에 같은 파일명이 있을 때 검색 확인"""
        repo_path = create_temp_repo_with_posts()
        try:
            result = search_posts_with_repo(repo_path, "Python")

            # python-tutorial.md는 한국어와 영어에 모두 있음
            python_results = [r for r in result["results"] if "python-tutorial.md" in r["filename"]]
            assert len(python_results) == 2

            # 두 결과 모두 다른 언어로 표시되어야 함
            languages = {r["language"] for r in python_results}
            assert languages == {"ko", "en"}
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)


class TestSearchIntegration:
    """검색 기능 통합 테스트"""

    def test_supported_languages_constant(self):
        """SUPPORTED_LANGUAGES 상수 확인"""
        assert "ko" in SUPPORTED_LANGUAGES
        assert "en" in SUPPORTED_LANGUAGES

    def test_get_content_dir_for_all_languages(self):
        """모든 지원 언어에 대해 content 디렉토리를 가져올 수 있는지 확인"""
        manager = BlogManager()

        for lang in SUPPORTED_LANGUAGES:
            content_dir = manager._get_content_dir(lang)
            assert content_dir is not None
            # 경로 검증
            if lang == "ko":
                assert "post" in str(content_dir)
                assert "content" in str(content_dir)
            else:
                assert lang in str(content_dir)
                assert "post" in str(content_dir)


class TestSearchPostsRealImplementation:
    """실제 BlogManager.search_posts() 테스트"""

    def test_search_posts_method_all_languages(self):
        """BlogManager.search_posts()가 모든 언어를 검색하는지 확인"""
        repo_path = create_temp_repo_with_posts()
        try:
            # BLOG_REPO_PATH를 임시 경로로 패치
            with patch('blog_manager.BLOG_REPO_PATH', repo_path):
                manager = BlogManager.__new__(BlogManager)
                manager.git = Mock()
                manager.git.pull = Mock(return_value=True)

                # _get_content_dir 메서드가 패치된 경로를 사용하도록 설정
                def mock_get_content_dir(language="ko"):
                    if language not in SUPPORTED_LANGUAGES:
                        raise ValueError(f"Unsupported language: {language}")
                    if language == "ko":
                        return repo_path / "content" / "post"
                    else:
                        return repo_path / "content" / language / "post"

                manager._get_content_dir = mock_get_content_dir

                # 검색 실행
                result = manager.search_posts("Python")

                # 검증
                assert "results" in result
                assert len(result["results"]) >= 2

                languages = {r["language"] for r in result["results"]}
                assert "ko" in languages
                assert "en" in languages
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
