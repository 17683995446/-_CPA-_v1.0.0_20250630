# 编码规范

## Python 规范

### 文件与模块

- 每个文件顶部必须有中文 docstring，说明模块职责和架构定位
- 文件长度超过 500 行时考虑拆分
- 模块导入顺序：标准库 → 第三方库 → 本项目（app），使用 isort 规则

### 命名

| 类型 | 规范 | 示例 |
|------|------|------|
| 类 | PascalCase | `BKTEngine`, `UserMastery` |
| 函数/方法 | snake_case | `submit_answer`, `get_due_cards` |
| 常量 | UPPER_SNAKE | `FSRS_REQUEST_RETENTION` |
| 私有函数 | 前缀下划线 | `_shuffle_options`, `_migrate_columns` |
| ORM 模型表名 | 复数 snake_case | `users`, `knowledge_points` |

### 类型注解

所有函数签名必须包含参数和返回值类型注解：

```python
def get_due_cards(user_id: int, db: Session) -> list[ReviewCard]:
    ...
```

### 异常处理

- 业务层抛出 `ValueError` 表示可预期的业务错误（自动转为 422）
- 未预期异常由全局处理器捕获返回 500
- 不使用裸 `except:`，明确捕获具体异常类型

### 配置管理

- 所有可配置参数集中在 `config.py` 的 `Settings` 类
- 禁止在引擎/服务/路由中硬编码参数
- 环境变量通过 `os.getenv()` 在 `Settings` 中统一读取

## 架构规范

### 分层职责

| 层 | 允许 | 禁止 |
|----|------|------|
| routers | 参数解析、调用 service、构造响应 | 直接访问 DB、含业务逻辑 |
| services | 跨引擎编排、事务管理 | HTTP 相关代码 |
| engines | 纯算法计算 | DB 访问、HTTP 依赖 |
| models | ORM 定义、简单属性方法 | 业务逻辑、外部调用 |

### 依赖方向

```
routers → services → engines
                  → models
routers → models（仅简单查询）
```

禁止反向依赖：engines 不引用 routers/services/models。

### 引擎设计

- 引擎状态使用 `@dataclass`，不继承 ORM 模型
- 通过 `from_orm()` / `to_orm()` 与 ORM 互转
- 引擎构造函数参数从 `config.py` 注入
- 引擎方法返回新状态或修改后的状态对象，不直接操作 DB

## 数据库规范

### 模型定义

- 继承 `Base`（提供 `id`, `created_at`, `updated_at`）
- 使用 SQLAlchemy 2.0 `Mapped` / `mapped_column` 语法
- 关系字段使用 `relationship()` + `back_populates`
- 字符串字段指定 `String(length)` 避免无限制

### 迁移

- 生产环境通过 Alembic 管理迁移
- 开发环境 `init_db()` 的 `_migrate_columns()` 仅作降级方案
- 迁移文件命名：`YYYYMMDD_NNNN_description.py`

## 测试规范

### 三层标记

```python
@pytest.mark.unit          # 单个函数/类的隔离测试
@pytest.mark.integration   # 跨模块协作测试
@pytest.mark.system        # 端到端完整流程测试
```

### 测试隔离

- 每个测试使用独立内存 SQLite
- 不依赖测试执行顺序
- 不修改共享文件系统状态

### 命名

- 测试文件：`test_<被测模块>.py`
- 测试函数：`test_<行为>_<条件>`（如 `test_bkt_update_correct_answer_increases_mastery`）

## API 规范

### 响应格式

所有 API 响应使用统一信封：

```json
{"code": 200, "message": "success", "data": {...}}
```

工厂函数 `success()` / `error()` / `not_found()` 在 `schemas/common.py` 中定义。

### 路由命名

- 资源用复数：`/questions`, `/users`
- 嵌套不超过 2 层：`/users/{id}/mastery`
- 动作用动词：`/questions/random`, `/mastery/{id}/answer`

## 前端规范

- 原生 JS，无构建工具
- 模块化：每个功能独立 JS 文件
- API 调用统一通过 `utils.js` 的 `fetchAPI()` 函数
- 样式集中在 `css/styles.css`
