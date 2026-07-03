"""
实体仓库层。

每个 Repository 封装对应模型的查询逻辑，
路由层通过 DI 注入 Repository 实例访问数据。

添加新仓库时：
1. 继承 BaseRepository[Model]
2. 设置 model 类属性
3. 添加特定查询方法
4. 在 deps.py 中注册依赖函数
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.repository import BaseRepository
from app.models import Question, User, KnowledgePoint, UserMastery


class UserRepository(BaseRepository[User]):
    """用户数据访问。"""

    model = User

    def find_by_email(self, email: str) -> User | None:
        """根据邮箱查询用户。"""
        return self.db.scalar(
            select(User).where(User.email == email)
        )

    def get_profile(self, user_id: int):
        """获取用户画像。"""
        from app.models import UserProfile

        return self.db.scalar(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )


class QuestionRepository(BaseRepository[Question]):
    """题目数据访问。"""

    model = Question

    def get_random(self, kp_code: str | None = None, limit: int = 10) -> list[Question]:
        """随机获取题目，可按知识点筛选。"""
        from sqlalchemy import func

        stmt = select(Question).order_by(func.random()).limit(limit)
        return list(self.db.scalars(stmt).all())

    def get_by_kp(self, kp_id: int, limit: int = 10) -> list[Question]:
        """按知识点 ID 获取题目。"""
        return list(
            self.db.scalars(
                select(Question)
                .where(Question.knowledge_point_id == kp_id)
                .limit(limit)
            ).all()
        )

    def count_all(self) -> int:
        """统计题目总数。"""
        from sqlalchemy import func

        return self.db.scalar(
            select(func.count()).select_from(Question)
        ) or 0


class KnowledgePointRepository(BaseRepository[KnowledgePoint]):
    """知识点数据访问。"""

    model = KnowledgePoint

    def get_by_code(self, code: str) -> KnowledgePoint | None:
        """按知识点编码查询。"""
        return self.db.scalar(
            select(KnowledgePoint).where(KnowledgePoint.code == code)
        )

    def get_by_subject(self, subject: str) -> list[KnowledgePoint]:
        """按科目获取所有知识点。"""
        return list(
            self.db.scalars(
                select(KnowledgePoint).where(KnowledgePoint.subject == subject)
            ).all()
        )


class MasteryRepository(BaseRepository[UserMastery]):
    """掌握度数据访问。"""

    model = UserMastery

    def get_or_create(self, user_id: int, kp_id: int) -> UserMastery:
        """获取或创建掌握度记录。"""
        mastery = self.db.scalar(
            select(UserMastery).where(
                UserMastery.user_id == user_id,
                UserMastery.knowledge_point_id == kp_id,
            )
        )
        if mastery is None:
            mastery = UserMastery(user_id=user_id, knowledge_point_id=kp_id)
            self.db.add(mastery)
            self.db.flush()
        return mastery

    def get_user_mastery_batch(self, user_id: int) -> list[UserMastery]:
        """批量获取用户所有知识点掌握度。"""
        return list(
            self.db.scalars(
                select(UserMastery).where(UserMastery.user_id == user_id)
            ).all()
        )


# ========== 依赖注入函数 ==========

def get_user_repository(db: Session = None) -> UserRepository:
    """获取用户仓库实例。配合 FastAPI Depends 使用。"""
    from app.db.session import get_db
    from fastapi import Depends
    if db is None:
        db = Depends(get_db)
    return UserRepository(db)


def get_question_repository(db: Session = None) -> QuestionRepository:
    """获取题目仓库实例。"""
    from app.db.session import get_db
    from fastapi import Depends
    if db is None:
        db = Depends(get_db)
    return QuestionRepository(db)
