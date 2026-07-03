# 架构设计文档

## 分层架构

```
┌─────────────────────────────────────────────────────┐
│                    HTTP 入口                         │
│  middleware.py — 安全头 / CORS / 请求日志            │
├─────────────────────────────────────────────────────┤
│              api/routers/ — 路由层                   │
│  参数解析 → 调用 service → 构造响应                   │
│  不含业务逻辑，不含 DB 直接访问                       │
├─────────────────────────────────────────────────────┤
│            services/ — 服务层                        │
│  跨引擎业务编排（如 AnswerService 联动 BKT+FSRS+XP） │
│  依赖注入 engines + db session                       │
├──────────────────┬──────────────────────────────────┤
│  engines/        │  models/                          │
│  纯算法层         │  ORM 层                           │
│  dataclass 承载   │  SQLAlchemy 2.0 Declarative       │
│  无 DB 依赖       │  Base 统一 id/created_at/updated  │
│  可独立单元测试   │  from_orm/to_orm 与引擎互转       │
├──────────────────┴──────────────────────────────────┤
│               db/ — 数据库基础设施                   │
│  session.py — 引擎/会话/迁移                         │
│  base.py — DeclarativeBase                          │
├─────────────────────────────────────────────────────┤
│               config.py — 全局配置                   │
│  所有引擎参数集中定义，环境变量可覆盖                 │
└─────────────────────────────────────────────────────┘
```

## 请求处理流程

以「提交答题」为例：

```
POST /api/mastery/{user_id}/answer
  │
  ├─ routers/mastery.py — 解析 SubmitAnswerRequest
  │   └─ deps.get_bkt_engine() → 注入 BKTEngine 单例
  │   └─ deps.get_db() → 注入 Session
  │
  ├─ services/answer_service.py — AnswerService.submit_answer()
  │   ├─ BKTEngine.update() → 更新掌握度
  │   ├─ FSRSEngine.review() → 调度下次复习
  │   └─ GamificationEngine.add_xp() → 计算 XP / 等级
  │
  ├─ models/ — UserMastery / ReviewCard / UserProfile 持久化
  │
  └─ schemas/ — SubmitAnswerResponse 构造响应
```

## 引擎设计原则

引擎层遵循「纯函数 + 可变状态容器」模式：

- 每个引擎接收 dataclass 状态对象，返回更新后的状态
- 引擎自身无 DB 依赖，通过 `from_orm()/to_orm()` 与 ORM 模型互转
- 引擎参数全部从 `config.py` 注入，消除硬编码

```python
# 引擎使用示例
mastery = BKTState.from_orm(user_mastery)        # ORM → dataclass
updated = bkt_engine.update(mastery, is_correct)  # 纯计算
user_mastery.apply_state(updated)                  # dataclass → ORM
db.commit()
```

## 题库生命周期

```
启动
 ├─ init_db() — create_all + 列迁移兜底
 ├─ 版本检查 — .question_db_version vs QUESTION_DB_VERSION
 │   ├─ 版本匹配 → 跳过生成
 │   └─ 版本不匹配 → 清空题目 → run_seed() → generate_mass_questions()
 ├─ generate_mass_questions() — orchestrator 调度 6 科生成器
 └─ fix_existing_database() — 数据完整性修复管道
     ├─ 选项打乱（label 固定，交换 content/is_correct）
     ├─ 判断题修复（确保单一正确选项，~50% 分布）
     ├─ 答案一致性校验
     ├─ 选项去重（数值偏移 / 文本后缀）
     ├─ 幂等保障（清除上次后缀）
     ├─ label 规范化（按 id 排序重分配 A/B/C/D）
     ├─ 短解析增强
     ├─ 判断题答案平衡
     ├─ 静态模块加载（static_modules.json → explanation 等 4 模块）
     └─ 最终去重与判断题 answer 修复
```

## 数据库迁移策略

双轨制：

1. **生产环境**: `alembic upgrade head`（Dockerfile 构建时执行）
2. **开发/测试**: `init_db()` → `create_all()` + `_migrate_columns()` 轻量级 ALTER TABLE

`_migrate_columns()` 检查并添加缺失列，作为 Alembic 未安装时的降级方案。

## 测试架构

```
tests/
├── conftest.py          — 共享 fixtures（内存 SQLite + StaticPool）
├── unit/                — 引擎/模型/schema 独立测试（~4s）
├── integration/         — 跨模块协作测试（API + 引擎联动）
└── system/              — 端到端完整流程测试
```

- 每个测试使用独立内存 SQLite（`sqlite://`），互不干扰
- `AUTO_SEED_ON_STARTUP=False` 避免测试时污染
- 三层标记：`@pytest.mark.unit/integration/system`
- CI 分层运行，单元测试优先反馈
