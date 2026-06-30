"""
学习会话路由。

业务规范：
- 学习会话记录用户连续学习的时间段
- 会话结束时统计答题数、正确率、获得经验值
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import StudySession, User
from app.schemas.study import (
    StartSessionRequest,
    StudySessionResponse,
    UpdateSessionRequest,
)

router = APIRouter(prefix="/api/study", tags=["学习会话"])


@router.post("/sessions", response_model=StudySessionResponse, status_code=status.HTTP_201_CREATED)
def start_session(
    user_id: int,
    req: StartSessionRequest,
    db: Session = Depends(get_db),
):
    """开始学习会话。"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户 {user_id} 不存在",
        )

    session = StudySession(
        user_id=user_id,
        subject=req.subject,
        started_at=datetime.now(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions/{session_id}", response_model=StudySessionResponse)
def get_session(session_id: int, db: Session = Depends(get_db)):
    """获取学习会话详情。"""
    session = db.query(StudySession).filter(StudySession.id == session_id).first()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"学习会话 {session_id} 不存在",
        )
    return session


@router.patch("/sessions/{session_id}", response_model=StudySessionResponse)
def update_session(
    session_id: int,
    req: UpdateSessionRequest,
    db: Session = Depends(get_db),
):
    """更新学习会话（结束时调用）。"""
    session = db.query(StudySession).filter(StudySession.id == session_id).first()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"学习会话 {session_id} 不存在",
        )

    if req.ended_at is not None:
        session.ended_at = req.ended_at
    elif req.questions_answered is not None or req.correct_count is not None or req.xp_earned is not None:
        # 如果有统计数据更新但未指定结束时间，自动设置
        if session.ended_at is None:
            session.ended_at = datetime.now()

    if req.questions_answered is not None:
        session.questions_answered = req.questions_answered
    if req.correct_count is not None:
        session.correct_count = req.correct_count
    if req.xp_earned is not None:
        session.xp_earned = req.xp_earned

    db.commit()
    db.refresh(session)
    return session


@router.get("/{user_id}/sessions", response_model=list[StudySessionResponse])
def list_user_sessions(
    user_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """获取用户的学习会话历史。"""
    sessions = (
        db.query(StudySession)
        .filter(StudySession.user_id == user_id)
        .order_by(StudySession.started_at.desc())
        .limit(limit)
        .all()
    )
    return sessions
