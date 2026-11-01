"""Real LlamaIndex tools bound to the authenticated server-side user/session."""
from fastapi import HTTPException

from ..models import PracticeSession, Report
from ..security import require_course


def build_agent_tools(db, user, settings, enqueue):
    """enqueue(kind, id) is the authenticated application's job dispatcher."""
    from llama_index.core.tools import FunctionTool
    from ..routers.practice import PracticeInput
    from ..routers.execution import ExecuteInput
    from .execution import submit_execution

    def generate_practice(course_id: int, mode: str = "quiz", count: int = 3) -> dict:
        """Generate a practice quiz/interview for an enrolled student in a permitted course."""
        require_course(db, user, course_id)
        if user.role != "student":
            raise HTTPException(403, "此操作仅学生可用")
        body = PracticeInput(mode=mode, count=count)
        item = PracticeSession(course_id=course_id, user_id=user.id, mode=body.mode, count=body.count, ai_mode=settings.mode)
        db.add(item)
        db.commit()
        enqueue("practice_generate", item.id)
        db.refresh(item)
        return {"id": item.id, "status": item.status}

    def generate_report(course_id: int) -> dict:
        """Generate a personal or teaching report using the authenticated user's course permission."""
        require_course(db, user, course_id, teacher=user.role != "student")
        item = Report(course_id=course_id, user_id=user.id, scope="personal" if user.role == "student" else "course", ai_mode=settings.mode)
        db.add(item)
        db.commit()
        enqueue("report", item.id)
        db.refresh(item)
        return {"id": item.id, "status": item.status}

    def execute_code(course_id: int, language: str, code: str, stdin: str = "") -> dict:
        """Execute bounded Python, Java or SQL code only in the configured Judge0 sandbox."""
        body = ExecuteInput(language=language, code=code, stdin=stdin)
        item = submit_execution(db, user, course_id, body.language, body.code, body.stdin, settings)
        return {"id": item.id, "status": item.status, "error": item.error}

    return [FunctionTool.from_defaults(fn=generate_practice), FunctionTool.from_defaults(fn=generate_report),
            FunctionTool.from_defaults(fn=execute_code)]
