import json
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..models import (Assignment, Conversation, Course, Enrollment, LearningEvent, Message,
                      Mistake, PracticeSession, Submission, now)
from .generation import deepseek_json
from .practice import claim, fail, finish


class Narrative(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    content: str = Field(min_length=1, max_length=24000)
    # Some JSON-mode providers echo the requested response format inside the object.
    type: Literal["json_object"] = "json_object"


def collect_statistics(db, item):
    """SQL scopes all rows; Pandas groups only actual, non-seed submissions."""
    import pandas as pd
    personal = item.scope == "personal"
    submissions = db.query(Submission, Assignment).join(Assignment).filter(Assignment.course_id == item.course_id)
    if personal:
        submissions = submissions.filter(Submission.student_id == item.user_id)
    rows = submissions.all()
    actual = [(s, a) for s, a in rows if not s.is_seed]
    conversations = db.query(Conversation).filter_by(course_id=item.course_id)
    mistakes = db.query(Mistake).filter_by(course_id=item.course_id, status="pending")
    practice = db.query(PracticeSession).filter_by(course_id=item.course_id)
    events = db.query(LearningEvent).filter_by(course_id=item.course_id, is_seed=False)
    if personal:
        conversations = conversations.filter_by(user_id=item.user_id)
        mistakes = mistakes.filter_by(student_id=item.user_id)
        practice = practice.filter_by(user_id=item.user_id)
        events = events.filter_by(user_id=item.user_id)
    # Seed mistakes are excluded through the real source submission, not labels in text.
    mistake_rows = mistakes.join(Submission, Submission.id == Mistake.submission_id).filter(Submission.is_seed == False).all()
    conversation_rows = conversations.all()
    practice_rows = practice.all()
    ids = [c.id for c in conversation_rows]
    question_count = db.query(Message).filter(Message.conversation_id.in_(ids), Message.role == "user").count() if ids else 0
    frame = pd.DataFrame([{"student_id": s.student_id, "status": s.status, "topic": a.topic,
                           "score": (s.grade or {}).get("score"), "created_at": s.created_at.isoformat()}
                          for s, a in actual])
    scores = pd.to_numeric(frame.loc[frame["status"] == "graded", "score"], errors="coerce").dropna() if not frame.empty else pd.Series(dtype=float)
    scores = scores[scores.map(lambda value: math.isfinite(value) and 0 <= value <= 100)]
    topics = dict(frame.groupby("topic").size().items()) if not frame.empty else {}
    dates = ([s.created_at for s, _ in actual] + [e.created_at for e in events]
             + [c.created_at for c in conversation_rows] + [p.created_at for p in practice_rows])
    return {"scope": item.scope, "course_id": item.course_id,
            "student_count": 1 if personal else db.query(Enrollment).filter_by(course_id=item.course_id).count(),
            "submissions": len(actual), "graded_submissions": sum(s.status == "graded" for s, _ in actual),
            "excluded_seed_submissions": sum(bool(s.is_seed) for s, _ in rows),
            "average_score": round(float(scores.mean()), 1) if len(scores) else None,
            "conversations": len(ids), "questions": question_count,
            "pending_mistakes": len(mistake_rows),
            "weak_topics": sorted({m.topic for m in mistake_rows}),
            "practice_sessions": len(practice_rows), "graded_practice_sessions": sum(p.status == "graded" for p in practice_rows),
            "submissions_by_topic": {str(k): int(v) for k, v in topics.items()},
            "range_start": min(dates).isoformat() if dates else None,
            "range_end": now().isoformat(), "basis": "数据库真实记录；演示种子提交和对应错题不计入掌握度统计"}


def process_report(db, item, settings):
    if not claim(db, item, "pending", "generating"):
        return
    attempt = item.attempts
    try:
        from .storage import store_bytes
        course = db.get(Course, item.course_id)
        stats = collect_statistics(db, item)
        title = f"{course.title} · {'个人学习' if item.scope == 'personal' else '课程教学'}报告"
        objective = (f"# {title}\n\n## 客观统计\n\n"
            f"统计区间：{stats['range_start'] or '暂无学习记录'} 至 {stats['range_end']}（北京时间）\n\n"
            f"统计范围：{'本人' if item.scope == 'personal' else '本课程'}；学生数 {stats['student_count']}。\n\n"
            f"作业提交 {stats['submissions']} 次，已批改 {stats['graded_submissions']} 次，"
            f"平均建议分 {stats['average_score'] if stats['average_score'] is not None else '暂无'}。\n\n"
            f"对话 {stats['conversations']} 个，学生提问 {stats['questions']} 条；"
            f"待复习错题 {stats['pending_mistakes']} 条。测验/面试 {stats['practice_sessions']} 次，"
            f"已评阅 {stats['graded_practice_sessions']} 次。\n\n"
            f"薄弱知识点：{'、'.join(stats['weak_topics']) or '暂无真实错题依据'}。\n\n"
            f"来源：本课程作业提交、对话消息、错题、测验会话和学习事件 SQL 记录；"
            f"按知识点使用 Pandas 聚合。已排除演示种子提交 {stats['excluded_seed_submissions']} 条。\n\n")
        if settings.mode == "deepseek":
            result = Narrative.model_validate(deepseek_json(settings,
                "你是教学分析助教。仅依据给定真实SQL统计提出中文教学/学习建议，不编造学生行为、分数、趋势或因果。"
                "数据不足时明确说明。不要重复或篡改客观统计。"
                '严格只返回JSON对象 {"content":"Markdown分析与可执行建议"}。content必须是非空字符串，'
                "不添加type、statistics等其他字段，不返回嵌套对象。",
                json.dumps({"course": course.title, "statistics": stats}, ensure_ascii=False)))
            narrative = "## AI分析与建议（需教师核对）\n\n" + result.content
        else:
            narrative = "## 规则演示建议\n\n此部分未调用AI。请结合课程资料复习实际错题；暂无记录时先完成一次作业或测验，再依据反馈制定计划。"
        content = objective + narrative + "\n"
        key = f"reports/{item.course_id}/{item.user_id}/{item.id}-{attempt}.md"
        store_bytes(settings, key, content.encode("utf-8"), "text/markdown; charset=utf-8")
        finish(db, item, "generating", attempt, {"title": title, "content": content, "statistics": stats,
               "storage_key": key, "ai_mode": settings.mode, "status": "ready", "error": ""})
    except Exception as error:
        fail(db, item, error, "generating", attempt)
