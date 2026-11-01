from datetime import datetime
import math
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ..db import get_db
from ..models import Assignment, Submission, User, Mistake, LearningEvent, now
from ..security import get_user, require_course
from ..services.grading import grade_submission, validate_scores
from ..jobs import dispatch_job

router = APIRouter(prefix="/api", tags=["作业批改"])


class RubricItem(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    max_score: int = Field(ge=1, le=100)


class AssignmentInput(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=10000)
    topic: str = Field(default="SQL 综合", min_length=1, max_length=100)
    max_score: int = Field(default=100, ge=1, le=100)
    rubric: list[RubricItem] = Field(min_length=1, max_length=10)
    status: str = Field(default="draft", pattern="^(draft|published)$")
    deadline: datetime | None = None
    starter_code: str = Field(default="SELECT * FROM students;", max_length=20000)

    @model_validator(mode="after")
    def total(self):
        if sum(r.max_score for r in self.rubric) != self.max_score:
            raise ValueError("评分维度总和必须等于满分")
        if self.deadline and self.deadline.tzinfo:
            from zoneinfo import ZoneInfo
            self.deadline = self.deadline.astimezone(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)
        return self


class SubmissionInput(BaseModel):
    code: str = Field(min_length=1, max_length=30000)
    request_id: str = Field(min_length=1, max_length=100)


class ReviewInput(BaseModel):
    scores: list[float] = Field(min_length=1, max_length=10)
    feedback: str = Field(min_length=1, max_length=6000)
    error_type: str | None = Field(default=None, max_length=100)


def assignment_dict(a, db, user):
    query = db.query(Submission).filter_by(assignment_id=a.id)
    if user.role == "student":
        query = query.filter_by(student_id=user.id)
    latest = query.order_by(Submission.id.desc()).first()
    return {"id": a.id, "course_id": a.course_id, "title": a.title, "description": a.description, "topic": a.topic,
            "rubric": a.rubric, "max_score": a.max_score, "status": a.status, "deadline": a.deadline,
            "starter_code": a.starter_code, "submission_count": query.count(),
            "latest_submission": submission_dict(latest, db) if latest else None}


def submission_dict(s, db):
    a = db.get(Assignment, s.assignment_id)
    u = db.get(User, s.student_id)
    return {"id": s.id, "assignment_id": s.assignment_id, "assignment_title": a.title, "student_id": s.student_id, "student_name": u.name,
            "code": s.code, "status": s.status, "error": s.error, "grade": s.grade, "attempts": s.attempts,
            "is_seed": s.is_seed, "created_at": s.created_at, "review_history": s.review_history}


def accessible_assignment(aid, db, user, teacher=False):
    a = db.get(Assignment, aid)
    if not a:
        raise HTTPException(404, "作业不存在")
    require_course(db, user, a.course_id, teacher=teacher)
    if user.role == "student" and a.status != "published":
        raise HTTPException(409, "作业尚未发布")
    return a


def accessible_submission(sid, db, user, teacher=False):
    s = db.get(Submission, sid)
    if not s:
        raise HTTPException(404, "提交记录不存在")
    accessible_assignment(s.assignment_id, db, user, teacher=teacher)
    if user.role == "student" and s.student_id != user.id:
        raise HTTPException(403, "只能查看自己的提交")
    return s


@router.get("/courses/{course_id}/assignments")
def assignments(course_id: int, db: Session = Depends(get_db), user=Depends(get_user)):
    require_course(db, user, course_id)
    query = db.query(Assignment).filter_by(course_id=course_id)
    if user.role == "student":
        query = query.filter_by(status="published")
    return [assignment_dict(a, db, user) for a in query.order_by(Assignment.id)]


@router.post("/courses/{course_id}/assignments")
def create(course_id: int, body: AssignmentInput, db: Session = Depends(get_db), user=Depends(get_user)):
    require_course(db, user, course_id, teacher=True)
    a = Assignment(course_id=course_id, **body.model_dump())
    db.add(a)
    db.commit()
    return assignment_dict(a, db, user)


@router.put("/assignments/{assignment_id}")
def update(assignment_id: int, body: AssignmentInput, db: Session = Depends(get_db), user=Depends(get_user)):
    a = accessible_assignment(assignment_id, db, user, teacher=True)
    if db.query(Submission).filter_by(assignment_id=a.id).count():
        # Changing the rubric beneath a saved grade would corrupt its meaning.
        if a.rubric != [r.model_dump() for r in body.rubric] or a.max_score != body.max_score:
            raise HTTPException(409, "已有提交的作业不可修改评分标准，请创建新作业")
        if body.status != "published":
            raise HTTPException(409, "已有提交的作业不可退回草稿")
    if a.description != body.description or a.topic != body.topic or a.starter_code != body.starter_code:
        # A fixed demonstration rule is valid only for its original exercise.
        a.grading_rule = "manual"
    for key, value in body.model_dump().items():
        setattr(a, key, value)
    db.commit()
    return assignment_dict(a, db, user)


@router.post("/assignments/{assignment_id}/submissions")
def submit(assignment_id: int, body: SubmissionInput, request: Request, db: Session = Depends(get_db), user=Depends(get_user)):
    a = accessible_assignment(assignment_id, db, user)
    if user.role != "student":
        raise HTTPException(403, "请使用学生账号提交作业")
    existing = db.query(Submission).filter_by(assignment_id=a.id, student_id=user.id, request_id=body.request_id).first()
    if existing:
        if existing.code != body.code:
            raise HTTPException(409, "请求编号已用于不同内容，请创建新提交")
        return submission_dict(existing, db)
    if a.deadline and now() > a.deadline:
        raise HTTPException(409, "作业已截止，请联系教师")
    if not body.code.strip():
        raise HTTPException(422, "提交内容不能为空")
    s = Submission(assignment_id=a.id, student_id=user.id, request_id=body.request_id, code=body.code)
    db.add(s)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(Submission).filter_by(assignment_id=a.id, student_id=user.id, request_id=body.request_id).one()
        return submission_dict(existing, db)
    dispatch_job(request, "grade", s.id)
    db.refresh(s)
    return submission_dict(s, db)


@router.get("/courses/{course_id}/submissions")
def submissions(course_id: int, db: Session = Depends(get_db), user=Depends(get_user)):
    require_course(db, user, course_id)
    query = db.query(Submission).join(Assignment).filter(Assignment.course_id == course_id)
    if user.role == "student":
        query = query.filter(Submission.student_id == user.id)
    return [submission_dict(s, db) for s in query.order_by(Submission.id.desc()).limit(200)]


@router.get("/submissions/{submission_id}")
def detail(submission_id: int, db: Session = Depends(get_db), user=Depends(get_user)):
    return submission_dict(accessible_submission(submission_id, db, user), db)


@router.post("/submissions/{submission_id}/retry")
def retry(submission_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_user)):
    s = accessible_submission(submission_id, db, user)
    if s.status != "failed":
        raise HTTPException(409, "仅失败的批改可以重试")
    claimed = db.query(Submission).filter_by(id=s.id, status="failed").update({"status": "pending", "error": ""}, synchronize_session=False)
    db.commit()
    if not claimed:
        raise HTTPException(409, "此批改已由其他请求重试")
    dispatch_job(request, "grade", s.id)
    db.refresh(s)
    return submission_dict(s, db)


