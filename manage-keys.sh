#!/bin/bash
# Blog API Key 관리 스크립트
# OCI 서버에서 실행

set -e

API_DIR="/var/www/blog-api"
ENV_FILE="$API_DIR/.env"

echo "=== Blog API Key 관리 ==="
echo ""

# .env 파일 확인
if [ ! -f "$ENV_FILE" ]; then
    echo "오류: .env 파일이 없습니다."
    exit 1
fi

# 현재 키 목록
echo "현재 등록된 API Keys:"
echo "---"
grep "BLOG_API_KEYS" "$ENV_FILE" | cut -d'=' -f2 | tr ',' '\n' | nl
echo ""

# 메뉴
echo "작업 선택:"
echo "  1) 새 API Key 발급"
echo "  2) API Key 삭제"
echo "  3) 종료"
echo ""
read -p "선택: " choice

case $choice in
    1)
        # 새 키 발급
        NEW_KEY=$(python3 -c "import secrets; print(f'blog_{secrets.token_urlsafe(32)}')")

        echo ""
        read -p "사용자 이름 (선택): " username

        # 기존 키에 추가
        CURRENT_KEYS=$(grep "BLOG_API_KEYS" "$ENV_FILE" | cut -d'=' -f2)
        if [ -z "$CURRENT_KEYS" ]; then
            UPDATED_KEYS="$NEW_KEY"
        else
            UPDATED_KEYS="$CURRENT_KEYS,$NEW_KEY"
        fi

        # .env 업데이트
        sed -i "s|^BLOG_API_KEYS=.*|BLOG_API_KEYS=$UPDATED_KEYS|" "$ENV_FILE"

        echo ""
        echo "=== 새 API Key 발급 완료 ==="
        [ -n "$username" ] && echo "사용자: $username"
        echo ""
        echo "API Key:"
        echo "$NEW_KEY"
        echo ""
        echo "이 키를 안전하게 사용자에게 전달하세요."
        ;;

    2)
        # 키 삭제
        read -p "삭제할 키 번호: " key_num

        KEYS=$(grep "BLOG_API_KEYS" "$ENV_FILE" | cut -d'=' -f2)
        IFS=',' read -ra KEY_ARRAY <<< "$KEYS"

        if [ "$key_num" -lt 1 ] || [ "$key_num" -gt ${#KEY_ARRAY[@]} ]; then
            echo "잘못된 번호입니다."
            exit 1
        fi

        # 선택한 키 제거
        unset 'KEY_ARRAY[key_num-1]'
        UPDATED_KEYS=$(IFS=','; echo "${KEY_ARRAY[*]}")

        # .env 업데이트
        sed -i "s|^BLOG_API_KEYS=.*|BLOG_API_KEYS=$UPDATED_KEYS|" "$ENV_FILE"

        echo "키가 삭제되었습니다."
        ;;

    3)
        echo "종료합니다."
        ;;

    *)
        echo "잘못된 선택입니다."
        ;;
esac
