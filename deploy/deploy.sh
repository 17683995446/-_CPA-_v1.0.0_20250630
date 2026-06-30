#!/bin/bash
# ============================================
# CPA学习系统 - 一键部署脚本（非Docker方式）
# 适用于全新的 Ubuntu/Debian 云服务器
# 使用方法: bash deploy.sh
# ============================================

set -e

echo "=========================================="
echo "  CPA学习系统 - 云服务器一键部署"
echo "=========================================="

# 1. 检查是否为 root
if [ "$EUID" -ne 0 ]; then
  echo "请使用 root 用户运行: sudo bash deploy.sh"
  exit 1
fi

# 2. 安装系统依赖
echo "[1/7] 安装系统依赖..."
apt-get update -y
apt-get install -y python3 python3-pip python3-venv nginx git

# 3. 创建应用目录
APP_DIR="/opt/cpa-app"
echo "[2/7] 创建应用目录 $APP_DIR ..."
mkdir -p $APP_DIR

# 4. 复制项目文件（假设脚本在项目根目录运行）
echo "[3/7] 复制项目文件..."
cp -r backend/* $APP_DIR/

# 5. 创建虚拟环境并安装依赖
echo "[4/7] 创建虚拟环境并安装依赖..."
cd $APP_DIR
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 6. 配置 Nginx
echo "[5/7] 配置 Nginx..."
cat > /etc/nginx/sites-available/cpa-app << 'EOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 10m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location ~* \.(html|js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf)$ {
        proxy_pass http://127.0.0.1:8000;
        expires 1h;
        add_header Cache-Control "public, immutable";
    }
}
EOF

ln -sf /etc/nginx/sites-available/cpa-app /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx
systemctl enable nginx

# 7. 配置 systemd 服务（开机自启 + 崩溃重启）
echo "[6/7] 配置系统服务..."
cat > /etc/systemd/system/cpa-app.service << EOF
[Unit]
Description=CPA Learning App
After=network.target

[Service]
User=root
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable cpa-app
systemctl start cpa-app

# 8. 等待启动
echo "[7/7] 等待服务启动..."
sleep 5

# 检查状态
if systemctl is-active --quiet cpa-app; then
  echo ""
  echo "=========================================="
  echo "  部署成功！"
  echo "=========================================="
  echo ""
  echo "服务状态: 运行中"
  echo "访问地址: http://$(curl -s ifconfig.me)"
  echo ""
  echo "常用命令:"
  echo "  查看状态:  systemctl status cpa-app"
  echo "  查看日志:  journalctl -u cpa-app -f"
  echo "  重启服务:  systemctl restart cpa-app"
  echo "  停止服务:  systemctl stop cpa-app"
  echo ""
else
  echo "服务启动失败，请检查日志: journalctl -u cpa-app -f"
fi
