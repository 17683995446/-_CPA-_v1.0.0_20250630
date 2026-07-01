"""
知识点与知识图谱路由。

业务规范：
- 知识点按科目过滤查询
- 知识图谱可视化数据兼容前端图表库
- 学习路径遵循前置依赖拓扑排序
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.engines.knowledge_graph import KnowledgeGraphBuilder
from app.models import KnowledgeEdge, KnowledgePoint
from app.schemas.knowledge import (
    KnowledgeGraphResponse,
    KnowledgePointCreate,
    KnowledgePointResponse,
    LearningPathResponse,
)

router = APIRouter(prefix="/api/knowledge", tags=["知识图谱"])


@router.get("/points", response_model=list[KnowledgePointResponse])
def list_knowledge_points(
    subject: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """查询知识点列表（可按科目过滤）。"""
    query = db.query(KnowledgePoint)
    if subject:
        query = query.filter(KnowledgePoint.subject == subject)
    return query.all()


@router.get("/points/{kp_id}", response_model=KnowledgePointResponse)
def get_knowledge_point(kp_id: int, db: Session = Depends(get_db)):
    """获取知识点详情。"""
    kp = db.query(KnowledgePoint).filter(KnowledgePoint.id == kp_id).first()
    if kp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知识点 {kp_id} 不存在",
        )
    return kp


@router.post("/points", response_model=KnowledgePointResponse, status_code=status.HTTP_201_CREATED)
def create_knowledge_point(req: KnowledgePointCreate, db: Session = Depends(get_db)):
    """创建知识点。"""
    if db.query(KnowledgePoint).filter(KnowledgePoint.code == req.code).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"知识点编码 {req.code} 已存在",
        )

    kp = KnowledgePoint(
        code=req.code,
        name=req.name,
        subject=req.subject,
        chapter=req.chapter,
        description=req.description,
        difficulty=req.difficulty,
        mastery_default=req.mastery_default,
    )
    db.add(kp)
    db.commit()
    db.refresh(kp)
    return kp


@router.get("/graph", response_model=KnowledgeGraphResponse)
def get_knowledge_graph(
    subject: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """获取知识图谱可视化数据。"""
    graph = KnowledgeGraphBuilder.build_from_db(db, subject=subject)
    viz = graph.to_visualization()
    return KnowledgeGraphResponse(nodes=viz.nodes, edges=viz.edges)


@router.get("/graph/learning-path/{kp_id}", response_model=LearningPathResponse)
def get_learning_path(kp_id: int, db: Session = Depends(get_db)):
    """获取到目标知识点的学习路径。"""
    kp = db.query(KnowledgePoint).filter(KnowledgePoint.id == kp_id).first()
    if kp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知识点 {kp_id} 不存在",
        )

    graph = KnowledgeGraphBuilder.build_from_db(db)
    try:
        path_nodes = graph.get_learning_path(kp_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    path = [
        KnowledgePointResponse(
            id=n.id,
            code=n.code,
            name=n.name,
            subject=n.subject,
            chapter=n.chapter,
            description=n.description,
            difficulty=n.difficulty,
            mastery_default=0.1,
        )
        for n in path_nodes
    ]
    return LearningPathResponse(target_kp_id=kp_id, path=path)


@router.get("/graph/neighbors/{kp_id}")
def get_kp_neighbors(kp_id: int, db: Session = Depends(get_db)):
    """获取单个知识点的邻居关系图谱数据。

    返回中心知识点及其前置、后续、关联知识点，用于思维导图视图。
    """
    kp = db.query(KnowledgePoint).filter(KnowledgePoint.id == kp_id).first()
    if kp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知识点 {kp_id} 不存在",
        )

    graph = KnowledgeGraphBuilder.build_from_db(db)
    center_node = graph.get_node(kp_id)
    if center_node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知识点 {kp_id} 不在图谱中",
        )

    prerequisites = graph.get_prerequisites(kp_id)
    dependents = graph.get_dependents(kp_id)
    related = graph.get_related(kp_id)

    def node_dict(n, role):
        return {
            "id": n.id,
            "name": n.name,
            "code": n.code,
            "subject": n.subject,
            "chapter": n.chapter,
            "difficulty": n.difficulty,
            "description": n.description,
            "role": role,
        }

    nodes = [node_dict(center_node, "center")]
    seen_ids = {kp_id}

    for n in prerequisites:
        if n.id not in seen_ids:
            nodes.append(node_dict(n, "prerequisite"))
            seen_ids.add(n.id)
    for n in dependents:
        if n.id not in seen_ids:
            nodes.append(node_dict(n, "dependent"))
            seen_ids.add(n.id)
    for n in related:
        if n.id not in seen_ids:
            nodes.append(node_dict(n, "related"))
            seen_ids.add(n.id)

    edges = []
    for n in prerequisites:
        edges.append({"source": n.id, "target": kp_id, "label": "前置依赖"})
    for n in dependents:
        edges.append({"source": kp_id, "target": n.id, "label": "后续应用"})
    for n in related:
        edges.append({"source": kp_id, "target": n.id, "label": "关联知识"})

    return {"center_id": kp_id, "nodes": nodes, "edges": edges}


@router.post("/edges", status_code=status.HTTP_201_CREATED)
def create_knowledge_edge(
    source_id: int,
    target_id: int,
    relation_type: str = "prerequisite",
    db: Session = Depends(get_db),
):
    """创建知识点关联边。"""
    for kid, label in [(source_id, "source"), (target_id, "target")]:
        if not db.query(KnowledgePoint).filter(KnowledgePoint.id == kid).first():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{label} 知识点 {kid} 不存在",
            )

    edge = KnowledgeEdge(
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
    )
    db.add(edge)
    db.commit()
    db.refresh(edge)
    return {"id": edge.id, "source_id": source_id, "target_id": target_id, "relation_type": relation_type}
