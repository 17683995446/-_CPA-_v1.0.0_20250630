"""
学习诊断报告引擎 — 基于 BKT 掌握度 + 答题模式生成个性化诊断。

无 LLM 时降级为模板化报告（基于规则的数据汇总）。
"""
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.engines.llm_client import llm_client
from app.models import StudyReport, UserMastery, Question
from app.models.knowledge import KnowledgePoint

logger = logging.getLogger("app.engines.report")


class ReportEngine:
    """学习诊断报告引擎。"""

    def generate_report(
        self,
        db: Session,
        user_id: int,
        report_type: str = "weekly",
    ) -> StudyReport:
        """生成学习诊断报告。

        Args:
            db: 数据库会话
            user_id: 学生 ID
            report_type: weekly / monthly / on_demand

        Returns:
            StudyReport 记录（已写入数据库）
        """
        # 1. 收集数据
        snapshot = self._collect_snapshot(db, user_id)

        # 2. 生成报告内容
        if llm_client.available:
            content = self._generate_with_llm(snapshot)
        else:
            content = self._generate_fallback(snapshot)

        # 3. 提取摘要
        weak_kps = content.get("weak_points", [])
        summary = content.get("summary", f"本周共答题{snapshot['total_questions']}题，正确率{snapshot['accuracy_rate']:.0%}。")

        # 4. 写入数据库
        record = StudyReport(
            user_id=user_id,
            report_type=report_type,
            content_json=json.dumps(content, ensure_ascii=False),
            summary=summary[:500],
            total_questions=snapshot["total_questions"],
            accuracy_rate=snapshot["accuracy_rate"],
            weak_points_count=len(weak_kps),
        )
        db.add(record)
        db.commit()

        logger.info("学习报告生成: user=%d, type=%s, weak_points=%d",
                    user_id, report_type, len(weak_kps))
        return record

    def _collect_snapshot(self, db: Session, user_id: int) -> dict:
        """收集学生学习数据快照。"""
        # 掌握度数据
        masteries = db.query(UserMastery).filter(
            UserMastery.user_id == user_id
        ).all()

        # 关联知识点信息
        kp_ids = [m.knowledge_point_id for m in masteries]
        kps = db.query(KnowledgePoint).filter(
            KnowledgePoint.id.in_(kp_ids)
        ).all() if kp_ids else []
        kp_map = {kp.id: kp for kp in kps}

        # 计算各科目掌握度
        subject_stats = defaultdict(lambda: {"total": 0, "sum": 0.0, "weak": []})
        for m in masteries:
            kp = kp_map.get(m.knowledge_point_id)
            if not kp:
                continue
            subject_stats[kp.subject]["total"] += 1
            subject_stats[kp.subject]["sum"] += m.p_known
            if m.p_known < 0.7:
                subject_stats[kp.subject]["weak"].append({
                    "kp_code": kp.code,
                    "kp_name": kp.name,
                    "p_known": round(m.p_known, 2),
                    "total_answers": m.total_answers,
                })

        # 总体统计
        total_questions = sum(m.total_answers for m in masteries)
        total_correct = sum(m.correct_answers for m in masteries)
        accuracy = total_correct / total_questions if total_questions > 0 else 0.0

        # 薄弱知识点（掌握度 < 0.7，按掌握度升序）
        weak_points = []
        for subj, stats in subject_stats.items():
            weak_points.extend(stats["weak"])
        weak_points.sort(key=lambda x: x["p_known"])

        # 各科目平均掌握度
        subject_mastery = {}
        for subj, stats in subject_stats.items():
            if stats["total"] > 0:
                subject_mastery[subj] = round(stats["sum"] / stats["total"], 2)

        return {
            "user_id": user_id,
            "total_questions": total_questions,
            "total_correct": total_correct,
            "accuracy_rate": accuracy,
            "subject_mastery": subject_mastery,
            "weak_points": weak_points[:10],  # Top 10 薄弱点
            "weak_points_count": len(weak_points),
            "total_kps": len(masteries),
            "generated_at": datetime.now().isoformat(),
        }

    def _generate_with_llm(self, snapshot: dict) -> dict:
        """使用 LLM 生成诊断报告。"""
        weak_text = "\n".join(
            f"  - {w['kp_name']}（{w['kp_code']}）: 掌握度{w['p_known']:.0%}, 已答{w['total_answers']}题"
            for w in snapshot["weak_points"][:5]
        )
        mastery_text = ", ".join(
            f"{subj}: {val:.0%}" for subj, val in snapshot["subject_mastery"].items()
        )

        prompt = f"""你是CPA考试学习顾问。请根据以下学习数据生成诊断报告。

【学习数据】
总答题数: {snapshot['total_questions']}
正确率: {snapshot['accuracy_rate']:.1%}
各科目掌握度: {mastery_text}

薄弱知识点（掌握度<70%）:
{weak_text}

请返回JSON格式（不要markdown，不要其他文字，只输出纯JSON）：
{{
  "summary": "一句话概括学习状态",
  "overall_assessment": "总体评价100字",
  "weak_point_1": "薄弱点1名称和改进建议",
  "weak_point_2": "薄弱点2名称和改进建议",
  "weak_point_3": "薄弱点3名称和改进建议",
  "study_plan": "下周学习建议100字",
  "encouragement": "鼓励语20字"
}}

只返回纯JSON。"""

        messages = [
            {"role": "system", "content": "你是JSON API。只输出纯JSON，不要markdown，不要其他文字。"},
            {"role": "user", "content": prompt},
        ]

        result = llm_client.chat_json(messages, temperature=0.4)

        if result:
            # 将扁平结构转为带 weak_points 列表的结构
            weak_points = []
            for key in ["weak_point_1", "weak_point_2", "weak_point_3"]:
                val = result.get(key, "")
                if val:
                    weak_points.append({"description": val})
            result["weak_points"] = weak_points
            # 补充原始数据
            result["data_snapshot"] = {
                "total_questions": snapshot["total_questions"],
                "accuracy_rate": snapshot["accuracy_rate"],
                "subject_mastery": snapshot["subject_mastery"],
            }
            return result

        # LLM 失败，降级
        logger.warning("LLM 报告生成失败，降级为模板报告")
        return self._generate_fallback(snapshot)

    def _generate_fallback(self, snapshot: dict) -> dict:
        """降级方案：基于规则的模板化报告。"""
        weak_points = []
        for w in snapshot["weak_points"][:5]:
            weak_points.append({
                "kp_name": w["kp_name"],
                "kp_code": w["kp_code"],
                "reason": f"掌握度仅{w['p_known']:.0%}，低于及格线70%",
                "action": f"建议重新学习{w['kp_name']}，完成至少10道相关题目后重新评估",
            })

        # 总体评价
        accuracy = snapshot["accuracy_rate"]
        if accuracy >= 0.8:
            assessment = f"学习状态优秀，正确率达到{accuracy:.0%}。继续保持当前学习节奏，重点突破薄弱知识点即可。"
            encouragement = "坚持就是胜利，你做得很好！"
        elif accuracy >= 0.6:
            assessment = f"学习状态良好，正确率{accuracy:.0%}。部分知识点需要加强理解，建议针对薄弱点专项练习。"
            encouragement = "稳步前进，每一次练习都是进步！"
        else:
            assessment = f"学习状态需要提升，正确率{accuracy:.0%}。建议放慢节奏，先巩固基础知识再做难题。"
            encouragement = "不要气馁，扎实基础是成功的关键！"

        # 学习计划
        if weak_points:
            plan = "建议按以下顺序学习：\n"
            for i, wp in enumerate(weak_points[:3], 1):
                plan += f"{i}. 重点复习「{wp['kp_name']}」\n"
            plan += "每完成一个知识点后，做10道相关题目验证掌握度。"
        else:
            plan = "当前无明显薄弱点，建议继续综合练习，保持手感。"

        return {
            "summary": f"共答题{snapshot['total_questions']}题，正确率{accuracy:.0%}，薄弱知识点{len(weak_points)}个。",
            "overall_assessment": assessment,
            "weak_points": weak_points,
            "study_plan": plan,
            "encouragement": encouragement,
            "data_snapshot": {
                "total_questions": snapshot["total_questions"],
                "accuracy_rate": snapshot["accuracy_rate"],
                "subject_mastery": snapshot["subject_mastery"],
            },
        }

    def get_latest_report(self, db: Session, user_id: int) -> dict | None:
        """获取学生最近的诊断报告。"""
        record = db.query(StudyReport).filter(
            StudyReport.user_id == user_id
        ).order_by(StudyReport.created_at.desc()).first()

        if not record:
            return None

        return {
            "id": record.id,
            "report_type": record.report_type,
            "summary": record.summary,
            "content": json.loads(record.content_json),
            "total_questions": record.total_questions,
            "accuracy_rate": record.accuracy_rate,
            "weak_points_count": record.weak_points_count,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }

    def get_report_history(self, db: Session, user_id: int, limit: int = 10) -> list[dict]:
        """获取报告历史列表。"""
        records = db.query(StudyReport).filter(
            StudyReport.user_id == user_id
        ).order_by(StudyReport.created_at.desc()).limit(limit).all()

        return [
            {
                "id": r.id,
                "report_type": r.report_type,
                "summary": r.summary,
                "total_questions": r.total_questions,
                "accuracy_rate": r.accuracy_rate,
                "weak_points_count": r.weak_points_count,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]


# 全局单例
report_engine = ReportEngine()
