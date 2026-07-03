"""
数据访问 Repository 基类。

架构规范：
- 路由层通过 Repository 访问数据，不直接 db.query()
- Repository 封装查询逻辑，返回 ORM 模型实例
- 复杂查询集中在 Repository 中，路由层只调用方法

第一性原理：数据访问逻辑应集中管理，便于复用、测试和优化。
"""
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """通用数据访问基类，提供 CRUD 操作模板。

    子类只需指定 model 属性即可继承全部通用方法。
    特定查询方法在子类中扩展。

    Usage:
        class UserRepository(BaseRepository[User]):
            model = User

            def find_by_email(self, email: str) -> User | None:
                ...
    """

    model: type[ModelT]

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, entity_id: int) -> ModelT | None:
        """根据主键查询单条记录。"""
        return self.db.get(self.model, entity_id)

    def get_or_404(self, entity_id: int) -> ModelT:
        """根据主键查询，不存在则抛出 404。"""
        from fastapi import HTTPException, status

        entity = self.get_by_id(entity_id)
        if entity is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__name__} {entity_id} 不存在",
            )
        return entity

    def get_all(self, skip: int = 0, limit: int = 100) -> list[ModelT]:
        """分页查询全部记录。"""
        stmt = select(self.model).offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def count(self) -> int:
        """统计总记录数。"""
        from sqlalchemy import func

        return self.db.scalar(select(func.count()).select_from(self.model)) or 0

    def create(self, **kwargs: Any) -> ModelT:
        """创建记录。"""
        entity = self.model(**kwargs)
        self.db.add(entity)
        self.db.flush()
        return entity

    def delete(self, entity: ModelT) -> None:
        """删除记录。"""
        self.db.delete(entity)
        self.db.flush()

    def save(self) -> None:
        """提交事务。"""
        self.db.commit()
