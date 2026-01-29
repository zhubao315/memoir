#!/bin/bash

# 数字人生回忆录 - 启动脚本

echo "🚀 启动数字人生回忆录..."

# 检查Python环境
if [ ! -d "/data/venv" ]; then
    echo "❌ 错误: Python虚拟环境不存在"
    exit 1
fi

# 激活虚拟环境
source /data/venv/bin/activate

# 进入后端目录
cd /fs/memoir/backend

# 检查依赖
echo "📦 检查依赖..."
python -c "import fastapi, uvicorn, sqlalchemy" 2>/dev/null || {
    echo "❌ 错误: 缺少依赖，请运行:"
    echo "cd /data/venv && uv pip install fastapi uvicorn sqlalchemy psycopg psycopg2-binary python-magic pillow jinja2 python-jose[cryptography] passlib[bcrypt] python-multipart"
    exit 1
}

# 创建上传目录
mkdir -p /fs/memoir/uploads

# 启动后端
echo "🎯 启动后端服务 (端口: 8000)..."
echo "📱 前端访问: http://192.168.1.22/memoir/"
echo "🔧 API文档: http://192.168.1.22:8000/docs"
echo ""
echo "按 Ctrl+C 停止服务"

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
