"""
阶段4 单元测试：知识图谱引擎。

测试范围：
- 节点和边的添加
- 前置依赖查找（直接和递归）
- 后续依赖查找
- 关联知识点查找
- 拓扑排序
- 环检测
- 学习路径生成
- 可视化数据导出
- 从数据库构建图谱
"""
import pytest

from app.engines.knowledge_graph import (
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
    KnowledgeGraphBuilder,
    VisualizationData,
)


def make_node(node_id: int, code: str, name: str, subject="会计", chapter="ch1", difficulty=3):
    """创建测试用节点。"""
    return GraphNode(
        id=node_id, code=code, name=name,
        subject=subject, chapter=chapter, difficulty=difficulty,
    )


@pytest.mark.unit
class TestGraphNodeEdge:
    """测试节点和边的基础操作。"""

    def test_add_node(self):
        graph = KnowledgeGraph()
        node = make_node(1, "KP-01", "借贷记账法")
        graph.add_node(node)

        assert graph.get_node(1) is not None
        assert graph.get_node(1).name == "借贷记账法"

    def test_add_edge(self):
        graph = KnowledgeGraph()
        graph.add_node(make_node(1, "KP-01", "基础"))
        graph.add_node(make_node(2, "KP-02", "进阶"))
        graph.add_edge(GraphEdge(1, 2, "prerequisite"))

        assert len(graph.adjacency[1]) == 1
        assert len(graph.reverse_adjacency[2]) == 1

    def test_get_nonexistent_node(self):
        graph = KnowledgeGraph()
        assert graph.get_node(999) is None


@pytest.mark.unit
class TestPrerequisites:
    """测试前置依赖查找。"""

    def _build_chain(self):
        """构建链式依赖：1→2→3→4 (1是2的前置, 2是3的前置, ...)"""
        graph = KnowledgeGraph()
        for i in range(1, 5):
            graph.add_node(make_node(i, f"KP-{i:02d}", f"知识点{i}"))
        graph.add_edge(GraphEdge(1, 2, "prerequisite"))
        graph.add_edge(GraphEdge(2, 3, "prerequisite"))
        graph.add_edge(GraphEdge(3, 4, "prerequisite"))
        return graph

    def test_direct_prerequisites(self):
        """获取直接前置知识点。"""
        graph = self._build_chain()
        prereqs = graph.get_prerequisites(3)
        assert len(prereqs) == 1
        assert prereqs[0].id == 2

    def test_all_prerequisites(self):
        """递归获取所有前置知识点。"""
        graph = self._build_chain()
        all_prereqs = graph.get_all_prerequisites(4)
        prereq_ids = {n.id for n in all_prereqs}
        assert prereq_ids == {1, 2, 3}

    def test_no_prerequisites(self):
        """没有前置依赖的节点应返回空列表。"""
        graph = self._build_chain()
        assert graph.get_prerequisites(1) == []
        assert graph.get_all_prerequisites(1) == []

    def test_prerequisites_exclude_related(self):
        """前置查找应排除 related 类型的边。"""
        graph = KnowledgeGraph()
        graph.add_node(make_node(1, "A", "A"))
        graph.add_node(make_node(2, "B", "B"))
        graph.add_edge(GraphEdge(1, 2, "related"))
        assert graph.get_prerequisites(2) == []


@pytest.mark.unit
class TestDependents:
    """测试后续依赖查找。"""

    def test_get_dependents(self):
        """获取依赖此知识点的后续知识点。"""
        graph = KnowledgeGraph()
        graph.add_node(make_node(1, "KP-01", "基础"))
        graph.add_node(make_node(2, "KP-02", "进阶A"))
        graph.add_node(make_node(3, "KP-03", "进阶B"))
        graph.add_edge(GraphEdge(1, 2, "prerequisite"))
        graph.add_edge(GraphEdge(1, 3, "prerequisite"))

        dependents = graph.get_dependents(1)
        dependent_ids = {n.id for n in dependents}
        assert dependent_ids == {2, 3}


@pytest.mark.unit
class TestRelated:
    """测试关联知识点查找。"""

    def test_get_related(self):
        """获取关联知识点（双向）。"""
        graph = KnowledgeGraph()
        graph.add_node(make_node(1, "A", "A"))
        graph.add_node(make_node(2, "B", "B"))
        graph.add_node(make_node(3, "C", "C"))
        graph.add_edge(GraphEdge(1, 2, "related"))
        graph.add_edge(GraphEdge(3, 1, "related"))

        related = graph.get_related(1)
        related_ids = {n.id for n in related}
        assert related_ids == {2, 3}

    def test_related_excludes_prerequisite(self):
        """关联查找应排除 prerequisite 类型的边。"""
        graph = KnowledgeGraph()
        graph.add_node(make_node(1, "A", "A"))
        graph.add_node(make_node(2, "B", "B"))
        graph.add_edge(GraphEdge(1, 2, "prerequisite"))
        assert graph.get_related(1) == []


