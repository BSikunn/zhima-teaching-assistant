"""HTTP client for the single-owner Chroma/BGE index service."""
import httpx
from .generation import GenerationError


def _request(settings, path, payload):
    try:
        response = httpx.post(settings.index_url + path, json=payload,
                              headers={"Authorization": "Bearer " + settings.index_token}, timeout=settings.index_timeout)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except (httpx.HTTPError, ValueError):
        raise GenerationError("课程向量索引服务不可用，请稍后重试或联系管理员") from None


def search(settings, course_id, question, limit=3):
    result = _request(settings, "/search", {"course_id": course_id, "question": question, "limit": limit})
    matches = result.get("matches")
    if not isinstance(matches, list):
        raise GenerationError("课程向量索引返回格式无效")
    return matches


def index_material(settings, course_id, material_id, chunks):
    if settings.retrieval_backend != "vector":
        return
    _request(settings, "/materials/upsert", {"course_id": course_id, "material_id": material_id,
        "chunks": [{"chunk_id": c.id, "text": c.text, "location": c.location} for c in chunks]})


def delete_material(settings, course_id, material_id):
    if settings.retrieval_backend == "vector":
        _request(settings, "/materials/delete", {"course_id": course_id, "material_id": material_id})


def sync_ready_materials(db, settings):
    from ..models import Material, KnowledgeChunk
    count = 0
    for material in db.query(Material).filter_by(status="ready").all():
        chunks = db.query(KnowledgeChunk).filter_by(material_id=material.id, course_id=material.course_id).order_by(KnowledgeChunk.position).all()
        index_material(settings, material.course_id, material.id, chunks)
        count += 1
    return count


if __name__ == "__main__":
    import sys
    from ..config import Settings
    from ..db import make_database
    if sys.argv[1:] != ["sync"]:
        raise SystemExit("Usage: python -m app.services.vectors sync")
    settings = Settings()
    engine, factory = make_database(settings.database_url)
    try:
        with factory() as db:
            print({"indexed_materials": sync_ready_materials(db, settings)})
    finally:
        engine.dispose()
