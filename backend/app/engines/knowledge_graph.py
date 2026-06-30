"""
知识图谱引擎。

第一性原理：知识不是孤立的点，而是有结构的网络。
知识点之间的前置依赖关系决定了学习路径——先学基础才能学进阶。
知识图谱引擎负责构建、遍历和分析这个网络。

核心功能：
- 从数据库构建知识图谱
- 前置依赖链分析（BFS 遍历）
- 学习路径生成（拓扑排序）
- 环检测（防止循环依赖）
- 可视化数据导出（供前端渲染）
- 关联知识点推荐

业务规范：
- CPA 知识体系按「科目→章节→知识点」组织
- 知识点间存在 prerequisite（前置）、related（关联）、parent（包含）关系
- 学习路径应遵循前置依赖顺序
"""
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.models import KnowledgeEdge, KnowledgePoint


@dataclass
class GraphNode:
    """知识图谱节点。"""
    id: int
    code: str
    name: str
    subject: str
    chapter: str
    difficulty: int
    description: Optional[str] = None


@dataclass
class GraphEdge:
    """知识图谱边。"""
    source_id: int
    target_id: int
    relation_type: str  # prerequisite / related / parent


@dataclass
class VisualizationData:
    """可视化导出数据（供前端 AntV G6 / React Flow 渲染）。"""
    nodes: list[dict] = field(default_factory=list)
    edges: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"nodes": self.nodes, "edges": self.edges}


class KnowledgeGraph:
    """
    知识图谱：内存中的图结构。

    用邻接表存储边，支持高效的遍历操作。
    """

    def __init__(self):
        self.nodes: dict[int, GraphNode] = {}
        # 邻接表：node_id → [(target_id, relation_type)]
        self.adjacency: dict[int, list[tuple[int, str]]] = {}
        # 反向邻接表：node_id → [(source_id, relation_type)]
        self.reverse_adjacency: dict[int, list[tuple[int, str]]] = {}

    def add_node(self, node: GraphNode) -> None:
        """添加节点。"""
        self.nodes[node.id] = node
        if node.id not in self.adjacency:
            self.adjacency[node.id] = []
        if node.id not in self.reverse_adjacency:
            self.reverse_adjacency[node.id] = []

    def add_edge(self, edge: GraphEdge) -> None:
        """添加边。"""
        if edge.source_id not in self.adjacency:
            self.adjacency[edge.source_id] = []
        self.adjacency[edge.source_id].append((edge.target_id, edge.relation_type))

        if edge.target_id not in self.reverse_adjacency:
            self.reverse_adjacency[edge.target_id] = []
        self.reverse_adjacency[edge.target_id].append(
            (edge.source_id, edge.relation_type)
        )

    def get_node(self, node_id: int) -> Optional[GraphNode]:
        """获取节点。"""
        return self.nodes.get(node_id)

    def get_prerequisites(self, node_id: int) -> list[GraphNode]:
        """
        获取直接前置知识点。

        前置关系：source → target (prerequisite)
        即 source 是 target 的前置。
        在反向邻接表中查找 relation_type == "prerequisite" 的源节点。
        """
        result = []
        for source_id, rel in self.reverse_adjacency.get(node_id, []):
            if rel == "prerequisite":
                node = self.nodes.get(source_id)
                if node:
                    result.append(node)
        return result

    def get_all_prerequisites(self, node_id: int) -> list[GraphNode]:
        """
        获取所有前置知识点（递归，BFS 遍历）。

        返回按依赖顺序排列的所有前置知识点列表。
        """
        visited: set[int] = set()
        result: list[GraphNode] = []
        queue: deque[int] = deque([node_id])

        while queue:
            current = queue.popleft()
            for source_id, rel in self.reverse_adjacency.get(current, []):
                if rel == "prerequisite" and source_id not in visited:
                    visited.add(source_id)
                    node = self.nodes.get(source_id)
                    if node:
                        result.append(node)
                        queue.append(source_id)

        return result

    def get_dependents(self, node_id: int) -> list[GraphNode]:
        """
        获取直接依赖此知识点的后续知识点。
        """
        result = []
        for target_id, rel in self.adjacency.get(node_id, []):
            if rel == "prerequisite":
                node = self.nodes.get(target_id)
                if node:
                    result.append(node)
        return result

    def get_related(self, node_id: int) -> list[GraphNode]:
        """获取关联知识点（非前置依赖的关联）。"""
        result = []
        seen: set[int] = set()
        for target_id, rel in self.adjacency.get(node_id, []):
            if rel == "related" and target_id not in seen:
                node = self.nodes.get(target_id)
                if node:
                    result.append(node)
                    seen.add(target_id)
        for source_id, rel in self.reverse_adjacency.get(node_id, []):
            if rel == "related" and source_id not in seen:
                node = self.nodes.get(source_id)
                if node:
                    result.append(node)
                    seen.add(source_id)
        return result

    def topological_sort(self) -> list[GraphNode]:
        """
        拓扑排序：生成学习路径。

        前置知识点排在前面，后续知识点排在后面。
        如果存在环，则抛出 ValueError。
        """
        in_degree: dict[int, int] = {nid: 0 for nid in self.nodes}

        for node_id in self.nodes:
            for target_id, rel in self.adjacency.get(node_id, []):
                if rel == "prerequisite":
                    in_degree[target_id] = in_degree.get(target_id, 0) + 1

        queue: deque[int] = deque(
            nid for nid, deg in in_degree.items() if deg == 0
        )
        result: list[GraphNode] = []

        while queue:
            current = queue.popleft()
            node = self.nodes.get(current)
            if node:
                result.append(node)

            for target_id, rel in self.adjacency.get(current, []):
                if rel == "prerequisite":
                    in_degree[target_id] -= 1
                    if in_degree[target_id] == 0:
                        queue.append(target_id)

        if len(result) != len(self.nodes):
            raise ValueError("知识图谱中存在循环依赖，无法生成学习路径")

        return result

    def detect_cycle(self) -> bool:
        """检测是否存在循环依赖（仅检查 prerequisite 关系）。"""
        in_degree: dict[int, int] = {nid: 0 for nid in self.nodes}

        for node_id in self.nodes:
            for target_id, rel in self.adjacency.get(node_id, []):
                if rel == "prerequisite":
                    in_degree[target_id] = in_degree.get(target_id, 0) + 1

        queue: deque[int] = deque(
            nid for nid, deg in in_degree.items() if deg == 0
        )
        processed = 0

        while queue:
            current = queue.popleft()
            processed += 1
            for target_id, rel in self.adjacency.get(current, []):
                if rel == "prerequisite":
                    in_degree[target_id] -= 1
                    if in_degree[target_id] == 0:
                        queue.append(target_id)

        return processed != len(self.nodes)

    def get_learning_path(self, target_node_id: int) -> list[GraphNode]:
        """
        生成到目标知识点的学习路径。

        返回从基础到目标知识点的有序列表，包含所有前置依赖。
        """
        all_prereqs = self.get_all_prerequisites(target_node_id)
        target = self.nodes.get(target_node_id)

        # 构建子图并拓扑排序
        sub_graph = KnowledgeGraph()
        node_ids = {target_node_id} | {n.id for n in all_prereqs}

        for nid in node_ids:
            node = self.nodes.get(nid)
            if node:
                sub_graph.add_node(node)

        for nid in node_ids:
            for target_id, rel in self.adjacency.get(nid, []):
                if target_id in node_ids and rel == "prerequisite":
                    sub_graph.add_edge(GraphEdge(nid, target_id, rel))

        return sub_graph.topological_sort()

    def to_visualization(self) -> VisualizationData:
        """
        导出可视化数据。

        格式兼容 AntV G6 / React Flow：
        - nodes: [{id, label, subject, chapter, difficulty}]
        - edges: [{source, target, label}]
        """
        viz = VisualizationData()

        for node_id, node in self.nodes.items():
            viz.nodes.append({
                "id": node_id,
                "label": node.name,
                "code": node.code,
                "subject": node.subject,
                "chapter": node.chapter,
                "difficulty": node.difficulty,
            })

        seen_edges: set[tuple[int, int, str]] = set()
        for source_id, edges in self.adjacency.items():
            for target_id, rel in edges:
                key = (source_id, target_id, rel)
                if key not in seen_edges:
                    seen_edges.add(key)
                    viz.edges.append({
                        "source": source_id,
                        "target": target_id,
                        "label": rel,
                    })

        return viz


