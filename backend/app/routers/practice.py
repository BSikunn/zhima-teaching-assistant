from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import PracticeSession
from ..security import get_user, require_course

router = APIRouter(prefix="/api", tags=["测验与面试"])


def get_owned(db, user, model, item_id, label):
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(404, f"{label}不存在")
    require_course(db, user, item.course_id, teacher=user.role != "student")
    if user.role == "student" and item.user_id != user.id:
        raise HTTPException(403, "只能访问自己的记录")
    return item


def practice_dict(item):
    answered = len(item.answers or [])
    completed = len((item.feedback or {}).get("items", []))
    visible = min(item.count, completed + 1) if item.mode == "interview" else item.count
    return {"id": item.id, "course_id": item.course_id, "user_id": item.user_id,
            "mode": item.mode, "ai_mode": item.ai_mode, "count": item.count,
            "status": item.status, "error": item.error, "created_at": item.created_at,
            # An allowlist prevents new private fields from leaking in the future.
            "questions": [{"prompt": q["prompt"], "topic": q["topic"]} for q in item.questions[:visible]],
            "answers": item.answers, "feedback": item.feedback if completed else None,
            "current_round": min(completed + 1, item.count), "answered_count": answered}


def dispatch(request, db, kind, item):
    from ..jobs import dispatch_job
    dispatch_job(request, kind, item.id)
    db.refresh(item)


class PracticeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["quiz", "interview"] = "quiz"
    count: int = Field(default=3, ge=1, le=5, strict=True)


@router.post("/courses/{course_id}/practice-sessions")
def create_practice(course_id: int, body: PracticeInput, request: Request, db: Session = Depends(get_db), user=Depends(get_user)):
    require_course(db, user, course_id)
    if user.role != "student":
        raise HTTPException(403, "此操作仅学生可用")
    item = PracticeSession(course_id=course_id, user_id=user.id, mode=body.mode, count=body.count,
                           ai_mode=request.app.state.settings.mode)
    db.add(item)
    db.commit()
    dispatch(request, db, "practice_generate", item)
    return practice_dict(item)


@router.get("/courses/{course_id}/practice-sessions")
def list_practice(course_id: int, db: Session = Depends(get_db), user=Depends(get_user)):
    require_course(db, user, course_id, teacher=user.role != "student")
    query = db.query(PracticeSession).filter_by(course_id=course_id)
    if user.role == "student":
        query = query.filter_by(user_id=user.id)
    return [practice_dict(p) for p in query.order_by(PracticeSession.id.desc()).limit(100)]


@router.get("/practice-sessions/{item_id}")
def get_practice(item_id: int, db: Session = Depends(get_db), user=Depends(get_user)):
    return practice_dict(get_owned(db, user, PracticeSession, item_id, "测验"))


class AnswersInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: list[str] = Field(min_length=1, max_length=5)
    request_id: str = Field(min_length=1, max_length=100)


@router.post("/practice-sessions/{item_id}/answers")
def answer_practice(item_id: int, body: AnswersInput, request: Request, db: Session = Depends(get_db), user=Depends(get_user)):
    item = get_owned(db, user, PracticeSession, item_id, "测验")
    if user.role != "student" or item.user_id != user.id:
        raise HTTPException(403, "只能提交自己的答案")
    if item.request_id is not None:
        if item.request_id == body.request_id and item.answers == body.answers:
            return practice_dict(item)
        if item.mode != "interview" or item.status != "ready" or item.request_id == body.request_id:
            raise HTTPException(409, "此轮已提交，不能重复或更改作答")
    completed = len((item.feedback or {}).get("items", []))
    expected_count = completed + 1 if item.mode == "interview" else item.count
    if len(body.answers) != expected_count or any(not a.strip() or len(a) > 20000 for a in body.answers):
        raise HTTPException(422, "测验须提交全部作答；面试须按轮累计提交，每题须为非空且不超过20000字")
    if item.mode == "interview" and body.answers[:completed] != item.answers[:completed]:
        raise HTTPException(409, "不能更改已评阅的面试作答")
    changed = db.query(PracticeSession).filter_by(id=item.id, status="ready", request_id=item.request_id).update(
        {"answers": body.answers, "request_id": body.request_id, "status": "pending_grade"}, synchronize_session=False)
    db.commit()
    db.refresh(item)
    if changed != 1:
        if item.request_id == body.request_id and item.answers == body.answers:
            return practice_dict(item)
        raise HTTPException(409, "测验尚未就绪或已提交")
    dispatch(request, db, "practice_grade", item)
    return practice_dict(item)


@router.post("/practice-sessions/{item_id}/retry")
def retry_practice(item_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_user)):
    item = get_owned(db, user, PracticeSession, item_id, "测验")
    if user.role != "student" or item.user_id != user.id:
        raise HTTPException(403, "只能重试自己的测验")
    grading = item.request_id is not None
    changed = db.query(PracticeSession).filter_by(id=item.id, status="failed").update(
        {"status": "pending_grade" if grading else "pending", "error": ""}, synchronize_session=False)
    db.commit()
    if changed != 1:
        raise HTTPException(409, "仅失败的任务可重试")
    dispatch(request, db, "practice_grade" if grading else "practice_generate", item)
    return practice_dict(item)
