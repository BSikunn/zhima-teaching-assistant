import base64
import hashlib
import hmac
import os
from datetime import timedelta
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, Course, Enrollment, now

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return base64.b64encode(salt + digest).decode()


def verify_password(password: str, encoded: str) -> bool:
    raw = base64.b64decode(encoded)
    digest = hashlib.scrypt(password.encode(), salt=raw[:16], n=16384, r=8, p=1)
    return hmac.compare_digest(raw[16:], digest)


def get_user(request: Request, token: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    if not token:
        raise HTTPException(401, "请先登录")
    try:
        data = jwt.decode(token.credentials, request.app.state.settings.jwt_secret, algorithms=["HS256"])
        user = db.get(User, int(data["sub"]))
        if not user:
            raise ValueError()
        return user
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, "登录已过期，请重新登录")


def require_course(db: Session, user: User, course_id: int, teacher: bool = False):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    owner = course.teacher_id == user.id and user.role == "teacher"
    member = db.query(Enrollment).filter_by(course_id=course_id, user_id=user.id).first()
    if user.role != "admin" and not owner and (teacher or not member):
        raise HTTPException(403, "无权访问此课程或执行此操作")
    return course


def public_user(user):
    return {"id": user.id, "username": user.username, "name": user.name, "role": user.role}
