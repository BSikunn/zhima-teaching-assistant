from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Mistake, StudyPlan, PlanItem, AgentConfig, Submission, Assignment, LearningEvent
from ..security import get_user, require_course
from ..services.analytics import dashboard_data

router = APIRouter(prefix="/api", tags=["学情与复习"])


def student_only(user):
    if user.role != "student":
        raise HTTPException(403, "此操作仅学生可用")


@router.get("/courses/{course_id}/overview")
def overview(course_id: int, db: Session = Depends(get_db), user=Depends(get_user)):
    require_course(db, user, course_id)
    return dashboard_data(db, course_id, user)


@router.get("/courses/{course_id}/dashboard")
def dashboard(course_id: int, db: Session = Depends(get_db), user=Depends(get_user)):
    require_course(db, user, course_id, teacher=True)
    return dashboard_data(db, course_id, user)


@router.get("/courses/{course_id}/mistakes")
def mistakes(course_id: int, db: Session = Depends(get_db), user=Depends(get_user)):
    require_course(db, user, course_id)
    student_only(user)
    result = []
    for m in db.query(Mistake).filter_by(course_id=course_id, student_id=user.id).order_by(Mistake.id.desc()):
        s = db.get(Submission, m.submission_id)
        result.append({"id": m.id, "submission_id": m.submission_id, "topic": m.topic, "detail": m.detail,
                       "status": m.status, "code": s.code, "grade": s.grade, "is_seed": s.is_seed,
                       "assignment_title": db.get(Assignment, s.assignment_id).title, "created_at": m.created_at})
    return result


class MistakeUpdate(BaseModel):
    status: str = Field(pattern="^(pending|mastered)$")


@router.patch("/mistakes/{mistake_id}")
def update_mistake(mistake_id: int, body: MistakeUpdate, db: Session = Depends(get_db), user=Depends(get_user)):
    m = db.get(Mistake, mistake_id)
    if not m:
        raise HTTPException(404, "错题不存在")
    if m.student_id != user.id:
        raise HTTPException(403, "只能更新自己的错题")
    require_course(db, user, m.course_id)
    m.status = body.status
    db.commit()
    return {"ok": True}


def plan_dict(plan, db):
    return {"id": plan.id, "title": plan.title, "basis": plan.basis, "created_at": plan.created_at,
            "items": [{"id": i.id, "title": i.title, "description": i.description, "duration": i.duration, "done": i.done} for i in db.query(PlanItem).filter_by(plan_id=plan.id).order_by(PlanItem.id)]}


@router.get("/courses/{course_id}/plans")
def plans(course_id: int, db: Session = Depends(get_db), user=Depends(get_user)):
    require_course(db, user, course_id)
    student_only(user)
    return [plan_dict(p, db) for p in db.query(StudyPlan).filter_by(course_id=course_id, student_id=user.id).order_by(StudyPlan.id.desc())]


@router.post("/courses/{course_id}/plans")
def generate_plan(course_id: int, db: Session = Depends(get_db), user=Depends(get_user)):
    course = require_course(db, user, course_id)
    student_only(user)
    mistakes = db.query(Mistake).join(Submission).filter(Mistake.course_id == course_id, Mistake.student_id == user.id,
                                                       Mistake.status == "pending", Submission.is_seed.is_(False)).all()
    topics = list(dict.fromkeys(m.topic for m in mistakes))[:5]
    events = db.query(LearningEvent).filter_by(course_id=course_id, user_id=user.id, is_seed=False).count()
    fallback = list(dict.fromkeys(a.topic for a in db.query(Assignment).filter_by(course_id=course_id, status="published")))[:3]
    plan = StudyPlan(course_id=course_id, student_id=user.id, title=f"我的{course.title}复习计划",
                     basis=f"依据当前 {len(mistakes)} 条真实待复习错题与 {events} 条学习事件，结合本课程作业知识点生成；任务完成状态由本人自报。")
    db.add(plan)
    db.flush()
    for topic in topics or fallback or [f"{course.title}基础"]:
        db.add(PlanItem(plan_id=plan.id, title=f"回顾「{topic}」并完成相似练习", description=f"打开课程资料回顾{topic}，整理自己的错误原因，再独立写出一个正确例子和一个反例。", duration=20))
    db.add(PlanItem(plan_id=plan.id, title="用自己的话解释，再做一次检查", description="不查看答案，重新解释关键规则；仍有疑问时带上尝试过程向助教提问。", duration=10))
    db.add(LearningEvent(course_id=course_id, user_id=user.id, kind="plan", text="生成了个性化复习计划"))
    db.commit()
    return plan_dict(plan, db)


class ItemUpdate(BaseModel):
    done: bool


@router.patch("/plan-items/{item_id}")
def update_item(item_id: int, body: ItemUpdate, db: Session = Depends(get_db), user=Depends(get_user)):
    item = db.get(PlanItem, item_id)
    if not item:
        raise HTTPException(404, "复习任务不存在")
    plan = db.get(StudyPlan, item.plan_id)
    if plan.student_id != user.id:
        raise HTTPException(403, "只能更新自己的学习计划")
    require_course(db, user, plan.course_id)
    item.done = body.done
    db.commit()
    return {"ok": True, "done": item.done}


class ConfigInput(BaseModel):
    persona: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=6000)
    hint_first: bool = True
    max_hint_level: int = Field(default=3, ge=1, le=3)


@router.get("/courses/{course_id}/config")
def config(course_id: int, db: Session = Depends(get_db), user=Depends(get_user)):
    require_course(db, user, course_id, teacher=True)
    c = db.get(AgentConfig, course_id)
    return {"persona": c.persona, "prompt": c.prompt, "hint_first": c.hint_first, "max_hint_level": c.max_hint_level}


@router.put("/courses/{course_id}/config")
def update_config(course_id: int, body: ConfigInput, db: Session = Depends(get_db), user=Depends(get_user)):
    require_course(db, user, course_id, teacher=True)
    c = db.get(AgentConfig, course_id)
    for key, value in body.model_dump().items():
        setattr(c, key, value)
    db.commit()
    return body.model_dump()
