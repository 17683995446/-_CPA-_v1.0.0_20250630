"""
游戏化相关 Schema。

业务规范：
- Streak：连续学习天数，配保护卡机制
- XP：答对题目、连续学习获得经验值
- 等级：指数增长的 XP 需求
- 成就：条件触发式解锁
"""
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class StreakResponse(BaseModel):
    """连续学习状态响应。"""

    streak_count: int
    max_streak: int
    protections: int
    last_study_date: Optional[date] = None


class UpdateStreakRequest(BaseModel):
    """更新连续学习请求。"""

    study_date: date = Field(..., description="学习日期")


class StreakUpdateResponse(BaseModel):
    """连续学习更新响应。"""

    streak: StreakResponse
    message: str
    streak_xp: int


class LevelInfoResponse(BaseModel):
    """等级信息响应。"""

    level: int
    current_level_xp: int
    next_level_xp: int
    progress: float


class AchievementResponse(BaseModel):
    """成就响应。"""

    code: str
    name: str
    description: str
    category: str
    xp_reward: int
    unlocked: bool = False