@pytest.mark.unit
class TestTopologicalSort:
    """测试拓扑排序。"""

    def test_simple_order(self):
        """简单链式依赖的拓扑排序。"""
        graph = KnowledgeGraph()
        for i in range(1, 4):
            graph.add_node(make_node(i, f"KP-{i}", f"KP{i}"))
        graph.add_edge(GraphEdge(1, 2, "prerequisite"))
        graph.add_edge(GraphEdge(2, 3, "prerequisite"))

        sorted_nodes = graph.topological_sort()
        ids = [n.id for n in sorted_nodes]
        assert ids == [1, 2, 3]

    def test_diamond_dependency(self):
        """菱形依赖：1→2, 1→3, 2→4, 3→4。"""
        graph = KnowledgeGraph()
        for i in range(1, 5):
            graph.add_node(make_node(i, f"KP-{i}", f"KP{i}"))
        graph.add_edge(GraphEdge(1, 2, "prerequisite"))
        graph.add_edge(GraphEdge(1, 3, "prerequisite"))
        graph.add_edge(GraphEdge(2, 4, "prerequisite"))
        graph.add_edge(GraphEdge(3, 4, "prerequisite"))

        sorted_nodes = graph.topological_sort()
        ids = [n.id for n in sorted_nodes]
        assert ids[0] == 1  # 1 必须在最前
        assert ids[-1] == 4  # 4 必须在最后
        assert set(ids[1:3]) == {2, 3}  # 2 和 3 在中间

    def test_cycle_detection_true(self):
        """存在环时应检测到。"""
        graph = KnowledgeGraph()
        for i in range(1, 4):
            graph.add_node(make_node(i, f"KP-{i}", f"KP{i}"))
        graph.add_edge(GraphEdge(1, 2, "prerequisite"))
        graph.add_edge(GraphEdge(2, 3, "prerequisite"))
        graph.add_edge(GraphEdge(3, 1, "prerequisite"))  # 形成环

        assert graph.detect_cycle() is True

    def test_cycle_detection_false(self):
        """无环时应返回 False。"""
        graph = KnowledgeGraph()
        for i in range(1, 4):
            graph.add_node(make_node(i, f"KP-{i}", f"KP{i}"))
        graph.add_edge(GraphEdge(1, 2, "prerequisite"))
        graph.add_edge(GraphEdge(2, 3, "prerequisite"))

        assert graph.detect_cycle() is False

    def test_topological_sort_with_cycle_raises(self):
        """有环时拓扑排序应抛出异常。"""
        graph = KnowledgeGraph()
        graph.add_node(make_node(1, "A", "A"))
        graph.add_node(make_node(2, "B", "B"))
        graph.add_edge(GraphEdge(1, 2, "prerequisite"))
        graph.add_edge(GraphEdge(2, 1, "prerequisite"))

        with pytest.raises(ValueError, match="循环依赖"):
            graph.topological_sort()


@pytest.mark.unit
class TestLearningPath:
    """测试学习路径生成。"""

    def test_learning_path(self):
        """生成到目标知识点的学习路径。"""
        graph = KnowledgeGraph()
        for i in range(1, 5):
            graph.add_node(make_node(i, f"KP-{i}", f"KP{i}"))
        graph.add_edge(GraphEdge(1, 2, "prerequisite"))
        graph.add_edge(GraphEdge(2, 3, "prerequisite"))
        graph.add_edge(GraphEdge(3, 4, "prerequisite"))

        path = graph.get_learning_path(4)
        ids = [n.id for n in path]
        assert ids == [1, 2, 3, 4]

    def test_learning_path_no_prerequisites(self):
        """无前置依赖的知识点，路径只包含自身。"""
        graph = KnowledgeGraph()
        graph.add_node(make_node(1, "KP-01", "基础"))
        path = graph.get_learning_path(1)
        assert len(path) == 1
        assert path[0].id == 1


@pytest.mark.unit
class TestVisualization:
    """测试可视化数据导出。"""

    def test_to_visualization(self):
        """导出数据应包含正确的节点和边。"""
        graph = KnowledgeGraph()
        graph.add_node(make_node(1, "A", "知识点A", difficulty=2))
        graph.add_node(make_node(2, "B", "知识点B", difficulty=4))
        graph.add_edge(GraphEdge(1, 2, "prerequisite"))

        viz = graph.to_visualization()

        assert isinstance(viz, VisualizationData)
        assert len(viz.nodes) == 2
        assert len(viz.edges) == 1
        assert viz.nodes[0]["label"] == "知识点A"
        assert viz.edges[0]["source"] == 1
        assert viz.edges[0]["target"] == 2
        assert viz.edges[0]["label"] == "prerequisite"

    def test_to_dict(self):
        """to_dict 应返回可序列化的字典。"""
        graph = KnowledgeGraph()
        graph.add_node(make_node(1, "A", "A"))
        viz = graph.to_visualization()
        d = viz.to_dict()
        assert "nodes" in d
        assert "edges" in d


@pytest.mark.unit
class TestBuildFromDb:
    """测试从数据库构建知识图谱。"""

    def test_build_from_db(self, db_session):
        """从数据库构建图谱应包含所有知识点和边。"""
        from app.models import KnowledgeEdge, KnowledgePoint

        kp1 = KnowledgePoint(code="DB-01", name="基础", subject="会计", chapter="ch1", difficulty=2)
        kp2 = KnowledgePoint(code="DB-02", name="进阶", subject="会计", chapter="ch2", difficulty=4)
        db_session.add_all([kp1, kp2])
        db_session.flush()

        edge = KnowledgeEdge(source_id=kp1.id, target_id=kp2.id, relation_type="prerequisite")
        db_session.add(edge)
        db_session.commit()

        graph = KnowledgeGraphBuilder.build_from_db(db_session)

        assert len(graph.nodes) == 2
        assert graph.get_prerequisites(kp2.id)[0].id == kp1.id

    def test_build_filtered_by_subject(self, db_session):
        """按科目过滤应只返回该科目的知识点。"""
        from app.models import KnowledgePoint

        db_session.add_all([
            KnowledgePoint(code="S1-01", name="会计KP", subject="会计", chapter="ch1"),
            KnowledgePoint(code="S2-01", name="税法KP", subject="税法", chapter="ch1"),
        ])
        db_session.commit()

        graph = KnowledgeGraphBuilder.build_from_db(db_session, subject="会计")
        assert len(graph.nodes) == 1
        assert list(graph.nodes.values())[0].subject == "会计"
