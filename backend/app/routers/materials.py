from pathlib import Path
import uuid
import tempfile
from urllib.parse import quote
from fastapi import APIRouter, Depends, Request, HTTPException, UploadFile, File
from fastapi.responses import Response
from loguru import logger
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Material, KnowledgeChunk, LearningEvent
from ..security import get_user, require_course
from ..services.documents import SUPPORTED, extract_document
from ..services.storage import store_bytes, load_bytes, StorageError
from ..services.vectors import index_material, delete_material
from ..services.generation import GenerationError
from ..jobs import dispatch_job

router = APIRouter(prefix="/api", tags=["知识库"])


def material_dict(m, db):
    return {"id": m.id, "filename": m.filename, "status": m.status, "error": m.error, "pages": m.pages,
            "size": m.size, "is_seed": m.is_seed, "created_at": m.created_at,
            "chunks": db.query(KnowledgeChunk).filter_by(material_id=m.id).count()}


def process_material(db, material, settings):
    claimed = db.query(Material).filter_by(id=material.id, status="pending").update(
        {"status": "processing", "error": ""}, synchronize_session=False)
    db.commit()
    db.refresh(material)
    if not claimed:
        return
    try:
        temp_dir = settings.data_dir / "tmp"
        temp_dir.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=temp_dir, suffix=Path(material.stored_name).suffix, delete=False) as temporary:
            temp_path = Path(temporary.name)
        try:
            temp_path.write_bytes(load_bytes(settings, "uploads/" + material.stored_name))
            chunks = extract_document(temp_path, use_llamaindex=settings.retrieval_backend == "vector")
        finally:
            temp_path.unlink(missing_ok=True)
        # Lock the current state before replacing SQL fragments. Deletion wins over a late worker.
        still_owned = db.query(Material).filter_by(id=material.id, status="processing").update(
            {"error": ""}, synchronize_session=False)
        if not still_owned:
            db.rollback()
            db.refresh(material)
            return
        db.query(KnowledgeChunk).filter_by(material_id=material.id).delete()
        stored = []
        for i, chunk in enumerate(chunks):
            row = KnowledgeChunk(course_id=material.course_id, material_id=material.id, position=i, **chunk)
            db.add(row)
            stored.append(row)
        db.commit()
        index_material(settings, material.course_id, material.id, stored)
        db.query(Material).filter_by(id=material.id, status="processing").update(
            {"status": "ready", "pages": len({c["location"] for c in chunks})}, synchronize_session=False)
    except Exception as error:
        db.rollback()
        logger.warning("Material {} parsing failed: {}", material.id, type(error).__name__)
        detail = str(error)[:300] if isinstance(error, (ValueError, GenerationError, StorageError)) else "文件结构损坏或无法解析，请检查文件后重新上传"
        db.query(Material).filter_by(id=material.id, status="processing").update(
            {"status": "failed", "error": detail}, synchronize_session=False)
    db.commit()
    db.refresh(material)


@router.get("/courses/{course_id}/materials")
def list_materials(course_id: int, db: Session = Depends(get_db), user=Depends(get_user)):
    require_course(db, user, course_id)
    rows = db.query(Material).filter(Material.course_id == course_id, Material.status != "deleted").order_by(Material.id.desc()).all()
    return [material_dict(m, db) for m in rows]


@router.post("/courses/{course_id}/materials")
async def upload_material(course_id: int, request: Request, file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(get_user)):
    require_course(db, user, course_id, teacher=True)
    filename = Path((file.filename or "file").replace("\\", "/")).name[:200]
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED:
        raise HTTPException(400, "支持 PDF、PPTX、DOCX、TXT、MD、SRT、VTT；请先转换旧版 DOC/PPT 文件")
    settings = request.app.state.settings
    content = await file.read(settings.max_upload_bytes + 1)
    if not content or len(content) > settings.max_upload_bytes:
        raise HTTPException(400, "文件为空或超过 20 MB，请检查后重试")
    name = uuid.uuid4().hex + extension
    try:
        store_bytes(settings, "uploads/" + name, content, file.content_type or "application/octet-stream")
    except StorageError as error:
        raise HTTPException(503, str(error))
    material = Material(course_id=course_id, filename=filename, stored_name=name, size=len(content))
    db.add(material)
    db.commit()
    dispatch_job(request, "material", material.id)
    db.refresh(material)
    db.add(LearningEvent(course_id=course_id, user_id=user.id, kind="material", text=f"上传了资料：{filename}"))
    db.commit()
    return material_dict(material, db)


def accessible_material(material_id, db, user, teacher=False):
    material = db.get(Material, material_id)
    if not material or material.status == "deleted":
        raise HTTPException(404, "资料不存在或已删除")
    require_course(db, user, material.course_id, teacher=teacher)
    return material


@router.get("/materials/{material_id}")
def detail(material_id: int, db: Session = Depends(get_db), user=Depends(get_user)):
    m = accessible_material(material_id, db, user)
    return {**material_dict(m, db), "segments": [{"id": c.id, "text": c.text, "location": c.location} for c in db.query(KnowledgeChunk).filter_by(material_id=m.id).order_by(KnowledgeChunk.position)]}


@router.get("/materials/{material_id}/download")
def download(material_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_user)):
    m = accessible_material(material_id, db, user)
    try:
        content = load_bytes(request.app.state.settings, "uploads/" + m.stored_name)
    except FileNotFoundError:
        raise HTTPException(404, "原始文件已丢失，请联系教师")
    except StorageError as error:
        raise HTTPException(503, str(error))
    return Response(content, media_type="application/octet-stream", headers={"Content-Disposition": "attachment; filename*=UTF-8''" + quote(m.filename)})


@router.post("/materials/{material_id}/retry")
def retry(material_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_user)):
    m = accessible_material(material_id, db, user, teacher=True)
    claimed = db.query(Material).filter_by(id=m.id, status="failed").update({"status": "pending", "error": ""}, synchronize_session=False)
    db.commit()
    if not claimed:
        raise HTTPException(409, "仅失败资料可重试，请刷新当前状态")
    dispatch_job(request, "material", m.id)
    db.refresh(m)
    return material_dict(m, db)


@router.delete("/materials/{material_id}")
def remove(material_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_user)):
    m = accessible_material(material_id, db, user, teacher=True)
    m.status = "deleted"
    db.commit()
    try:
        delete_material(request.app.state.settings, m.course_id, m.id)
    except GenerationError:
        # SQL excludes the material immediately even if external cleanup needs retry.
        logger.warning("Material {} vector cleanup deferred", m.id)
    return {"ok": True}
