"""
LLM 分析路由 — 智能分析相关 API 端点。

端点清单：
    POST /api/llm/similarity/build         构建 embedding 索引
    GET  /api/llm/similarity/{question_id}  相似题推荐
    POST /api/llm/explanation/{question_id} 增强单题解析
    POST /api/llm/explanation/batch         批量增强解析
    POST /api/llm/error-analysis            错题归因分析
    GET  /api/llm/error-analysis/{user_id}  获取归因历史
    GET  /api/llm/error-analysis/{user_id}/stats  错误类型统计
    POST /api/llm/report/{user_id}          生成诊断报告
    GET  /api/llm/report/{user_id}/latest   获取最新报告
    GET  /api/llm/report/{user_id}/history  报告历史
    GET  /api/llm/status                    LLM 状态查询
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.engines.analysis_engine import error_analysis_engine
from app.engines.explanation_engine import explanation_engine
from app.engines.llm_client import llm_client
from app.engines.report_engine import report_engine
from app.engines.similarity_engine import similarity_engine

router = APIRouter(prefix="/api/llm", tags=["智能分析"])


# ===== LLM 状态 =====

@router.get("/status")
async def llm_status():
    """查询 LLM 服务状态。"""
    return {
        "available": llm_client.available,
        "mode": "llm" if llm_client.available else "fallback",
    }


# ===== 相似题推荐 =====

@router.post("/similarity/build")
async def build_similarity_index(db: Session = Depends(get_db)):
    """构建全题库 embedding 索引（一次性操作）。"""
    stats = similarity_engine.build_index(db)
    return {"code": 200, "data": stats}


@router.get("/similarity/{question_id}")
async def recommend_similar(
    question_id: int,
    top_k: int = Query(5, ge=1, le=20),
    same_kp: bool = Query(False),
    db: Session = Depends(get_db),
):
    """推荐与指定题目最相似的题目。"""
    results = similarity_engine.recommend(db, question_id, top_k, same_kp)
    return {"code": 200, "data": results}


# ===== 智能解析增强 =====

@router.post("/explanation/batch")
async def batch_enhance_explanation(
    max_total: int = Query(100, ge=1, le=1000),
    only_short: bool = Query(True),
    db: Session = Depends(get_db),
):
    """批量增强题目解析。"""
    stats = explanation_engine.enhance_batch(db, max_total=max_total, only_short=only_short)
    return {"code": 200, "data": stats}


@router.post("/explanation/{question_id}")
async def enhance_explanation(question_id: int, db: Session = Depends(get_db)):
    """增强单道题目的解析（按需调用）。"""
    result = explanation_engine.enhance_question(db, question_id)
    if result is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return {"code": 200, "data": result}


# ===== 错题归因分析 =====

@router.post("/error-analysis")
async def analyze_error(
    user_id: int,
    question_id: int,
    user_answer: str,
    db: Session = Depends(get_db),
):
    """分析学生答错原因。"""
    try:
        record = error_analysis_engine.analyze(db, user_id, question_id, user_answer)
        return {
            "code": 200,
            "data": {
                "id": record.id,
                "error_type": record.error_type,
                "suggestion": record.suggestion,
                "related_concept": record.related_concept,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/error-analysis/{user_id}")
async def get_error_analyses(
    user_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """获取学生的错题归因历史。"""
    data = error_analysis_engine.get_user_analyses(db, user_id, limit)
    return {"code": 200, "data": data}


@router.get("/error-analysis/{user_id}/stats")
async def get_error_stats(user_id: int, db: Session = Depends(get_db)):
    """获取学生错误类型分布统计。"""
    data = error_analysis_engine.get_error_type_stats(db, user_id)
    return {"code": 200, "data": data}


# ===== 学习诊断报告 =====

@router.post("/report/{user_id}")
async def generate_report(
    user_id: int,
    report_type: str = Query("on_demand", pattern="^(weekly|monthly|on_demand)$"),
    db: Session = Depends(get_db),
):
    """生成学习诊断报告。"""
    record = report_engine.generate_report(db, user_id, report_type)
    import json
    return {
        "code": 200,
        "data": {
            "id": record.id,
            "summary": record.summary,
            "content": json.loads(record.content_json),
            "total_questions": record.total_questions,
            "accuracy_rate": record.accuracy_rate,
            "weak_points_count": record.weak_points_count,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        },
    }


@router.get("/report/{user_id}/latest")
async def get_latest_report(user_id: int, db: Session = Depends(get_db)):
    """获取学生最近的诊断报告。"""
    data = report_engine.get_latest_report(db, user_id)
    if data is None:
        return {"code": 200, "data": None, "message": "暂无报告"}
    return {"code": 200, "data": data}


@router.get("/report/{user_id}/history")
async def get_report_history(
    user_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """获取报告历史列表。"""
    data = report_engine.get_report_history(db, user_id, limit)
    return {"code": 200, "data": data}
