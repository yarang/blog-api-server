"""
LLM 기반 번역 모듈
Anthropic Claude API 또는 ZAI API를 사용하여 마크다운 포스트를 번역합니다.
"""

import os
import re
import json
import httpx
from typing import Dict, Optional, Any

from logger_config import get_logger

logger = get_logger(__name__)

# 환경 변수
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ZAI_API_KEY = os.getenv("ZAI_API_KEY")
# ZAI API는 OpenAI 호환 엔드포인트 사용
ZAI_BASE_URL = os.getenv("ZAI_BASE_URL", "https://api.zukijourney.com/v1")
ZAI_MODEL = os.getenv("ZAI_MODEL", "gpt-4o-mini")

# 지원하는 언어 쌍
SUPPORTED_LANGUAGE_PAIRS = [
    ("ko", "en"),
    ("en", "ko")
]


class Translator:
    """LLM 기반 번역기"""

    def __init__(self, api_key: str = None):
        # ZAI API 우선 사용, 없으면 Anthropic 사용
        if ZAI_API_KEY:
            self.api_key = ZAI_API_KEY
            self.base_url = ZAI_BASE_URL
            self.use_zai = True
            logger.info("Translation service initialized", extra={
                "provider": "ZAI",
                "base_url": self.base_url
            })
        else:
            self.api_key = api_key or ANTHROPIC_API_KEY
            self.base_url = "https://api.anthropic.com"
            self.use_zai = False
            if not self.api_key:
                logger.warning("ANTHROPIC_API_KEY not set")
            else:
                logger.info("Translation service initialized", extra={"provider": "Anthropic"})

    def _call_api(self, model: str, max_tokens: int, messages: list) -> str:
        """API 호출 (ZAI 또는 Anthropic)"""
        if not self.api_key:
            raise ValueError("API key not configured")

        logger.debug(f"Calling translation API", extra={"model": model, "max_tokens": max_tokens})

        if self.use_zai:
            # ZAI API 호출 (OpenAI 호환 형식)
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": ZAI_MODEL,
                "messages": messages,
                "max_tokens": max_tokens
            }

            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=120)

                if response.status_code != 200:
                    logger.error(f"ZAI Translation API error: {response.status_code}", extra={
                        "status_code": response.status_code,
                        "response_text": response.text[:500]
                    })
                    raise Exception(f"ZAI API error: {response.status_code} - {response.text}")

                data = response.json()
                # OpenAI 형식 응답
                result = data["choices"][0]["message"]["content"]
                logger.debug("ZAI Translation API call successful", extra={
                    "response_length": len(result)
                })
                return result

            except httpx.TimeoutException:
                logger.error("ZAI Translation API timeout")
                raise Exception("Translation API timeout")

        else:
            # Anthropic API 호출
            url = f"{self.base_url}/v1/messages"
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": messages
            }

            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=120)

                if response.status_code != 200:
                    logger.error(f"Anthropic Translation API error: {response.status_code}", extra={
                        "status_code": response.status_code,
                        "response_text": response.text[:500]
                    })
                    raise Exception(f"API error: {response.status_code} - {response.text}")

                data = response.json()
                # Anthropic 형식 응답
                result = data["content"][0]["text"]
                logger.debug("Translation API call successful", extra={
                    "response_length": len(result)
                })
                return result

            except httpx.TimeoutException:
                logger.error("Translation API timeout")
                raise Exception("Translation API timeout")

    def _extract_front_matter(self, content: str) -> tuple[str, str]:
        """front matter와 본문 분리"""
        # Hugo TOML front matter (+++ ... +++)
        front_matter_match = re.match(r'^\+\+\+\n(.*?)\n\+\+\+\n(.*)$', content, re.DOTALL)
        if front_matter_match:
            return front_matter_match.group(1), front_matter_match.group(2)

        # YAML front matter (--- ... ---)
        yaml_match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)
        if yaml_match:
            return yaml_match.group(1), yaml_match.group(2)

        # front matter가 없는 경우
        return "", content

    def _parse_front_matter(self, front_matter: str) -> Dict[str, Any]:
        """front matter 파싱 (간단한 TOML 파서)"""
        result: Dict[str, Any] = {}
        for line in front_matter.split('\n'):
            line = line.strip()
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                # 쉼표로 구분된 리스트 처리
                if value.startswith('[') and value.endswith(']'):
                    value = [v.strip().strip('"').strip("'") for v in value[1:-1].split(',') if v.strip()]
                result[key] = value
        return result

    def _build_front_matter(self, parsed: Dict[str, Any]) -> str:
        """front matter 재구성"""
        lines = []
        for key, value in parsed.items():
            if isinstance(value, list):
                lines.append(f'{key} = {json.dumps(value, ensure_ascii=False)}')
            elif isinstance(value, bool):
                lines.append(f'{key} = {str(value).lower()}')
            elif isinstance(value, (int, float)):
                lines.append(f'{key} = {value}')
            else:
                lines.append(f'{key} = "{value}"')
        return '\n'.join(lines)

    def translate(
        self,
        content: str,
        source: str = "ko",
        target: str = "en",
        preserve_markdown: bool = True
    ) -> Dict[str, any]:
        """
        마크다운 콘텐츠 번역

        Args:
            content: 번역할 마크다운 콘텐츠
            source: 소스 언어 (ko, en)
            target: 타겟 언어 (ko, en)
            preserve_markdown: 마크다운 형식 보존 여부

        Returns:
            번역 결과 딕셔너리
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "Translation service not configured. Set API key."
            }

        if (source, target) not in SUPPORTED_LANGUAGE_PAIRS:
            return {
                "success": False,
                "error": f"Unsupported language pair: {source} -> {target}"
            }

        # 언어 이름 매핑
        lang_names = {
            "ko": {"ko": "한국어", "en": "Korean"},
            "en": {"ko": "영어", "en": "English"}
        }

        source_name = lang_names[source][source]
        target_name = lang_names[target][source]

        # front matter와 본문 분리
        front_matter, body = self._extract_front_matter(content)

        # 번역 프롬프트
        if preserve_markdown:
            prompt = f"""You are a professional translator. Translate the following {source_name} markdown content to {target_name}.

