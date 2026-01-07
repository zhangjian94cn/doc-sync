#!/bin/bash

# 确保使用正确的 Python 环境
export PATH=/opt/miniconda3/bin:$PATH

# 加载 .env 文件 (如果存在)
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# ==========================================
# 同步配置
# ==========================================
# 路径配置
LOCAL_PATH="/Users/zhangjian/Documents/webdav/zhangjian/obsidian/1.cmcc"
CLOUD_TOKEN="Qw7YfVmf1ldtAAdN3koc8nTXnje"
VAULT_ROOT="/Users/zhangjian/Documents/webdav/zhangjian/obsidian"

# 确保 Assets Token 被设置 (如果 .env 里没有，这里作为默认值)
if [ -z "$FEISHU_ASSETS_TOKEN" ]; then
    export FEISHU_ASSETS_TOKEN="XlvUfnlYxlcPlTdihxJc72h5nhb"
fi

# ==========================================
# 执行同步
# ==========================================
echo "🚀 开始同步任务..."
echo "📂 本地路径: $LOCAL_PATH"
echo "☁️  云端Token: $CLOUD_TOKEN"
echo "🏠 Vault Root: $VAULT_ROOT"
echo "🖼️  资源Token: $FEISHU_ASSETS_TOKEN"
echo "----------------------------------------"

# 检查 App ID 是否设置
if [ -z "$FEISHU_APP_ID" ]; then
    echo "❌ 错误: FEISHU_APP_ID 为空！"
    echo "⚠️  请打开项目目录下的 '.env' 文件，填入你的 App ID 和 App Secret。"
    echo "   文件路径: $(pwd)/.env"
    
    # 尝试自动打开 .env 文件 (macOS)
    if command -v open &> /dev/null; then
        open .env
        echo "   (已尝试自动打开 .env 文件)"
    fi
    exit 1
fi

python3 main.py --force "$LOCAL_PATH" "$CLOUD_TOKEN" --vault-root "$VAULT_ROOT"
