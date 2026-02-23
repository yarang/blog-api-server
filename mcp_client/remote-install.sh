#!/bin/bash
# Blog MCP Client 원격 설치 스크립트
# 다른 프로젝트에서 사용할 때

set -e

INSTALL_DIR="${1:-$HOME/.blog-mcp-client}"

echo "=== Blog MCP Client 원격 설치 ==="
echo "설치 경로: $INSTALL_DIR"
echo ""

# 1. 설치 디렉토리 생성
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# 2. MCP 클라이언트 다운로드
echo "MCP 클라이언트 다운로드 중..."
curl -fsSL https://raw.githubusercontent.com/yarang/blogs/main/mcp_client/mcp_blog_client.py -o mcp_blog_client.py

# 3. uv 확인 및 설치
if ! command -v uv &> /dev/null; then
    echo "uv를 설치합니다..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# 4. 가상환경 및 의존성 설치
echo "의존성을 설치합니다..."
uv venv
uv pip install mcp httpx

# 5. API Key 입력
echo ""
echo "API Key를 입력하세요:"
echo "(블로그 관리자에게 문의: yarang)"
read -r API_KEY

if [ -z "$API_KEY" ]; then
    echo "경고: API Key가 입력되지 않았습니다. 나중에 설정하세요."
    API_KEY="YOUR_API_KEY"
fi

# 6. 설정 파일 생성
CONFIG_FILE="$INSTALL_DIR/.mcp.json"
cat > "$CONFIG_FILE" << EOF
{
  "mcpServers": {
    "blog": {
      "command": "$INSTALL_DIR/.venv/bin/python",
      "args": ["$INSTALL_DIR/mcp_blog_client.py"],
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
echo "다음 내용을 프로젝트의 .mcp.json에 추가하거나,"
echo "설정 파일을 복사해서 사용하세요:"
echo ""
echo "  cp $CONFIG_FILE /your/project/.mcp.json"
echo ""
echo "또는 Claude Code 설정(~/.claude/settings.json)에 추가:"
echo ""
cat << 'SETTINGSEOF'
{
  "enableAllProjectMcpServers": true
}
SETTINGSEOF
echo ""
echo "API Key 변경: $INSTALL_DIR/.mcp.json 파일을 수정하세요."
echo ""