IMPORTANT REQUIREMENTS:
1. Preserve ALL markdown formatting: headers (#), bold (**), italic (*), links ([text](url)), images (![alt](url)), code blocks (```), inline code (`), lists (-, *, 1.), blockquotes (>), tables
2. Keep code blocks and technical terms unchanged unless they have natural translations
3. Translate only the natural language text while maintaining the exact same markdown structure
4. For technical terms, use commonly accepted translations or keep the original if appropriate
5. Maintain the same tone and style as the original

Content to translate:
```
{body}
```

Provide ONLY the translated markdown content without any additional explanation."""

        else:
            prompt = f"""Translate the following {source_name} content to {target_name}.

Content:
{body}

Provide only the translated text."""

        try:
            translated_body = self._call_api(
                model="claude-3-7-sonnet-20250219",
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}]
            )

            # front matter가 있으면 번역된 본문과 결합
            if front_matter:
                # front matter 파싱
                parsed = self._parse_front_matter(front_matter)

                # title 필드가 있으면 번역
                if "title" in parsed:
                    title_prompt = f"""Translate this title to {target_name}. Provide only the translated title without quotes.

Title: {parsed["title"]}"""
                    translated_title = self._call_api(
                        model="claude-3-5-haiku-20241022",
                        max_tokens=256,
                        messages=[{"role": "user", "content": title_prompt}]
                    )
                    parsed["title"] = translated_title.strip().strip('"').strip("'")

                # front matter 재구성
                translated_front_matter = self._build_front_matter(parsed)
                result = f"+++\n{translated_front_matter}\n+++\n\n{translated_body}"
            else:
                result = translated_body

            return {
                "success": True,
                "translated": result,
                "source_language": source,
                "target_language": target
            }

        except Exception as e:
            logger.error(f"Translation error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def translate_title_only(self, title: str, target: str = "en") -> Dict[str, any]:
        """제목만 번역"""
        if not self.api_key:
            return {
                "success": False,
                "error": "Translation service not configured"
            }

        lang_names = {"ko": "영어(English)", "en": "한국어(Korean)"}
        target_name = lang_names.get(target, target)

        try:
            prompt = f"""Translate this title to {target_name}. Provide only the translated title without quotes or punctuation.

Title: {title}"""

            translated = self._call_api(
                model="claude-3-5-haiku-20241022",
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}]
            )

            return {
                "success": True,
                "translated": translated.strip().strip('"').strip("'")
            }

        except Exception as e:
            return {"success": False, "error": str(e)}


# 전역 인스턴스
translator = Translator()