@router.post("/submissions/{submission_id}/review")
def review(submission_id: int, body: ReviewInput, db: Session = Depends(get_db), user=Depends(get_user)):
    s = accessible_submission(submission_id, db, user, teacher=True)
    a = db.get(Assignment, s.assignment_id)
    if s.status in {"pending", "grading"}:
        raise HTTPException(409, "批改正在处理中，请稍后复核")
    try:
        scores = validate_scores(body.scores, a.rubric)
    except ValueError as error:
        raise HTTPException(422, str(error))
    # Serialize review against retry/worker claims, even when this session loaded a stale row.
    claimed = db.query(Submission).filter(Submission.id == s.id, Submission.status.in_(["graded", "needs_review", "failed"])).update(
        {"status": "reviewing"}, synchronize_session=False)
    if not claimed:
        db.rollback()
        raise HTTPException(409, "批改状态已变化，请刷新后复核")
    db.refresh(s)
    old = s.grade or {}
    error_type = body.error_type if body.error_type is not None else old.get("error_type", "")
    if sum(scores) == a.max_score:
        error_type = ""
    s.review_history = [*(s.review_history or []), {"reviewer": user.name, "at": now().isoformat(), "previous_grade": old, "feedback": body.feedback}]
    s.grade = {**old, "score": sum(scores), "dimensions": [{**r, "score": score} for r, score in zip(a.rubric, scores)],
               "feedback": body.feedback, "error_type": error_type, "reviewed": True, "reviewer": user.name, "mode": old.get("mode", "manual"), "hints": old.get("hints", []), "supported": True}
    s.status, s.error = "graded", ""
    mistake = db.query(Mistake).filter_by(submission_id=s.id).first()
    if not error_type and mistake:
        db.delete(mistake)
    elif error_type:
        if mistake:
            mistake.topic, mistake.detail = error_type, body.feedback
        else:
            db.add(Mistake(submission_id=s.id, course_id=a.course_id, student_id=s.student_id, topic=error_type, detail=body.feedback))
    db.add(LearningEvent(course_id=a.course_id, user_id=user.id, kind="review", text=f"复核了{db.get(User, s.student_id).name}的作业"))
    db.commit()
    return submission_dict(s, db)
