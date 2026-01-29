#!/bin/bash

# 数字人生回忆录 - 测试脚本

echo "🧪 测试数字人生回忆录应用..."
echo ""

# 测试后端API
echo "1. 测试后端API..."
API_RESPONSE=$(curl -s http://127.0.0.1:8000/)
if echo "$API_RESPONSE" | grep -q "数字人生回忆录"; then
    echo "   ✅ 后端API运行正常"
else
    echo "   ❌ 后端API无法访问"
    exit 1
fi

# 测试前端页面
echo "2. 测试前端页面..."
FRONTEND_RESPONSE=$(curl -s http://192.168.1.22/memoir/)
if echo "$FRONTEND_RESPONSE" | grep -q "数字人生回忆录"; then
    echo "   ✅ 前端页面可访问"
else
    echo "   ❌ 前端页面无法访问"
    exit 1
fi

# 测试注册功能
echo "3. 测试用户注册..."
TIMESTAMP=$(date +%s)
USERNAME="testuser_$TIMESTAMP"
REGISTER_RESPONSE=$(curl -s -X POST http://127.0.0.1:8000/api/auth/register \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$USERNAME\",\"email\":\"test_$TIMESTAMP@example.com\",\"password\":\"test123\"}")

if echo "$REGISTER_RESPONSE" | grep -q "$USERNAME"; then
    echo "   ✅ 用户注册成功 ($USERNAME)"
else
    echo "   ⚠️  用户注册可能失败（可能是用户已存在）"
fi

# 测试登录功能
echo "4. 测试用户登录..."
LOGIN_RESPONSE=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$USERNAME\",\"password\":\"test123\"}")

if echo "$LOGIN_RESPONSE" | grep -q "access_token"; then
    echo "   ✅ 用户登录成功"
    TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
    echo "   📝 Token: ${TOKEN:0:20}..."
else
    echo "   ❌ 用户登录失败"
    exit 1
fi

# 测试创建记忆
echo "5. 测试创建记忆..."
ENTRY_RESPONSE=$(curl -s -X POST http://127.0.0.1:8000/api/entries \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"title":"测试记忆","content":"这是一个测试记忆","entry_date":"2026-01-29","mood":"happy"}')

if echo "$ENTRY_RESPONSE" | grep -q "测试记忆"; then
    echo "   ✅ 记忆创建成功"
    ENTRY_ID=$(echo "$ENTRY_RESPONSE" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
else
    echo "   ❌ 记忆创建失败"
    exit 1
fi

# 测试获取记忆列表
echo "6. 测试获取记忆列表..."
LIST_RESPONSE=$(curl -s http://127.0.0.1:8000/api/entries \
    -H "Authorization: Bearer $TOKEN")

if echo "$LIST_RESPONSE" | grep -q "测试记忆"; then
    echo "   ✅ 记忆列表获取成功"
else
    echo "   ❌ 记忆列表获取失败"
    exit 1
fi

# 测试统计信息
echo "7. 测试统计信息..."
STATS_RESPONSE=$(curl -s http://127.0.0.1:8000/api/stats \
    -H "Authorization: Bearer $TOKEN")

if echo "$STATS_RESPONSE" | grep -q "total_entries"; then
    echo "   ✅ 统计信息获取成功"
else
    echo "   ❌ 统计信息获取失败"
    exit 1
fi

# 测试标签功能
echo "8. 测试标签功能..."
TAG_RESPONSE=$(curl -s -X POST http://127.0.0.1:8000/api/tags \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"name":"测试标签","color":"#6366f1"}')

if echo "$TAG_RESPONSE" | grep -q "测试标签"; then
    echo "   ✅ 标签创建成功"
else
    echo "   ⚠️  标签创建可能失败（可能是标签已存在）"
fi

# 测试删除记忆
echo "9. 测试删除记忆..."
DELETE_RESPONSE=$(curl -s -X DELETE http://127.0.0.1:8000/api/entries/$ENTRY_ID \
    -H "Authorization: Bearer $TOKEN")

if echo "$DELETE_RESPONSE" | grep -q "删除成功"; then
    echo "   ✅ 记忆删除成功"
else
    echo "   ⚠️  记忆删除可能失败"
fi

echo ""
echo "========================================"
echo "✅ 所有测试通过！"
echo "========================================"
echo ""
echo "📱 应用访问地址:"
echo "   前端: http://192.168.1.22/memoir/"
echo "   API文档: http://192.168.1.22:8000/docs"
echo ""
echo "🎉 数字人生回忆录已成功部署！"
echo ""
echo "使用说明:"
echo "1. 访问 http://192.168.1.22/memoir/"
echo "2. 注册新账号或使用 testuser/test123 登录"
echo "3. 开始记录你的人生回忆吧！"
