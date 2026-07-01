"""
FastAPI 应用入口。

架构规范：
- 应用实例创建与路由注册分离
- 启动时初始化数据库（可通过 config.AUTO_SEED_ON_STARTUP 跳过）
- 全局异常处理中间件捕获未处理异常，返回统一错误格式
- 健康检查端点用于系统测试
- 所有业务路由注册在 /api 前缀下
- 前端静态文件挂载在根路径
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers import (
    gamification as gamification_router,
    journal as journal_router,
    knowledge as knowledge_router,
    mastery as mastery_router,
    questions as questions_router,
    review as review_router,
    study as study_router,
    users as users_router,
)
from app.config import settings
from app.db.session import init_db
from app.seed_data import run_seed
from app.mass_questions import generate_mass_questions

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库并加载种子数据与题库。

    测试隔离：当 config.AUTO_SEED_ON_STARTUP=False 时跳过种子数据与题库生成，
    避免测试时污染真实数据库文件。
    数据完整性修复（fix_existing_database）始终执行，不受此开关控制。
    """
    init_db()

    from app.db.session import SessionLocal
    from app.models import Question

    db = SessionLocal()
    try:
        if settings.AUTO_SEED_ON_STARTUP:
            run_seed(db)
            q_count = db.query(Question).count()
            if q_count < settings.QUESTION_BANK_THRESHOLD:
                print(f"题库仅 {q_count} 题，开始批量生成...")
                generate_mass_questions(db)
                final_count = db.query(Question).count()
                print(f"题库生成完成，共 {final_count} 题")

        # 启动时自动修复已有题库的选项顺序和数据完整性（始终执行）
        from app.mass_questions import fix_existing_database
        fix_stats = fix_existing_database(db)
        if fix_stats["judgment_fixed"] > 0 or fix_stats["answer_fixed"] > 0:
            print(f"题库修复: 打乱{fix_stats['shuffled']}题, "
                  f"判断题修复{fix_stats['judgment_fixed']}题, "
                  f"答案修正{fix_stats['answer_fixed']}题")
        else:
            print(f"题库选项已打乱: {fix_stats['shuffled']}题")
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# 注册 API 路由
app.include_router(users_router.router)
app.include_router(knowledge_router.router)
app.include_router(questions_router.router)
app.include_router(review_router.router)
app.include_router(mastery_router.router)
app.include_router(gamification_router.router)
app.include_router(journal_router.router)
app.include_router(study_router.router)


# ===== 全局异常处理 =====

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """捕获所有未处理异常，返回统一 500 响应，避免暴露内部栈。"""
    logger.error("Unhandled exception: %s %s -> %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "服务器内部错误", "data": None},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """将业务层 ValueError 转为 422 响应。"""
    return JSONResponse(
        status_code=422,
        content={"code": 422, "message": str(exc), "data": None},
    )


# ===== 系统端点 =====

@app.get("/health")
async def health_check():
    """健康检查端点。用于系统测试和容器探针。"""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/")
async def root():
    """根端点：返回前端页面。"""
    return FileResponse(STATIC_DIR / "index.html")
