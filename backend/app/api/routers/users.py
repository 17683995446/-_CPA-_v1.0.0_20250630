"""
用户管理路由。

业务规范：
- 用户注册时自动创建用户画像
- 密码使用 bcrypt 加 salt 哈希存储
- 用户画像包含备考计划和游戏化状态
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_user_or_404
from app.db.session import get_db
from app.models import User, UserProfile
from app.schemas.user import (
    UserCreate,
    UserProfileResponse,
    UserProfileUpdate,
    UserResponse,
)
from app.security import hash_password

router = APIRouter(prefix="/api/users", tags=["用户管理"])


@router.get("")
def search_users(
    username: str | None = Query(None, description="按用户名搜索"),
    db: Session = Depends(get_db),
) -> list[dict]:
    """搜索用户列表（用于登录时查找用户）。"""
    query = db.query(User)
    if username:
        query = query.filter(User.username == username)
    users = query.limit(10).all()
    return [
        {"id": u.id, "username": u.username, "email": u.email}
        for u in users
    ]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(req: UserCreate, db: Session = Depends(get_db)) -> UserResponse:
    """注册新用户。"""
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在",
        )
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="邮箱已注册",
        )

    user = User(
        username=req.username,
        email=req.email,
        password_hash=hash_password(req.password),
    )
    db.add(user)
    db.flush()

    profile = UserProfile(
        user_id=user.id,
        target_exam_date=req.target_exam_date,
        daily_goal_minutes=req.daily_goal_minutes,
    )
    db.add(profile)
    db.commit()
    db.refresh(user)

    return user


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user: User = Depends(get_user_or_404)) -> UserResponse:
    """获取用户信息。"""
    return user


@router.get("/{user_id}/profile", response_model=UserProfileResponse)
def get_user_profile(user_id: int, db: Session = Depends(get_db)) -> UserProfileResponse:
    """获取用户画像。"""
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户 {user_id} 的画像不存在",
        )
    return profile


@router.patch("/{user_id}/profile", response_model=UserProfileResponse)
def update_user_profile(
    user_id: int, req: UserProfileUpdate, db: Session = Depends(get_db)
) -> UserProfileResponse:
    """更新用户画像。"""
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户 {user_id} 的画像不存在",
        )

    if req.target_exam_date is not None:
        profile.target_exam_date = req.target_exam_date
    if req.daily_goal_minutes is not None:
        profile.daily_goal_minutes = req.daily_goal_minutes

    db.commit()
    db.refresh(profile)
    return profile
