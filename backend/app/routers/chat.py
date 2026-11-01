from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Conversation, Message, AgentConfig, LearningEvent
from ..security import get_user, require_course
from ..services.retrieval import retrieve
from ..services.generation import answer_question, GenerationError
from ..services.workflow import run_course_workflow

router = APIRouter(prefix="/api", tags=["课程问答"])


class ChatInput(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: int | None = None
    hint_level: int = Field(default=1, ge=1, le=3)
    web_search: bool | None = None


def message_dict(m):
    payload = m.citations if isinstance(m.citations, dict) else {"sources": m.citations or []}
    citations = payload.get("sources", [])
    return {"id": m.id, "role": m.role, "content": m.content, "citations": citations,
            "grounded": m.grounded, "mode": m.mode, "hint_level": m.hint_level, "created_at": m.created_at,
            "answer_basis": payload.get("answer_basis", "course" if citations else "model" if m.mode == "deepseek" else "demo"),
            "web_search": payload.get("web_search", {"status": "not_recorded", "detail": "历史回答未记录联网状态"}),
            "retrieval_status": payload.get("retrieval_status", "not_recorded")}


def own_conversation(db, user, conversation_id):
    c = db.get(Conversation, conversation_id)
    if not c:
        raise HTTPException(404, "对话不存在")
    if c.user_id != user.id:
        raise HTTPException(403, "只能访问自己的对话")
    require_course(db, user, c.course_id)
    return c


@router.get("/courses/{course_id}/conversations")
def conversations(course_id: int, db: Session = Depends(get_db), user=Depends(get_user)):
    require_course(db, user, course_id)
    return [{"id": c.id, "title": c.title, "created_at": c.created_at} for c in db.query(Conversation).filter_by(course_id=course_id, user_id=user.id).order_by(Conversation.id.desc())]


@router.get("/conversations/{conversation_id}")
def history(conversation_id: int, db: Session = Depends(get_db), user=Depends(get_user)):
    c = own_conversation(db, user, conversation_id)
    return {"id": c.id, "title": c.title, "messages": [message_dict(m) for m in db.query(Message).filter_by(conversation_id=c.id).order_by(Message.id)]}


@router.post("/courses/{course_id}/chat")
def chat(course_id: int, body: ChatInput, request: Request, db: Session = Depends(get_db), user=Depends(get_user)):
    require_course(db, user, course_id)
    question = body.question.strip()
    if not question:
        raise HTTPException(422, "请输入问题")
    if body.conversation_id:
        c = own_conversation(db, user, body.conversation_id)
        if c.course_id != course_id:
            raise HTTPException(400, "对话与课程不匹配")
    else:
        c = Conversation(course_id=course_id, user_id=user.id, title=question[:40])
        db.add(c)
        db.flush()
    config = db.get(AgentConfig, course_id)
    previous = [{"role": m.role, "content": m.content} for m in reversed(db.query(Message).filter_by(conversation_id=c.id).order_by(Message.id.desc()).limit(6).all())]
    try:
        result = run_course_workflow(db, request.app.state.settings, course_id, question, config, body.hint_level, previous, enable_web=body.web_search)
        content, citations = result["content"], result["citations"]
    except GenerationError as error:
        db.rollback()
        raise HTTPException(502, str(error))
    db.add(Message(conversation_id=c.id, role="user", content=question))
    evidence = {"version": 2, "sources": citations, "answer_basis": result.get("answer_basis", "course" if citations else "model"),
                "web_search": result.get("web_search", {"status": "disabled"}), "retrieval_status": result.get("retrieval_status", "ready")}
    answer = Message(conversation_id=c.id, role="assistant", content=content, citations=evidence, grounded=bool(citations),
                     mode=request.app.state.settings.mode, hint_level=min(body.hint_level, config.max_hint_level))
    db.add(answer)
    db.add(LearningEvent(course_id=course_id, user_id=user.id, kind="question", text=f"提问：{question[:200]}"))
    db.commit()
    return {"conversation_id": c.id, "answer": message_dict(answer)}
