#!/bin/bash

# locator_json_download.sh - 根据locator_id搜索并下载JSON文件

set -euo pipefail

# 检查参数
if [ $# -ne 1 ]; then
    echo "用法: $0 <locator_id>"
    echo "示例: $0 4551211"
    exit 1
fi

LOCATOR_ID="$1"
echo "🔍 正在搜索 locator_id=$LOCATOR_ID 的JSON文件..."

# 搜索文件
SEARCH_RESULT=$(pixi run s3-cli ls --recursive "luonairui/data/visual-cr-locator-fe" | grep "locator_id=$LOCATOR_ID" | head -1)

if [ -z "$SEARCH_RESULT" ]; then
    echo "❌ 未找到 locator_id=$LOCATOR_ID 的JSON文件"
    echo "可用的搜索命令:"
    echo "  pixi run s3-cli ls --recursive \"luonairui/data/visual-cr-locator-fe\" | grep \"locator_id=$LOCATOR_ID\""
    exit 1
fi

# 提取完整的S3路径
S3_PATH=$(echo "$SEARCH_RESULT" | awk '{print $NF}')
LOCAL_FILENAME=$(basename "$S3_PATH")

echo "✅ 找到文件: $S3_PATH"
echo "📥 正在下载到: $LOCAL_FILENAME"

# 下载文件
pixi run s3-cli get "$S3_PATH" "$LOCAL_FILENAME"

echo "🎉 下载完成! 文件已保存为: $LOCAL_FILENAME"
echo ""
echo "文件内容预览:"
head -n 20 "$LOCAL_FILENAME"