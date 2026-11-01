from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Execution
from ..security import get_user, require_course
from ..services.execution import available_languages, course_language, refresh_execution, submit_execution
from .practice import get_owned

router = APIRouter(prefix="/api", tags=["沙箱代码执行"])


class ExecuteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Literal["python", "java", "sql"]
    code: str = Field(min_length=1, max_length=20000)
    stdin: str = Field(default="", max_length=10000)


def execution_dict(item):
    return {"id": item.id, "course_id": item.course_id, "user_id": item.user_id, "language": item.language,
            "code": item.code, "stdin": item.stdin, "status": item.status, "error": item.error,
            "result": item.result, "created_at": item.created_at, "provider": "judge0"}


@router.post("/courses/{course_id}/execute")
def execute(course_id: int, body: ExecuteInput, request: Request, db: Session = Depends(get_db), user=Depends(get_user)):
    item = submit_execution(db, user, course_id, body.language, body.code, body.stdin, request.app.state.settings)
    return execution_dict(item)


@router.get("/courses/{course_id}/execution-languages")
def execution_languages(course_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_user)):
    course = require_course(db, user, course_id, teacher=user.role != "student")
    settings = request.app.state.settings
    if not getattr(settings, "judge0_url", ""):
        return {"available": False, "languages": [], "error": "未配置 Judge0，代码执行暂不可用"}
    try:
        languages = [entry for entry in available_languages(settings) if entry["language"] == course_language(course)]
    except Exception:
        raise HTTPException(503, "Judge0 语言列表暂不可用")
    return {"available": bool(languages), "languages": languages,
            "error": "" if languages else "Judge0 实例不支持当前课程语言"}


@router.get("/executions/{item_id}")
def get_execution(item_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_user)):
    item = get_owned(db, user, Execution, item_id, "执行记录")
    return execution_dict(refresh_execution(db, item, request.app.state.settings))
