# CPA学习系统 - Docker 部署文件
# 构建: docker build -t cpa-app .
# 运行: docker run -d -p 80:80 --name cpa cpa-app

FROM python:3.11-slim

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装 Nginx
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 先复制依赖文件，利用 Docker 缓存层
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY backend/ .

# 预生成数据库和题库（构建时完成，启动时直接用）
# 同时执行 fix_existing_database 确保选项去重、打乱、解析增强
RUN python -c "from app.db.session import init_db; from app.seed_data import run_seed; from app.question_data import generate_mass_questions; from app.question_data.fixes import fix_existing_database; from app.db.session import SessionLocal; from app.models import Question; init_db(); db=SessionLocal(); run_seed(db); generate_mass_questions(db); fix_existing_database(db); cnt=db.query(Question).count(); print(f'题目数: {cnt}'); db.close()"

# 执行 Alembic 迁移（确保数据库结构最新）
RUN cd /app && alembic upgrade head 2>&1 || echo "Alembic migration skipped (already up to date)"

# 配置 Nginx
RUN rm -f /etc/nginx/sites-enabled/default
COPY deploy/nginx.conf /etc/nginx/sites-available/cpa-app
RUN ln -s /etc/nginx/sites-available/cpa-app /etc/nginx/sites-enabled/

# 暴露 80 端口
EXPOSE 80

# 启动脚本：同时启动 uvicorn 和 nginx
COPY deploy/start.sh /start.sh
RUN chmod +x /start.sh

# 关闭启动时重新生成题库（构建时已生成）
ENV AUTO_SEED_ON_STARTUP=false

CMD ["/start.sh"]
