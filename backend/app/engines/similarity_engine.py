"""
相似题推荐引擎 — 基于 embedding 向量的语义匹配。

工作流程：
    1. build_index(): 全题库 embedding 一次性建索引，存入 question_embeddings 表
    2. recommend(): 给定一道题，计算余弦相似度，返回最相似的 N 道题

无 LLM 时降级为关键词匹配（基于题干共同词汇）。
"""
import json
import logging
import re
from collections import Counter

import numpy as np
from sqlalchemy.orm import Session

from app.config import settings
from app.engines.llm_client import llm_client
from app.models import Question, QuestionEmbedding
from app.models.knowledge import KnowledgePoint

logger = logging.getLogger("app.engines.similarity")


class SimilarityEngine:
    """相似题推荐引擎。"""

    def __init__(self) -> None:
        self._cache: dict[int, np.ndarray] = {}
        self._indexed: bool = False

    def build_index(self, db: Session, batch_size: int = 100) -> dict:
        """为全题库构建 embedding 索引。

        幂等：已有 embedding 的题目跳过，只处理新增题目。
        无 LLM 时跳过（相似题推荐降级为关键词匹配）。

        Returns:
            统计信息 dict
        """
        stats = {"total": 0, "embedded": 0, "skipped": 0, "failed": 0}

        all_questions = db.query(Question).all()
        stats["total"] = len(all_questions)

        if not llm_client.available:
            logger.info("LLM 不可用，跳过 embedding 索引构建（相似题将使用关键词匹配）")
            stats["skipped"] = stats["total"]
            return stats

        # 找出还没有 embedding 的题目
        existing_ids = {r.question_id for r in db.query(QuestionEmbedding).all()}
        to_embed = [q for q in all_questions if q.id not in existing_ids]

        if not to_embed:
            logger.info("所有题目已有 embedding，无需更新")
            stats["skipped"] = stats["total"]
            return stats

        logger.info("开始构建 embedding 索引: %d 道题待处理", len(to_embed))

        for i in range(0, len(to_embed), batch_size):
            batch = to_embed[i:i + batch_size]
            texts = [self._make_embed_text(q) for q in batch]

            vectors = llm_client.embed_batch(texts)

            for q, vec in zip(batch, vectors):
                if vec:
                    record = QuestionEmbedding(
                        question_id=q.id,
                        embedding_json=json.dumps(vec),
                        dim=len(vec),
                        model_name=settings.LLM_EMBEDDING_MODEL,
                    )
                    db.add(record)
                    stats["embedded"] += 1
                else:
                    stats["failed"] += 1

            db.commit()
            logger.info("  embedding 进度: %d/%d", i + len(batch), len(to_embed))

        # 清空缓存（索引已更新）
        self._cache.clear()
        self._indexed = False

        logger.info("Embedding 索引构建完成: embedded=%d, skipped=%d, failed=%d",
                    stats["embedded"], stats["skipped"], stats["failed"])
        return stats

    def recommend(
        self,
        db: Session,
        question_id: int,
        top_k: int = 5,
        same_kp: bool = False,
    ) -> list[dict]:
        """推荐与指定题目最相似的 N 道题。

        Args:
            db: 数据库会话
            question_id: 基准题目 ID
            top_k: 返回数量
            same_kp: 是否限定同一知识点

        Returns:
            [{"question_id": int, "content": str, "similarity": float, "kp_code": str}, ...]
        """
        base_q = db.query(Question).filter(Question.id == question_id).first()
        if not base_q:
            return []

        # 尝试 LLM embedding 相似度
        if llm_client.available:
            results = self._recommend_by_embedding(db, base_q, top_k, same_kp)
            if results:
                return results

        # 降级：关键词匹配
        return self._recommend_by_keywords(db, base_q, top_k, same_kp)

    def _recommend_by_embedding(
        self, db: Session, base_q: Question, top_k: int, same_kp: bool
    ) -> list[dict]:
        """基于 embedding 余弦相似度推荐。"""
        base_emb = db.query(QuestionEmbedding).filter(
            QuestionEmbedding.question_id == base_q.id
        ).first()

        if not base_emb:
            # 基准题没有 embedding，实时获取
            vec = llm_client.embed(self._make_embed_text(base_q))
            if not vec:
                return []
            base_vec = np.array(vec, dtype=np.float32)
        else:
            base_vec = np.array(json.loads(base_emb.embedding_json), dtype=np.float32)

        # 加载所有 embedding 到内存（一次性，后续从缓存读）
        if not self._indexed:
            self._load_cache(db)

        if not self._cache:
            return []

        base_norm = np.linalg.norm(base_vec)
        if base_norm == 0:
            return []

        scores = []
        for qid, vec in self._cache.items():
            if qid == base_q.id:
                continue
            vec_norm = np.linalg.norm(vec)
            if vec_norm == 0:
                continue
            cos_sim = float(np.dot(base_vec, vec) / (base_norm * vec_norm))
            scores.append((qid, cos_sim))

        scores.sort(key=lambda x: x[1], reverse=True)

        # 取 top_k * 2 条，然后过滤知识点
        candidates = scores[:top_k * 3]
        results = []
        for qid, sim in candidates:
            q = db.query(Question).filter(Question.id == qid).first()
            if not q:
                continue
            if same_kp and q.knowledge_point_id != base_q.knowledge_point_id:
                continue
            kp = db.query(KnowledgePoint).filter(
                KnowledgePoint.id == q.knowledge_point_id
            ).first()
            results.append({
                "question_id": qid,
                "content": q.content[:100],
                "similarity": round(sim, 4),
                "kp_code": kp.code if kp else "",
                "kp_name": kp.name if kp else "",
            })
            if len(results) >= top_k:
                break

        return results

    def _recommend_by_keywords(
        self, db: Session, base_q: Question, top_k: int, same_kp: bool
    ) -> list[dict]:
        """降级方案：基于题干关键词重叠度推荐。"""
        base_keywords = self._extract_keywords(base_q.content)
        if not base_keywords:
            return []

        query = db.query(Question).filter(Question.id != base_q.id)
        if same_kp:
            query = query.filter(Question.knowledge_point_id == base_q.knowledge_point_id)

        candidates = []
        for q in query.all():
            q_keywords = self._extract_keywords(q.content)
            if not q_keywords:
                continue
            # Jaccard 相似度
            intersection = len(base_keywords & q_keywords)
            union = len(base_keywords | q_keywords)
            sim = intersection / union if union > 0 else 0
            if sim > 0:
                candidates.append((q, sim))

        candidates.sort(key=lambda x: x[1], reverse=True)

        results = []
        for q, sim in candidates[:top_k]:
            kp = db.query(KnowledgePoint).filter(
                KnowledgePoint.id == q.knowledge_point_id
            ).first()
            results.append({
                "question_id": q.id,
                "content": q.content[:100],
                "similarity": round(sim, 4),
                "kp_code": kp.code if kp else "",
                "kp_name": kp.name if kp else "",
            })

        return results

    def _load_cache(self, db: Session) -> None:
        """将所有 embedding 加载到内存缓存。"""
        records = db.query(QuestionEmbedding).all()
        for r in records:
            try:
                vec = np.array(json.loads(r.embedding_json), dtype=np.float32)
                self._cache[r.question_id] = vec
            except (json.JSONDecodeError, ValueError):
                continue
        self._indexed = True
        logger.info("Embedding 缓存已加载: %d 条", len(self._cache))

    @staticmethod
    def _make_embed_text(q: Question) -> str:
        """将题目转换为适合 embedding 的文本。"""
        parts = [q.content]
        if q.explanation:
            parts.append(q.explanation[:200])
        return " ".join(parts)

    @staticmethod
    def _extract_keywords(text: str) -> set[str]:
        """提取中文关键词（简单分词：2-4字滑动窗口）。"""
        # 去除标点和数字
        clean = re.sub(r"[^\u4e00-\u9fff]", "", text)
        if len(clean) < 2:
            return set()
        # 2-gram 提取
        keywords = set()
        for i in range(len(clean) - 1):
            keywords.add(clean[i:i+2])
        return keywords


# 全局单例
similarity_engine = SimilarityEngine()
