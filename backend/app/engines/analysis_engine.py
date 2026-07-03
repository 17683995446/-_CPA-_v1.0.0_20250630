"""
错题归因分析引擎 — LLM 诊断学生答错原因。

错误类型分类：
    - concept_confusion   概念混淆：对知识点理解有误
    - calculation_error   计算失误：公式正确但计算出错
    - misreading          审题不清：未看清题干条件
    - memory_decay        记忆遗忘：之前会但忘了
    - method_wrong        方法选择错误：用了错误的解题方法

无 LLM 时降级为规则判断（基于答案距离、题型等启发式）。
"""
import logging
from sqlalchemy.orm import Session

from app.engines.llm_client import llm_client
from app.models import ErrorAnalysis, Question, QuestionOption
from app.models.knowledge import KnowledgePoint

logger = logging.getLogger("app.engines.analysis")


# 降级模式的错误类型映射
_FALLBACK_MAP = {
    "single_choice": "concept_confusion",
    "judgment": "concept_confusion",
    "multiple_choice": "concept_confusion",
    "tbs": "method_wrong",
    "journal_entry": "method_wrong",
}


class ErrorAnalysisEngine:
    """错题归因分析引擎。"""

    def analyze(
        self,
        db: Session,
        user_id: int,
        question_id: int,
        user_answer: str,
    ) -> ErrorAnalysis:
        """分析学生答错原因，返回 ErrorAnalysis 记录。

        Args:
            db: 数据库会话
            user_id: 学生 ID
            question_id: 题目 ID
            user_answer: 学生的错误答案

        Returns:
            ErrorAnalysis 记录（已写入数据库）
        """
        question = db.query(Question).filter(Question.id == question_id).first()
        if not question:
            raise ValueError(f"题目 {question_id} 不存在")

        # 获取正确答案内容
        correct_opt = next(
            (o for o in question.options if o.is_correct), None
        )
        correct_content = correct_opt.content if correct_opt else question.answer

        # 获取知识点信息
        kp = db.query(KnowledgePoint).filter(
            KnowledgePoint.id == question.knowledge_point_id
        ).first()
        kp_name = kp.name if kp else "未知"

        # 尝试 LLM 分析
        if llm_client.available:
            analysis = self._analyze_with_llm(
                question, correct_content, user_answer, kp_name
            )
        else:
            analysis = self._analyze_fallback(question, correct_content, user_answer)

        # 写入数据库
        record = ErrorAnalysis(
            user_id=user_id,
            question_id=question_id,
            user_answer=user_answer[:500],
            error_type=analysis["error_type"],
            suggestion=analysis["suggestion"],
            related_concept=analysis.get("related_concept", kp_name),
        )
        db.add(record)
        db.commit()

        logger.info("错题归因: user=%d, q=%d, type=%s",
                    user_id, question_id, analysis["error_type"])
        return record

    def _analyze_with_llm(
        self,
        question: Question,
        correct_content: str,
        user_answer: str,
        kp_name: str,
    ) -> dict:
        """使用 LLM 分析错误原因。"""
        # 构造选项列表
        opts_text = "\n".join(
            f"  {o.label}. {o.content}" for o in question.options
        )

        prompt = f"""分析学生答错原因。

【题目】{question.content}
【正确答案】{correct_content}
【学生选择】{user_answer}
【知识点】{kp_name}

返回纯JSON（不要markdown）：
{{
  "error_type": "concept_confusion或calculation_error或misreading或memory_decay或method_wrong",
  "suggestion": "学习建议50字",
  "related_concept": "关联知识点"
}}

error_type: concept_confusion=概念混淆, calculation_error=计算失误, misreading=审题不清, memory_decay=记忆遗忘, method_wrong=方法错误
只返回纯JSON。"""

        messages = [
            {"role": "system", "content": "你是JSON API。只输出纯JSON，不要markdown，不要其他文字。"},
            {"role": "user", "content": prompt},
        ]

        result = llm_client.chat_json(messages, temperature=0.2)

        if result and "error_type" in result:
            return {
                "error_type": result["error_type"],
                "suggestion": result.get("suggestion", "建议复习相关知识点。"),
                "related_concept": result.get("related_concept", kp_name),
            }

        # LLM 返回异常，降级
        logger.warning("LLM 归因返回异常，降级为规则分析")
        return self._analyze_fallback(question, correct_content, user_answer)

    def _analyze_fallback(
        self,
        question: Question,
        correct_content: str,
        user_answer: str,
    ) -> dict:
        """降级方案：基于规则的启发式分析。"""
        qtype = question.question_type or "single_choice"
        error_type = _FALLBACK_MAP.get(qtype, "concept_confusion")

        # 如果是数值型答案，可能是计算错误
        try:
            correct_num = float(correct_content.replace("万元", "").replace("元", "").strip())
            user_num = float(user_answer.replace("万元", "").replace("元", "").strip())
            diff = abs(correct_num - user_num)
            if diff > 0 and diff / max(abs(correct_num), 1) < 0.1:
                # 差距很小，可能是计算精度问题
                error_type = "calculation_error"
                suggestion = "你的解题思路基本正确，但在计算过程中出现了小失误。建议重新验算每一步，注意小数位数和四舍五入规则。"
            elif diff > 0:
                error_type = "calculation_error"
                suggestion = "计算结果与正确答案差距较大，建议检查公式是否正确代入数据，逐步验算。"
            else:
                error_type = "concept_confusion"
                suggestion = "建议重新学习该知识点的核心概念，理解其原理。"
        except (ValueError, AttributeError):
            # 非数值型答案
            if qtype == "judgment":
                suggestion = "判断题答错说明对该知识点的理解不够准确，建议重新阅读教材相关章节，注意细节。"
            else:
                suggestion = "建议重新学习该知识点，重点关注概念辨析和适用条件。"

        return {
            "error_type": error_type,
            "suggestion": suggestion,
            "related_concept": "",
        }

    def get_user_analyses(
        self, db: Session, user_id: int, limit: int = 20
    ) -> list[dict]:
        """获取学生的错题归因历史。"""
        records = db.query(ErrorAnalysis).filter(
            ErrorAnalysis.user_id == user_id
        ).order_by(ErrorAnalysis.created_at.desc()).limit(limit).all()

        return [
            {
                "id": r.id,
                "question_id": r.question_id,
                "user_answer": r.user_answer,
                "error_type": r.error_type,
                "suggestion": r.suggestion,
                "related_concept": r.related_concept,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]

    def get_error_type_stats(self, db: Session, user_id: int) -> dict:
        """获取学生错误类型分布统计。"""
        from collections import Counter
        from sqlalchemy import func

        results = db.query(
            ErrorAnalysis.error_type,
            func.count(ErrorAnalysis.id)
        ).filter(
            ErrorAnalysis.user_id == user_id
        ).group_by(ErrorAnalysis.error_type).all()

        type_labels = {
            "concept_confusion": "概念混淆",
            "calculation_error": "计算失误",
            "misreading": "审题不清",
            "memory_decay": "记忆遗忘",
            "method_wrong": "方法错误",
        }

        return {
            type_labels.get(t, t): c for t, c in results
        }


# 全局单例
error_analysis_engine = ErrorAnalysisEngine()
