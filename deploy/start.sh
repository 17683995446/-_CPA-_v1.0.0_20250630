#!/bin/bash
# 同时启动 uvicorn 后端和 nginx 反向代理

echo "=== 启动 CPA 学习系统 ==="

# 后台启动 uvicorn
# 使用单 worker 避免多 worker 同时执行启动逻辑（数据库重建）导致竞态条件
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 &
echo "uvicorn 已启动 (PID: $!)"

# 等待 uvicorn 就绪
sleep 2

# 前台启动 nginx
echo "启动 nginx..."
nginx -g "daemon off;"
