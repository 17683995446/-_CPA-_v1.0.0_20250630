# ========== CPA Learning App Makefile ==========
# 常用命令快捷方式

.PHONY: help install dev test test-unit test-integration test-system run lint format clean docker-build docker-up docker-down db-migrate db-migrate-create db-rollback

# 默认目标
help: ## 显示所有可用命令
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## 安装生产依赖
	cd backend && pip install -r requirements.txt

dev: ## 安装开发依赖（含测试工具）
	cd backend && pip install -r requirements.txt && pip install pytest pytest-asyncio httpx ruff

test: ## 运行全部测试
	cd backend && python -m pytest tests/ -v --tb=short

test-unit: ## 运行单元测试
	cd backend && python -m pytest tests/unit/ -v --tb=short -m unit

test-integration: ## 运行集成测试
	cd backend && python -m pytest tests/integration/ -v --tb=short -m integration

test-system: ## 运行系统测试
	cd backend && python -m pytest tests/system/ -v --tb=short -m system

run: ## 启动开发服务器
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

lint: ## 代码检查
	cd backend && ruff check app/ tests/

format: ## 代码格式化
	cd backend && ruff format app/ tests/ && ruff check --fix app/ tests/

clean: ## 清理缓存文件
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -f backend/data/cpa_learning.db-journal 2>/dev/null || true

docker-build: ## 构建 Docker 镜像
	docker build -t cpa-app .

docker-up: ## 启动 Docker 容器
	docker compose up -d

docker-down: ## 停止 Docker 容器
	docker compose down

db-migrate: ## 执行数据库迁移
	cd backend && alembic upgrade head

db-migrate-create: ## 创建新迁移（用法: make db-migrate-create msg="描述"）
	cd backend && alembic revision --autogenerate -m "$(msg)"

db-rollback: ## 回滚上一个迁移
	cd backend && alembic downgrade -1
