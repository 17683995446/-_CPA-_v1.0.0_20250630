"""
智能解析增强引擎 — LLM 批量增强题目解析。

对现有题目的 explanation/simple_explanation/mnemonic/study_tip 四模块
进行 LLM 增强或回退到模板化增强。

设计原则：
    - 幂等：已有 LLM 增强的题目跳过
    - 批处理：支持分批调用 API
    - 降级：无 LLM 时使用 _enhance_explanations 的规则逻辑
"""
import json
import logging
import re

from sqlalchemy.orm import Session

from app.engines.llm_client import llm_client
from app.models import Question
from app.models.knowledge import KnowledgePoint

logger = logging.getLogger("app.engines.explanation")


# 标记字段：增强后的 explanation 前缀，用于幂等判断
_LLM_ENHANCED_MARKER = "【深度解析】"


class ExplanationEngine:
    """智能解析增强引擎。"""

    def enhance_batch(
        self,
        db: Session,
        batch_size: int = 20,
        max_total: int = 100,
        only_short: bool = True,
    ) -> dict:
        """批量增强题目解析。

        Args:
            db: 数据库会话
            batch_size: 每批 API 调用的题目数
            max_total: 本次最多增强的题目数
            only_short: True=只增强解析过短(<20字)的题目；False=增强全部

        Returns:
            统计信息 dict
        """
        stats = {"total": 0, "enhanced": 0, "skipped": 0, "failed": 0}

        query = db.query(Question)
        if only_short:
            # 只增强解析过短的题目（SQLite 不支持 length()，用 func.length）
            from sqlalchemy import func, or_
            query = query.filter(
                or_(
                    Question.explanation.is_(None),
                    Question.explanation == "",
                    func.length(Question.explanation) < 20,
                )
            )

        questions = query.limit(max_total).all()
        stats["total"] = len(questions)

        if not questions:
            logger.info("没有需要增强的题目")
            return stats

        if not llm_client.available:
            logger.info("LLM 不可用，跳过解析增强（使用现有解析）")
            stats["skipped"] = stats["total"]
            return stats

        logger.info("开始批量增强解析: %d 道题", len(questions))

        for i in range(0, len(questions), batch_size):
            batch = questions[i:i + batch_size]
            for q in batch:
                success = self._enhance_single(db, q)
                if success:
                    stats["enhanced"] += 1
                else:
                    stats["failed"] += 1
            db.commit()
            logger.info("  解析增强进度: %d/%d", i + len(batch), len(questions))

        logger.info("解析增强完成: enhanced=%d, skipped=%d, failed=%d",
                    stats["enhanced"], stats["skipped"], stats["failed"])
        return stats

    def _enhance_single(self, db: Session, question: Question) -> bool:
        """增强单道题目的解析。返回是否成功。"""
        # 幂等检查：已有 LLM 增强的跳过
        if question.explanation and _LLM_ENHANCED_MARKER in question.explanation:
            return False

        # 获取知识点
        kp = db.query(KnowledgePoint).filter(
            KnowledgePoint.id == question.knowledge_point_id
        ).first()
        kp_name = kp.name if kp else "未知"
        kp_desc = kp.description if kp else ""

        # 构造选项
        opts_text = "\n".join(
            f"  {o.label}. {o.content}" for o in question.options
        )

        # 找到正确答案
        correct_opt = next((o for o in question.options if o.is_correct), None)
        correct_text = correct_opt.content if correct_opt else question.answer

        prompt = f"""请为以下CPA考试题目生成深度解析。

【题目】{question.content}
【正确答案】{correct_text}
【知识点】{kp_name}

请返回纯JSON（不要markdown，不要其他文字）：
{{
  "explanation": "深度解析150字，包括考点定位、解题思路、易错点",
  "simple_explanation": "一句话通俗解释20字",
  "mnemonic": "记忆口诀20字",
  "study_tip": "学习建议30字"
}}

只返回纯JSON。"""

        messages = [
            {"role": "system", "content": "你是JSON API。只输出纯JSON，不要markdown，不要其他文字。"},
            {"role": "user", "content": prompt},
        ]

        result = llm_client.chat_json(messages, temperature=0.3)

        if not result:
            return False

        # 更新题目
        new_expl = result.get("explanation", "")
        if new_expl:
            question.explanation = f"{_LLM_ENHANCED_MARKER}\n{new_expl}"
        if result.get("simple_explanation"):
            question.simple_explanation = result["simple_explanation"]
        if result.get("mnemonic"):
            question.mnemonic = result["mnemonic"]
        if result.get("study_tip"):
            question.study_tip = result["study_tip"]

        return True

    def enhance_question(self, db: Session, question_id: int) -> dict | None:
        """增强单道题目（按需调用，用于前端"查看深度解析"功能）。"""
        question = db.query(Question).filter(Question.id == question_id).first()
        if not question:
            return None

        # 如果已有 LLM 增强，直接返回
        if question.explanation and _LLM_ENHANCED_MARKER in question.explanation:
            return self._format_question(question)

        if not llm_client.available:
            return self._format_question(question)

        success = self._enhance_single(db, question)
        if success:
            db.commit()
        return self._format_question(question)

    @staticmethod
    def _format_question(q: Question) -> dict:
        return {
            "question_id": q.id,
            "explanation": q.explanation or "",
            "simple_explanation": q.simple_explanation or "",
            "mnemonic": q.mnemonic or "",
            "study_tip": q.study_tip or "",
            "llm_enhanced": _LLM_ENHANCED_MARKER in (q.explanation or ""),
        }


# 全局单例
explanation_engine = ExplanationEngine()
