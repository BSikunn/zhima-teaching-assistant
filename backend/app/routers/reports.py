from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Report
from ..security import get_user, require_course
from .practice import dispatch, get_owned

router = APIRouter(prefix="/api", tags=["学习与教学报告"])


def report_dict(item):
    return {"id": item.id, "course_id": item.course_id, "user_id": item.user_id, "scope": item.scope,
            "status": item.status, "error": item.error, "created_at": item.created_at,
            "title": item.title, "content": item.content, "statistics": item.statistics, "ai_mode": item.ai_mode}


@router.post("/courses/{course_id}/reports")
def create_report(course_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_user)):
    require_course(db, user, course_id, teacher=user.role != "student")
    item = Report(course_id=course_id, user_id=user.id, scope="personal" if user.role == "student" else "course",
                  ai_mode=request.app.state.settings.mode)
    db.add(item)
    db.commit()
    dispatch(request, db, "report", item)
    return report_dict(item)


@router.get("/courses/{course_id}/reports")
def list_reports(course_id: int, db: Session = Depends(get_db), user=Depends(get_user)):
    require_course(db, user, course_id, teacher=user.role != "student")
    query = db.query(Report).filter_by(course_id=course_id)
    if user.role == "student":
        query = query.filter_by(user_id=user.id, scope="personal")
    return [report_dict(r) for r in query.order_by(Report.id.desc()).limit(100)]


@router.get("/reports/{item_id}")
def get_report(item_id: int, db: Session = Depends(get_db), user=Depends(get_user)):
    return report_dict(get_owned(db, user, Report, item_id, "报告"))


@router.get("/reports/{item_id}/download")
def download_report(item_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_user)):
    item = get_owned(db, user, Report, item_id, "报告")
    if item.status != "ready" or not item.storage_key:
        raise HTTPException(409, "报告尚未就绪")
    try:
        from ..services.storage import load_bytes
        content = load_bytes(request.app.state.settings, item.storage_key)
    except Exception:
        raise HTTPException(503, "报告文件暂不可用，请稍后重试")
    return Response(content, media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="zhima-report-{item.id}.md"'})


@router.post("/reports/{item_id}/retry")
def retry_report(item_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_user)):
    item = get_owned(db, user, Report, item_id, "报告")
    changed = db.query(Report).filter_by(id=item.id, status="failed").update(
        {"status": "pending", "error": ""}, synchronize_session=False)
    db.commit()
    if changed != 1:
        raise HTTPException(409, "仅失败的报告可重试")
    dispatch(request, db, "report", item)
    return report_dict(item)
