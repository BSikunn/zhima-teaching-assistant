import re
from collections import Counter
from ..models import KnowledgeChunk, Material


def tokens(text):
    text = text.lower()
    for stop in ["什么是", "是什么", "为什么", "如何", "请问", "帮我", "解释一下", "知识点", "课程", "资料"]:
        text = text.replace(stop, " ")
    words = re.findall(r"[a-z_][a-z0-9_]*", text)
    for chinese in re.findall(r"[\u4e00-\u9fff]+", text):
        words.extend(chinese[i:i + 2] for i in range(len(chinese) - 1))
    return set(words)


def retrieve(db, course_id, question, limit=3, settings=None):
    if settings is not None and settings.retrieval_backend == "vector":
        from .vectors import search
        # Index text and metadata are not trusted: SQL is the authority for access and freshness.
        hits = search(settings, course_id, question, max(limit * 4, 12))
        ids = list(dict.fromkeys(h.get("chunk_id") for h in hits if isinstance(h, dict) and type(h.get("chunk_id")) is int))
        rows = db.query(KnowledgeChunk, Material).join(Material, Material.id == KnowledgeChunk.material_id).filter(
            KnowledgeChunk.id.in_(ids), KnowledgeChunk.course_id == course_id,
            Material.course_id == course_id, Material.status == "ready").all()
        records = {c.id: {"chunk_id": c.id, "material_id": m.id, "filename": m.filename,
                   "location": c.location, "text": c.text, "is_seed": m.is_seed} for c, m in rows}
        return [records[i] for i in ids if i in records][:limit]
    query = tokens(question)
    if not query:
        return []
    rows = db.query(KnowledgeChunk, Material).join(Material, Material.id == KnowledgeChunk.material_id).filter(
        KnowledgeChunk.course_id == course_id, Material.course_id == course_id, Material.status == "ready").all()
    scored = []
    for chunk, material in rows:
        overlap = query & tokens(chunk.text)
        coverage = len(overlap) / len(query)
        if not overlap or coverage < 0.28 or (len(query) > 2 and len(overlap) < 2):
            continue
        # Prefer specific short fragments over unrelated long documents.
        score = coverage + len(overlap) / (len(tokens(chunk.text)) + 1)
        scored.append((score, {"chunk_id": chunk.id, "material_id": material.id, "filename": material.filename,
                                "location": chunk.location, "text": chunk.text, "is_seed": material.is_seed}))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [record for _, record in scored[:limit]]
