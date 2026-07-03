"""
FastAPI 应用入口。

架构分层：
    main.py          → 应用工厂：创建实例、注册中间件/路由/异常处理
    middleware.py     → HTTP 中间件（安全头等）
    api/routers/      → 路由层：HTTP 参数解析 + 响应构造
    services/         → 服务层：跨引擎业务编排
    engines/          → 引擎层：纯算法（BKT/FSRS/题库生成等）
    models/           → ORM 模型
    schemas/          → Pydantic 请求/响应模型
    question_data/    → 题库数据生成与修复（模块化包）

启动流程：
    1. init_db()  — 创建表结构
    2. run_seed() — 加载种子数据（知识点、用户）
    3. generate_mass_questions() — 批量生成题库（如不足阈值）
    4. fix_existing_database() — 数据完整性修复（始终执行）
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api.routers import register_routes
from app.config import settings
from app.db.session import init_db
from app.logging_config import setup_logging
from app.middleware import register_middleware
from app.question_data import fix_existing_database, generate_mass_questions
from app.seed_data import run_seed

# 初始化日志系统
setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("app.main")
STATIC_DIR = Path(__file__).parent / "static"


# ===== 应用生命周期 =====

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
        # ★ 版本检查：无论 AUTO_SEED_ON_STARTUP 是否开启，版本不匹配时必须重建
        # 版本文件放在 DATA_DIR（Docker volume 挂载点），这样：
        #   - 新 volume：Docker 自动从镜像拷贝构建时数据+版本文件 → 版本匹配 → 无需重建
        #   - 旧 volume：版本文件记录旧版本 → 版本不匹配 → 自动重建
        version_file = settings.DATA_DIR / ".question_db_version"
        stored_version = ""
        if version_file.exists():
            stored_version = version_file.read_text(encoding="utf-8").strip()

        version_mismatch = stored_version != settings.QUESTION_DB_VERSION
        q_count = db.query(Question).count()

        if version_mismatch and q_count > 0:
            logger.warning("题库版本不匹配 (存储=%s, 当前=%s)，重建题库...",
                           stored_version, settings.QUESTION_DB_VERSION)
            # 删除旧题目和知识点（保留用户学习记录）
            # 先删除 LLM 关联表（有外键指向 questions），再删选项和题目
            from app.models import QuestionOption, KnowledgePoint, QuestionEmbedding, ErrorAnalysis
            db.query(ErrorAnalysis).delete()
            db.query(QuestionEmbedding).delete()
            db.query(QuestionOption).delete()
            db.query(Question).delete()
            db.query(KnowledgePoint).delete()
            db.commit()
            q_count = 0
            # 版本不匹配时强制重新生成种子数据
            run_seed(db)
        elif q_count == 0 and settings.AUTO_SEED_ON_STARTUP:
            run_seed(db)

        if (version_mismatch or q_count < settings.QUESTION_BANK_THRESHOLD) and settings.AUTO_SEED_ON_STARTUP:
            logger.info("题库仅 %d 题，开始批量生成...", q_count)
            generate_mass_questions(db)
            final_count = db.query(Question).count()
            logger.info("题库生成完成，共 %d 题", final_count)
        elif version_mismatch:
            # AUTO_SEED_ON_STARTUP=false 但版本不匹配：也必须重建
            logger.info("版本不匹配，强制重建题库...")
            if q_count == 0:
                run_seed(db)
            generate_mass_questions(db)
            final_count = db.query(Question).count()
            logger.info("题库重建完成，共 %d 题", final_count)

        # 写入当前版本号
        version_file.write_text(settings.QUESTION_DB_VERSION, encoding="utf-8")

        # 启动时自动修复已有题库的选项顺序和数据完整性（始终执行）
        fix_stats = fix_existing_database(db)
        dedup = fix_stats.get("dedup_fixed", 0)
        suffix_cleaned = fix_stats.get("suffix_cleaned", 0)
        if fix_stats["judgment_fixed"] > 0 or fix_stats["answer_fixed"] > 0 or dedup > 0 or suffix_cleaned > 0:
            logger.info("题库修复: 打乱%d题, 判断题修复%d题, 答案修正%d题, 选项去重%d题, 后缀清理%d题",
                        fix_stats["shuffled"], fix_stats["judgment_fixed"],
                        fix_stats["answer_fixed"], dedup, suffix_cleaned)
        else:
            logger.info("题库选项已打乱: %d题", fix_stats["shuffled"])
    finally:
        db.close()
    yield


# ===== 应用工厂 =====

def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例。

    集中管理中间件注册、路由注册、异常处理器和系统端点，
    使应用结构清晰可维护。
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "CPA 注册会计师智能学习平台 API\n\n"
            "## 核心功能\n"
            "- **自适应学习**：BKT 知识追踪 + FSRS 间隔重复算法\n"
            "- **题库管理**：5000+ 题目，涵盖 CPA 六大科目\n"
            "- **知识图谱**：可视化知识点关联与学习路径\n"
            "- **游戏化激励**：等级、XP、成就、连续学习\n"
            "- **分录判错**：会计分录自动批改\n\n"
            "## 测试\n"
            "访问 `/docs` 查看 Swagger UI，`/redoc` 查看 ReDoc 文档。"
        ),
        lifespan=lifespan,
    )

    # 中间件
    register_middleware(app)

    # 静态文件
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # 路由
    register_routes(app)

    # 异常处理
    _register_exception_handlers(app)

    # 系统端点
    _register_system_endpoints(app)

    return app


def _register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。"""

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """捕获所有未处理异常，返回统一 500 响应，避免暴露内部栈。"""
        logger.error("Unhandled exception: %s %s -> %s",
                     request.method, request.url.path, exc, exc_info=True)
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


def _register_system_endpoints(app: FastAPI) -> None:
    """注册系统级端点（健康检查、根路径、favicon）。"""

    @app.get("/health")
    async def health_check():
        """健康检查端点。用于系统测试和容器探针。"""
        return {
            "status": "ok",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

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

    @app.get("/")
    async def root():
        """根端点：返回前端页面。"""
        return FileResponse(STATIC_DIR / "index.html")


# ===== 模块级应用实例 =====

app = create_app()
