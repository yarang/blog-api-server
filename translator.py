"""
LLM 기반 번역 모듈
Anthropic Claude API를 사용하여 마크다운 포스트를 번역합니다.
"""

import os
import re
import json
import logging
from typing import Dict, Optional, Any
from anthropic import Anthropic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 환경 변수
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# 지원하는 언어 쌍
SUPPORTED_LANGUAGE_PAIRS = [
    ("ko", "en"),
    ("en", "ko")
]


class Translator:
    """LLM 기반 번역기"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or ANTHROPIC_API_KEY
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not set")
        self.client = Anthropic(api_key=self.api_key) if self.api_key else None

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
        if not self.client:
            return {
                "success": False,
                "error": "Translation service not configured. Set ANTHROPIC_API_KEY."
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
            response = self.client.messages.create(
                model="claude-3-7-sonnet-20250219",
                max_tokens=8192,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            translated_body = response.content[0].text

            # front matter가 있으면 번역된 본문과 결합
            if front_matter:
                # front matter 파싱
                parsed = self._parse_front_matter(front_matter)

                # title 필드가 있으면 번역
                if "title" in parsed:
                    title_prompt = f"""Translate this title to {target_name}. Provide only the translated title without quotes.

Title: {parsed["title"]}"""
                    title_response = self.client.messages.create(
                        model="claude-3-5-haiku-20241022",
                        max_tokens=256,
                        messages=[{"role": "user", "content": title_prompt}]
                    )
                    parsed["title"] = title_response.content[0].text.strip().strip('"').strip("'")

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
        if not self.client:
            return {
                "success": False,
                "error": "Translation service not configured"
            }

        lang_names = {"ko": "영어(English)", "en": "한국어(Korean)"}
        target_name = lang_names.get(target, target)

        try:
            prompt = f"""Translate this title to {target_name}. Provide only the translated title without quotes or punctuation.

Title: {title}"""

            response = self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}]
            )

            return {
                "success": True,
                "translated": response.content[0].text.strip().strip('"').strip("'")
            }

        except Exception as e:
            return {"success": False, "error": str(e)}


# 전역 인스턴스
translator = Translator()
