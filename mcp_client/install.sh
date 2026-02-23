#!/bin/bash
# Blog MCP Client 설치 스크립트

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$HOME/.claude/settings.json"

echo "=== Blog MCP Client 설치 ==="

# 1. uv 확인
if ! command -v uv &> /dev/null; then
    echo "uv를 설치합니다..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# 2. 의존성 설치
echo "의존성을 설치합니다..."
cd "$SCRIPT_DIR"
uv venv
uv pip install mcp httpx

# 3. API Key 입력
echo ""
echo "API Key를 입력하세요 (블로그 관리자에게 문의):"
read -r API_KEY

if [ -z "$API_KEY" ]; then
    echo "API Key가 필요합니다."
    exit 1
fi

# 4. .mcp.json 업데이트
echo ""
echo "프로젝트의 .mcp.json을 업데이트합니다..."

MCP_JSON="$SCRIPT_DIR/../.mcp.json"
cat > "$MCP_JSON" << EOF
{
  "mcpServers": {
    "blog": {
      "command": "$SCRIPT_DIR/.venv/bin/python",
      "args": ["$SCRIPT_DIR/mcp_blog_client.py"],
      "env": {
        "BLOG_API_URL": "http://130.162.133.47",
        "BLOG_API_KEY": "$API_KEY"
      }
    }
  }
}
EOF

echo ""
echo "=== 설치 완료 ==="
echo ""
echo "사용법:"
echo "  Claude Code에서 이 프로젝트를 열고 다음과 같이 사용하세요:"
echo ""
echo "  '블로그에 새 포스트 작성해줘. 제목은 ...'"
echo "  '블로그 포스트 목록 보여줘'"
echo ""
