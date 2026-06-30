#!/bin/bash
# 同时启动 uvicorn 后端和 nginx 反向代理

echo "=== 启动 CPA 学习系统 ==="

# 后台启动 uvicorn
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 &
echo "uvicorn 已启动 (PID: $!)"

# 等待 uvicorn 就绪
sleep 2

# 前台启动 nginx
echo "启动 nginx..."
nginx -g "daemon off;"
