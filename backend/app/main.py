from pathlib import Path
import sys
from loguru import logger
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .config import Settings, ROOT
from .db import Base, make_database, get_db
from .models import Submission, User
from .seed import seed_database
from .security import get_user, public_user, require_course
from .routers import auth, courses, materials, chat, assignments, learning, admin, practice, reports, execution


def create_app(data_dir: Path | None = None) -> FastAPI:
    if sys.version_info[:2] not in {(3, 11), (3, 12)}:
        raise RuntimeError("本项目支持 Python 3.11/3.12，请使用项目内运行环境")
    app = FastAPI(title="智码助教 API", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.settings = Settings(data_dir)
    if data_dir is None:
        (ROOT / "logs").mkdir(exist_ok=True)
        logger.add(ROOT / "logs" / "backend.log", rotation="5 MB", retention=3, encoding="utf-8")
    engine, factory = make_database(app.state.settings.database_url)
    app.state.engine, app.state.Session = engine, factory
    Base.metadata.create_all(engine)
    with factory() as db:
        if app.state.settings.task_mode == "eager":
            from .jobs import recover_eager_jobs
            recover_eager_jobs(db)
        seed_database(db, app.state.settings)
    app.include_router(auth.router)
    app.include_router(courses.router)
    app.include_router(materials.router)
    app.include_router(chat.router)
    app.include_router(assignments.router)
    app.include_router(learning.router)
    app.include_router(admin.router)
    app.include_router(practice.router)
    app.include_router(reports.router)
    app.include_router(execution.router)

    @app.get("/api/health")
    def health():
        # Windows PowerShell 5.1 otherwise decodes non-ASCII paths incorrectly.
        return JSONResponse({"status": "ok", "product": "zhima-prototype", "project_root": str(ROOT), "python": sys.version.split()[0], "mode": app.state.settings.mode, "web_search_enabled": app.state.settings.web_search_enabled,
                             "task_mode": app.state.settings.task_mode, "storage_backend": app.state.settings.storage_backend}, media_type="application/json; charset=utf-8")

    @app.get("/api/admin/users")
    def users(db=Depends(get_db), user=Depends(get_user)):
        if user.role != "admin":
            raise HTTPException(403, "此操作仅管理员可用")
        return [public_user(u) for u in db.query(User).all()]

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "接口不存在")
        dist = (ROOT / "frontend" / "dist").resolve()
        candidate = (dist / path).resolve()
        if not candidate.is_relative_to(dist):
            raise HTTPException(404, "页面不存在")
        if candidate.is_file():
            return FileResponse(candidate)
        if (dist / "index.html").is_file():
            return FileResponse(dist / "index.html")
        raise HTTPException(503, "前端尚未构建，请执行项目安装脚本")

    return app
