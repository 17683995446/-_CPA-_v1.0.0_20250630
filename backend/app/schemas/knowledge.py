"""
知识图谱相关 Schema。

业务规范：
- 知识点按「科目 → 章节 → 知识点」三级层次组织
- 知识图谱可视化数据兼容 AntV G6 / React Flow
- 学习路径遵循前置依赖顺序
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class KnowledgePointCreate(BaseModel):
    """知识点创建请求。"""

    code: str = Field(..., max_length=32, description="知识点编码")
    name: str = Field(..., max_length=128, description="知识点名称")
    subject: str = Field(..., max_length=32, description="所属科目")
    chapter: str = Field(..., max_length=64, description="章节")
    description: Optional[str] = None
    difficulty: int = Field(3, ge=1, le=5, description="难度 1-5")
    mastery_default: float = Field(0.1, ge=0.0, le=1.0, description="默认掌握概率")


class KnowledgePointResponse(BaseModel):
    """知识点响应。"""

    id: int
    code: str
    name: str
    subject: str
    chapter: str
    description: Optional[str] = None
    difficulty: int
    mastery_default: float

    model_config = ConfigDict(from_attributes=True)


class KnowledgeEdgeResponse(BaseModel):
    """知识图谱边响应。"""

    source: int
    target: int
    label: str


class KnowledgeGraphResponse(BaseModel):
    """知识图谱可视化数据。"""

    nodes: list[dict] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)


class LearningPathResponse(BaseModel):
    """学习路径响应。"""

    target_kp_id: int
    path: list[KnowledgePointResponse]
