from datetime import datetime, timezone, timedelta
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User
from ..security import verify_password, get_user, public_user

router = APIRouter(prefix="/api/auth", tags=["登录"])


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


@router.post("/login")
def login(body: LoginInput, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=body.username.strip()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "账号或密码不正确")
    token = jwt.encode({"sub": str(user.id), "exp": datetime.now(timezone.utc) + timedelta(hours=8)}, request.app.state.settings.jwt_secret, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer", "user": public_user(user)}


@router.get("/me")
def me(user=Depends(get_user)):
    return public_user(user)
