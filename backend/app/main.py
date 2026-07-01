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
from fastapi.responses import FileResponse, JSONResponse, Response
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
        dedup = fix_stats.get("dedup_fixed", 0)
        if fix_stats["judgment_fixed"] > 0 or fix_stats["answer_fixed"] > 0 or dedup > 0:
            print(f"题库修复: 打乱{fix_stats['shuffled']}题, "
                  f"判断题修复{fix_stats['judgment_fixed']}题, "
                  f"答案修正{fix_stats['answer_fixed']}题, "
                  f"选项去重{dedup}题")
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


# ===== HTTP 安全头中间件 =====

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """为所有响应注入安全相关的 HTTP 头。"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # CSP：允许内联脚本/样式（单页应用需要）、CDN 资源、Google Fonts
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    )
    return response


# ===== 静态文件与 Favicon =====

# 挂载静态文件目录（支持 favicon 等静态资源访问）
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/favicon.ico")
async def favicon():
    """返回 SVG favicon，避免 404。"""
    svg_content = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        '<rect width="32" height="32" rx="6" fill="#6366f1"/>'
        '<text x="16" y="22" font-size="18" font-weight="bold" '
        'text-anchor="middle" fill="white" font-family="sans-serif">C</text>'
        '</svg>'
    )
    return Response(
        content=svg_content,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
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
