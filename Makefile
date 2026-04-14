# ============================================================
# 库存管理系统 - Makefile 便捷命令
# 使用方式: make <target>
# ============================================================

.PHONY: dev build up down restart logs migrate migrate-create test clean help

# 默认目标
.DEFAULT_GOAL := help

# ----------------------------------------------------------
# 开发环境
# ----------------------------------------------------------

## 启动开发环境（挂载本地代码，启用热重载）
dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

## 后台启动开发环境
dev-detach:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d

# ----------------------------------------------------------
# 生产环境
# ----------------------------------------------------------

## 构建所有服务镜像
build:
	docker compose build

## 启动生产环境（后台运行）
up:
	docker compose up -d --build

## 停止所有服务
down:
	docker compose down

## 停止所有服务并删除数据卷（危险！会清除数据库数据）
down-clean:
	docker compose down -v

## 重启所有服务
restart:
	docker compose restart

# ----------------------------------------------------------
# 日志查看
# ----------------------------------------------------------

## 查看后端日志
logs:
	docker compose logs -f backend

## 查看所有服务日志
logs-all:
	docker compose logs -f

## 查看 Celery Worker 日志
logs-worker:
	docker compose logs -f celery-worker

## 查看 Celery Beat 日志
logs-beat:
	docker compose logs -f celery-beat

## 查看数据库日志
logs-db:
	docker compose logs -f db

# ----------------------------------------------------------
# 数据库迁移
# ----------------------------------------------------------

## 执行数据库迁移（升级到最新版本）
migrate:
	docker compose exec backend alembic upgrade head

## 回滚上一次数据库迁移
migrate-downgrade:
	docker compose exec backend alembic downgrade -1

## 查看当前数据库迁移状态
migrate-status:
	docker compose exec backend alembic current

## 查看数据库迁移历史
migrate-history:
	docker compose exec backend alembic history --verbose

## 创建新的数据库迁移文件
## 使用方式: make migrate-create msg="add_users_table"
migrate-create:
	docker compose exec backend alembic revision --autogenerate -m "$(msg)"

# ----------------------------------------------------------
# 测试
# ----------------------------------------------------------

## 运行后端测试
test:
	docker compose exec backend pytest -v --tb=short

## 运行后端测试（含覆盖率报告）
test-cov:
	docker compose exec backend pytest -v --cov=app --cov-report=html --cov-report=term-missing

## 运行指定测试文件
## 使用方式: make test-file file="tests/test_users.py"
test-file:
	docker compose exec backend pytest -v $(file)

# ----------------------------------------------------------
# 数据库管理
# ----------------------------------------------------------

## 进入数据库命令行
db-shell:
	docker compose exec db psql -U inventory_user -d inventory_db

## 进入 Redis 命令行
redis-shell:
	docker compose exec redis redis-cli

## 创建数据库备份
db-backup:
	docker compose exec db pg_dump -U inventory_user inventory_db > backup_$$(date +%Y%m%d_%H%M%S).sql

# ----------------------------------------------------------
# 代码质量
# ----------------------------------------------------------

## 运行代码格式化（Black + isort）
fmt:
	docker compose exec backend black app/ tests/ && docker compose exec backend isort app/ tests/

## 运行代码检查（Flake8 + mypy）
lint:
	docker compose exec backend flake8 app/ tests/ && docker compose exec backend mypy app/

# ----------------------------------------------------------
# 清理
# ----------------------------------------------------------

## 清理 Docker 镜像、容器、未使用的卷和网络
clean:
	docker compose down -v --rmi all --remove-orphans
	docker system prune -f
	@echo "清理完成！"

## 清理前端构建产物
clean-frontend:
	rm -rf frontend/dist frontend/node_modules

## 清理后端构建产物
clean-backend:
	rm -rf backend/__pycache__ backend/app/__pycache__
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find backend -type f -name "*.pyc" -delete 2>/dev/null || true

# ----------------------------------------------------------
# 帮助
# ----------------------------------------------------------

## 显示帮助信息
help:
	@echo ""
	@echo "库存管理系统 - 可用命令"
	@echo "========================"
	@echo ""
	@grep -E '^## ' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ": "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' | \
		sed 's/## //'
	@echo ""
