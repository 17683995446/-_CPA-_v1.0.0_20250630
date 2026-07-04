"""
学习会话相关 Schema。

业务规范：
- 学习会话是用户连续学习的时间段
- 记录会话内的答题数、正确率、获得经验值
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class StartSessionRequest(BaseModel):
    """开始学习会话请求。"""

    subject: Optional[str] = Field(None, description="学习科目")


class StudySessionResponse(BaseModel):
    """学习会话响应。"""

    id: int
    user_id: int
    subject: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    questions_answered: int
    correct_count: int
    xp_earned: int

    model_config = ConfigDict(from_attributes=True)


class UpdateSessionRequest(BaseModel):
    """更新学习会话请求（结束会话时调用）。"""

    ended_at: Optional[datetime] = None
    questions_answered: Optional[int] = Field(None, ge=0, description="答题数（非负）")
    correct_count: Optional[int] = Field(None, ge=0, description="正确数（非负）")
    xp_earned: Optional[int] = Field(None, ge=0, description="获得经验值（非负）")
