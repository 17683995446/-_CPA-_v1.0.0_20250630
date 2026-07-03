# CPA 注册会计师智能学习平台

自适应学习系统，集成 BKT 知识追踪、FSRS 间隔重复算法、知识图谱和游戏化激励，覆盖 CPA 六大科目 5000+ 题目。

## 技术栈

- **后端**: FastAPI 0.138 + SQLAlchemy 2.0 + Pydantic 2.13
- **数据库**: SQLite（开发）/ PostgreSQL（生产）
- **前端**: 原生 JS SPA（无构建工具）
- **测试**: pytest（unit / integration / system 三层标记）
- **部署**: Docker + Nginx

## 快速开始

```bash
# 安装依赖
pip install -r backend/requirements.txt

# 启动开发服务器（自动初始化题库）
cd backend && python -m uvicorn app.main:app --reload --port 8000

# 运行测试
make test-unit          # 单元测试（~4s）
make test-integration   # 集成测试
make test-system        # 系统测试
```

访问 `http://localhost:8000/docs` 查看 Swagger UI。

## 项目结构

```
backend/app/
├── main.py              # 应用工厂与生命周期
├── config.py            # 全局配置
├── middleware.py         # HTTP 中间件
├── api/routers/         # 路由层（8 个业务域，35 个端点）
├── services/            # 服务层（跨引擎编排）
├── engines/             # 引擎层（BKT / FSRS / 游戏化 / 出题 / 图谱 / 分录判错）
├── models/              # ORM 模型（13 个表）
├── schemas/             # Pydantic 请求/响应模型
├── db/                  # 数据库会话与基类
├── question_data/       # 题库生成、修复与静态数据
└── static/              # 前端 SPA
```

## 架构分层

```
HTTP 请求
  → middleware（安全头 / CORS）
    → routers（参数解析 + 响应构造）
      → services（跨引擎业务编排）
        → engines（纯算法，无 DB 依赖）
        → models（ORM 读写）
```

引擎层使用 dataclass 承载状态，通过 `from_orm()/to_orm()` 与 ORM 模型互转，可独立单元测试。

## 核心引擎

| 引擎 | 文件 | 职责 |
|------|------|------|
| BKT | `engines/bkt.py` | 贝叶斯知识追踪，4 参数模型 |
| FSRS | `engines/fsrs.py` | 间隔重复调度，FSRS-4.5 算法 |
| Gamification | `engines/gamification.py` | XP / 等级 / 成就 / Streak |
| Question Gen | `engines/question_gen.py` | AI 出题，模板 + 变体策略 |
| Knowledge Graph | `engines/knowledge_graph.py` | 知识图谱构建与学习路径 |
| Journal Validator | `engines/journal_validator.py` | 会计分录自动判错 |

## 环境变量

参见 `.env.example`。关键配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEBUG` | `false` | 调试模式 |
| `DATABASE_URL` | `sqlite:///data/cpa_learning.db` | 数据库连接 |
| `AUTO_SEED_ON_STARTUP` | `true` | 启动时自动初始化题库 |
| `QUESTION_BANK_THRESHOLD` | `5000` | 题库最小数量阈值 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

## 许可证

MIT
