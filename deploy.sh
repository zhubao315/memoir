#!/bin/bash

# 数字人生回忆录 - 部署脚本

echo "🚀 部署数字人生回忆录到Nginx..."

# 复制Nginx配置
echo "📋 复制Nginx配置..."
sudo cp /fs/memoir/nginx.conf /etc/nginx/conf.d/memoir.conf

# 测试Nginx配置
echo "🔍 测试Nginx配置..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo "✅ Nginx配置测试通过"

    # 重新加载Nginx
    echo "🔄 重新加载Nginx..."
    sudo systemctl reload nginx

    if [ $? -eq 0 ]; then
        echo "✅ Nginx重新加载成功"
    else
        echo "⚠️  Nginx重新加载失败，尝试重启..."
        sudo systemctl restart nginx
    fi
else
    echo "❌ Nginx配置测试失败"
    exit 1
fi

# 启动后端
echo ""
echo "🎯 启动后端服务..."
echo "运行以下命令启动后端:"
echo "  cd /fs/memoir && bash start.sh"
echo ""
echo "📱 访问应用: http://192.168.1.22/memoir/"
echo "🔧 API文档: http://192.168.1.22:8000/docs"
echo ""
echo "部署完成！🎉"
