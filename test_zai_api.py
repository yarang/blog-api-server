#!/usr/bin/env python3
"""
ZAI API 연결 테스트 스크립트
"""

import os
import httpx
import json

API_KEY = os.getenv("ZAI_API_KEY", "")
if not API_KEY:
    print("ERROR: ZAI_API_KEY 환경 변수가 필요합니다")
    print("Usage: ZAI_API_KEY=your_key python test_zai_api.py")
    exit(1)

# 테스트할 base URL과 엔드포인트 조합
TEST_CASES = [
    # (base_url, endpoint, headers_format)
    ("https://api.z.ai/api/coding/paas/v4", "/messages", "anthropic"),
    ("https://api.z.ai/api/coding/paas", "/v4/messages", "anthropic"),
    ("https://api.z.ai/api/coding/paas", "/v4/chat/completions", "openai"),
    ("https://api.zukijourney.com/v2", "/messages", "anthropic"),
    ("https://api.zukijourney.com", "/v2/messages", "anthropic"),
    ("https://api.zukijourney.com", "/v2/chat/completions", "openai"),
    ("https://api.zukijourney.com", "/v1/messages", "anthropic"),
    ("https://api.zukijourney.com", "/v1/chat/completions", "openai"),
    ("https://api.zukijourney.com", "/chat/completions", "openai"),
]

def test_anthropic_format(base_url: str, endpoint: str):
    """Anthropic 형식 API 테스트"""
    url = f"{base_url}{endpoint}"
    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "claude-3-5-haiku-20241022",
        "max_tokens": 100,
        "messages": [{"role": "user", "content": "Say hello"}]
    }
    return url, headers, payload

def test_openai_format(base_url: str, endpoint: str):
    """OpenAI 형식 API 테스트"""
    url = f"{base_url}{endpoint}"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "claude-3-5-haiku-20241022",
        "max_tokens": 100,
        "messages": [{"role": "user", "content": "Say hello"}]
    }
    return url, headers, payload

def main():
    print("=" * 60)
    print("ZAI API 연결 테스트")
    print("=" * 60)

    success_cases = []

    for base_url, endpoint, format_type in TEST_CASES:
        print(f"\n테스트: {base_url}{endpoint} ({format_type})")

        if format_type == "anthropic":
            url, headers, payload = test_anthropic_format(base_url, endpoint)
        else:
            url, headers, payload = test_openai_format(base_url, endpoint)

        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=30)

            print(f"  상태 코드: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"  응답: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
                success_cases.append((base_url, endpoint, format_type))
                print("  ✅ 성공!")
            else:
                print(f"  ❌ 실패: {response.text[:200]}")

        except Exception as e:
            print(f"  ❌ 에러: {str(e)[:200]}")

    print("\n" + "=" * 60)
    print("성공한 조합:")
    print("=" * 60)
    for base_url, endpoint, format_type in success_cases:
        print(f"  Base URL: {base_url}")
        print(f"  Endpoint: {endpoint}")
        print(f"  Format: {format_type}")
        print()

    if not success_cases:
        print("  성공한 조합이 없습니다.")

if __name__ == "__main__":
    main()
