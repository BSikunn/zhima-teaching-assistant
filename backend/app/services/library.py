"""Explicit import of the local, attributed teaching library; never run on startup."""
import json
from pathlib import Path
import re

from ..migration import backup_database
from ..models import Course, Material
from .storage import store_bytes

LIBRARY_ROOT = Path(__file__).resolve().parents[3] / "resources" / "course-library"


def load_library(root=None):
    root = Path(root or LIBRARY_ROOT).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version") != 1 or not isinstance(manifest.get("materials"), list):
        raise ValueError("课程资料清单版本或结构无效")
    result, seen = [], set()
    for entry in manifest["materials"]:
        identity = entry["id"]
        if not re.fullmatch(r"[a-z0-9-]{1,70}", identity) or identity in seen:
            raise ValueError("课程资料标识无效或重复")
        seen.add(identity)
        if entry["course_id"] not in {1, 2, 3}:
            raise ValueError("未知课程")
        path = (root / entry["path"]).resolve()
        if not path.is_relative_to(root) or path.suffix != ".md":
            raise ValueError("课程资料路径越界或格式无效")
        content = path.read_bytes()
        text = content.decode("utf-8")
        if len(text) < 1000 or "```" not in text or not entry.get("sources"):
            raise ValueError(f"课程讲义内容不足: {identity}")
        if Path(entry["filename"]).name != entry["filename"] or len(entry["filename"]) > 200:
            raise ValueError("课程资料下载文件名无效")
        result.append({**entry, "content": content, "stored_name": f"library_v1_{identity}.md"})
    return result


def import_course_library(db, settings, root=None, *, backup=True):
    """Import missing fixed keys, preserving existing and soft-deleted teacher work.

    Stop API/workers before CLI use. `backup=False` is reserved for explicitly
    initializing an empty, freshly created installation, not for upgrades.
    Failed records stay visible for the existing teacher retry action.
    """
    if db.new or db.dirty or db.deleted:
        raise ValueError("导入需要独立会话，存在未提交业务更改")
    items = load_library(root)
    if any(db.get(Course, cid) is None for cid in {item["course_id"] for item in items}):
        raise ValueError("请先初始化三门课程，再导入资料库")
    existing = {item.stored_name: item for item in db.query(Material).filter(
        Material.stored_name.in_([entry["stored_name"] for entry in items]))}
    if any(existing[item["stored_name"]].course_id != item["course_id"]
           for item in items if item["stored_name"] in existing):
        raise ValueError("固定资料标识与现有课程冲突，拒绝覆盖")
    missing = [item for item in items if item["stored_name"] not in existing]
    pending = [row for row in existing.values() if row.status == "pending"]
    db.rollback()  # release the read transaction before the SQLite backup API
    snapshot = backup_database(settings) if backup and (missing or pending) else None
    report = {"added": 0, "skipped": len(existing), "deleted": 0, "failed": [],
              "material_ids": [], "backup": snapshot}
    # Import lazily: seed -> library must not create a routers/migration cycle.
    from ..routers.materials import process_material
    for item in items:
        material = existing.get(item["stored_name"])
        if material is None:
            store_bytes(settings, "uploads/" + item["stored_name"], item["content"], "text/markdown; charset=utf-8")
            material = Material(course_id=item["course_id"], filename=item["filename"],
                                stored_name=item["stored_name"], size=len(item["content"]), is_seed=True)
            db.add(material)
            db.commit()
            db.refresh(material)
            report["added"] += 1
        if material.status == "pending":
            process_material(db, material, settings)
        if material.status == "deleted":
            report["deleted"] += 1
        elif material.status != "ready":
            report["failed"].append({"id": material.id, "filename": material.filename,
                                     "status": material.status,
                                     "error": material.error or "任务未完成；请先停止 API/worker，检查任务恢复后按资料 ID 在教师端重试"})
        report["material_ids"].append(material.id)
    return report
