from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Course, Enrollment, User
from ..security import get_user, require_course

router = APIRouter(prefix="/api/courses", tags=["课程"])


def course_dict(course, db):
    teacher = db.get(User, course.teacher_id)
    return {"id": course.id, "title": course.title, "subtitle": course.subtitle,
            "code": course.code, "class_name": course.class_name, "teacher": teacher.name,
            "description": course.description,
            "student_count": db.query(Enrollment).filter_by(course_id=course.id).count()}


@router.get("")
def list_courses(db: Session = Depends(get_db), user=Depends(get_user)):
    courses = db.query(Course).order_by(Course.id).all()
    if user.role != "admin":
        ids = {e.course_id for e in db.query(Enrollment).filter_by(user_id=user.id)}
        courses = [c for c in courses if c.teacher_id == user.id or c.id in ids]
    return [course_dict(c, db) for c in courses]


@router.get("/{course_id}")
def get_course(course_id: int, db: Session = Depends(get_db), user=Depends(get_user)):
    return course_dict(require_course(db, user, course_id), db)