class KnowledgeGraphBuilder:
    """
    知识图谱构建器：从数据库构建知识图谱。
    """

    @staticmethod
    def build_from_db(
        db: Session,
        subject: Optional[str] = None,
    ) -> KnowledgeGraph:
        """
        从数据库构建知识图谱。

        参数：
        - db: 数据库会话
        - subject: 可选，按科目过滤

        返回：KnowledgeGraph 实例
        """
        graph = KnowledgeGraph()

        # 加载知识点
        query = db.query(KnowledgePoint)
        if subject:
            query = query.filter(KnowledgePoint.subject == subject)

        for kp in query.all():
            graph.add_node(GraphNode(
                id=kp.id,
                code=kp.code,
                name=kp.name,
                subject=kp.subject,
                chapter=kp.chapter,
                difficulty=kp.difficulty,
                description=kp.description,
            ))

        # 加载边
        edge_query = db.query(KnowledgeEdge)
        for edge in edge_query.all():
            if edge.source_id in graph.nodes and edge.target_id in graph.nodes:
                graph.add_edge(GraphEdge(
                    source_id=edge.source_id,
                    target_id=edge.target_id,
                    relation_type=edge.relation_type,
                ))

        return graph

    @staticmethod
    def build_from_knowledge_points(
        points: list[KnowledgePoint],
        edges: list[KnowledgeEdge],
    ) -> KnowledgeGraph:
        """
        从知识点和边的列表构建图谱（用于测试）。
        """
        graph = KnowledgeGraph()

        for kp in points:
            graph.add_node(GraphNode(
                id=kp.id,
                code=kp.code,
                name=kp.name,
                subject=kp.subject,
                chapter=kp.chapter,
                difficulty=kp.difficulty,
                description=kp.description,
            ))

        for edge in edges:
            if edge.source_id in graph.nodes and edge.target_id in graph.nodes:
                graph.add_edge(GraphEdge(
                    source_id=edge.source_id,
                    target_id=edge.target_id,
                    relation_type=edge.relation_type,
                ))

        return graph
