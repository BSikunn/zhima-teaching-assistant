from collections import Counter
from datetime import timedelta
import pandas as pd
from ..models import Assignment, Submission, Mistake, Enrollment, User, Material, Conversation, Message, LearningEvent, now


def dashboard_data(db, course_id, user):
    submissions = db.query(Submission).join(Assignment).filter(Assignment.course_id == course_id, Submission.is_seed.is_(False))
    mistakes = db.query(Mistake).join(Submission).filter(Mistake.course_id == course_id, Submission.is_seed.is_(False))
    events = db.query(LearningEvent).filter_by(course_id=course_id, is_seed=False)
    if user.role == "student":
        submissions = submissions.filter(Submission.student_id == user.id)
        mistakes = mistakes.filter(Mistake.student_id == user.id)
        events = events.filter(LearningEvent.user_id == user.id)
    submissions = submissions.order_by(Submission.created_at.desc()).all()
    errors = mistakes.all()
    scores = [s.grade["score"] for s in submissions if s.grade and s.grade.get("score") is not None]
    error_counts = Counter(m.topic for m in errors)
    all_assignments = db.query(Assignment).filter_by(course_id=course_id, status="published").all()
    submitted_ids = {s.assignment_id for s in submissions}
    pending = [a for a in all_assignments if a.id not in submitted_ids]
    date_labels = [(now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in reversed(range(7))]
    frame = pd.DataFrame([{"date": s.created_at.strftime("%Y-%m-%d"), "score": s.grade.get("score") if s.grade else None} for s in submissions])
    counts = frame.groupby("date").size().to_dict() if not frame.empty else {}
    trend = [{"date": day[5:], "count": int(counts.get(day, 0))} for day in date_labels]
    recent = []
    for s in submissions[:8]:
        grade = s.grade or {}
        recent.append({"id": s.id, "title": db.get(Assignment, s.assignment_id).title, "student": db.get(User, s.student_id).name,
                       "score": grade.get("score"), "reviewed": grade.get("reviewed", False), "status": s.status, "created_at": s.created_at, "is_seed": s.is_seed})
    student_ids = [u.id for u in db.query(User).join(Enrollment, Enrollment.user_id == User.id).filter(Enrollment.course_id == course_id, User.role == "student")]
    attention = []
    if user.role != "student":
        for uid in student_ids:
            own_scores = [s.grade["score"] for s in submissions if s.student_id == uid and s.grade and s.grade.get("score") is not None]
            own_pending = sum(1 for m in errors if m.student_id == uid and m.status == "pending")
            if own_pending:
                attention.append({"name": db.get(User, uid).name, "pending": own_pending, "average": round(sum(own_scores) / len(own_scores), 1) if own_scores else None})
        attention.sort(key=lambda r: r["pending"], reverse=True)
    topics = []
    for name in dict.fromkeys([a.topic for a in all_assignments] + list(error_counts)):
        topic_errors = [m for m in errors if m.topic == name]
        total = len(topic_errors)
        reviewed = sum(m.status == "mastered" for m in topic_errors)
        topics.append({"name": name, "pending": total - reviewed, "mastered": reviewed, "total": total,
                       "rate": round(reviewed / total * 100) if total else None})
    conversations = db.query(Conversation).filter_by(course_id=course_id)
    if user.role == "student":
        conversations = conversations.filter_by(user_id=user.id)
    question_count = db.query(Message).filter(Message.conversation_id.in_(conversations.with_entities(Conversation.id)), Message.role == "user").count()
    missing = [{"student_id": uid, "name": db.get(User, uid).name, "assignment_id": a.id, "title": a.title}
               for uid in ([user.id] if user.role == "student" else student_ids) for a in all_assignments
               if not any(s.student_id == uid and s.assignment_id == a.id for s in submissions)]
    return {"role": user.role, "student_count": len(student_ids), "submission_count": len(submissions),
            "seed_count": 0, "new_count": len(submissions),
            "average_score": round(sum(scores) / len(scores), 1) if scores else None,
            "pending_review": sum(s.status == "needs_review" or (s.grade is not None and not s.grade.get("reviewed", False)) for s in submissions),
            "conversation_count": conversations.count(), "question_count": question_count, "missing_submissions": missing,
            "mistake_count": sum(m.status == "pending" for m in errors),
            "material_count": db.query(Material).filter_by(course_id=course_id, status="ready").count(),
            "assignment_count": len(all_assignments), "pending_assignments": [{"id": a.id, "title": a.title, "topic": a.topic, "deadline": a.deadline} for a in pending],
            "error_distribution": [{"name": name, "value": count} for name, count in error_counts.most_common()],
            "trend": trend, "topics": topics, "attention": attention[:5], "recent_submissions": recent,
            "events": [{"id": e.id, "text": e.text, "kind": e.kind, "created_at": e.created_at, "is_seed": e.is_seed} for e in events.order_by(LearningEvent.id.desc()).limit(6)],
            "updated_at": now(), "score_note": "仅统计非样例提交；分数包含 AI 建议分与教师复核分。", "mastery_note": "复习状态来自手动标记，不代表测得的能力掌握度。"}
