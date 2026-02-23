#!/bin/bash
# Blog API 서버 배포 스크립트
# OCI 서버에서 실행

set -e

API_DIR="/var/www/blog-api"
BLOG_REPO="/var/www/blog-repo"

echo "=== Blog API 서버 배포 ==="

# 1. 디렉토리 생성
sudo mkdir -p $API_DIR
sudo chown -R ubuntu:ubuntu $API_DIR

# 2. API 서버 파일 복사 (현재 디렉토리에서)
if [ -d "./api_server" ]; then
    cp -r ./api_server/* $API_DIR/
else
    echo "Error: api_server 디렉토리를 찾을 수 없습니다"
    exit 1
fi

cd $API_DIR

# 3. Python 가상환경 생성
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# 4. 의존성 설치
./venv/bin/pip install -r requirements.txt

# 5. .env 파일 생성 (없으면)
if [ ! -f ".env" ]; then
    echo "BLOG_ROOT=$BLOG_REPO" > .env
    echo "PORT=8000" >> .env

    # API 키 생성
    API_KEY=$(./venv/bin/python -c "import secrets; print(f'blog_{secrets.token_urlsafe(32)}')")
    echo "BLOG_API_KEYS=$API_KEY" >> .env

    echo ""
    echo "=== 생성된 API Key ==="
    echo "$API_KEY"
    echo "이 키를 안전하게 보관하세요!"
    echo ""
fi

# 6. 블로그 레포지토리 클론 (없으면)
if [ ! -d "$BLOG_REPO" ]; then
    git clone https://github.com/yarang/blogs.git $BLOG_REPO
    chown -R ubuntu:ubuntu $BLOG_REPO
fi

# 7. systemd 서비스 등록
sudo cp blog-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable blog-api
sudo systemctl restart blog-api

# 8. 상태 확인
echo "서비스 상태:"
sudo systemctl status blog-api --no-pager

echo ""
echo "=== 배포 완료 ==="
echo "API 엔드포인트: http://localhost:8000"
echo "API 문서: http://localhost:8000/docs"
echo ""
echo "API Key 확인: cat $API_DIR/.env | grep BLOG_API_KEYS"
