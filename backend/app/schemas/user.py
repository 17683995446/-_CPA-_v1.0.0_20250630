"""
用户相关 Schema。

业务规范：
- 用户注册需提供用户名、邮箱、密码
- 用户画像包含备考计划和游戏化状态
"""
from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """用户注册请求。"""

    username: str = Field(..., min_length=2, max_length=64, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=128, description="密码")
    target_exam_date: Optional[date] = Field(None, description="目标考试日期")
    daily_goal_minutes: int = Field(60, ge=10, le=480, description="每日学习目标（分钟）")


class UserResponse(BaseModel):
    """用户信息响应。"""

    id: int
    username: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class UserProfileResponse(BaseModel):
    """用户画像响应。"""

    user_id: int
    target_exam_date: Optional[date] = None
    daily_goal_minutes: int
    current_level: int
    total_xp: int

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    """用户画像更新请求。"""

    target_exam_date: Optional[date] = None
    daily_goal_minutes: Optional[int] = Field(None, ge=10, le=480)
