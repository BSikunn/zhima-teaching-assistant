"""Versioned library import: real parsing, storage, API download and deletion."""
from collections import Counter
from pathlib import Path
import re

import pytest

from app.models import KnowledgeChunk, Material
from conftest import login


def test_library_has_substantial_distinct_materials_for_three_courses():
    from app.services.library import load_library
    items = load_library()
    assert Counter(item["course_id"] for item in items) == {1: 10, 2: 10, 3: 10}
    assert len({item["id"] for item in items}) == len(items)
    assert len({item["content"] for item in items}) == len(items)
    for item in items:
        text = item["content"].decode("utf-8")
        assert len(text) >= 1000, item["filename"]
        assert len(re.findall(r"[\u4e00-\u9fff]", text)) >= 400, item["filename"]
        assert "```" in text and "练习" in text and "误区" in text
        assert "2026-10-31" in text
        assert item["sources"] and all(source["url"].startswith("https://") for source in item["sources"])


def test_import_is_idempotent_and_keeps_teacher_work_and_deletions(client):
    from app.services.library import import_course_library, load_library
    settings = client.app.state.settings
    with client.app.state.Session() as db:
        before = db.query(Material).count()
        teacher = Material(course_id=1, filename=load_library()[0]["filename"], stored_name="teacher-copy.md", status="ready")
        db.add(teacher)
        db.commit()
        report = import_course_library(db, settings)
        assert report["added"] == 30 and not report["failed"]
        assert Path(report["backup"]["database"]).is_file()
        assert db.query(Material).count() == before + 31
        assert all(db.get(Material, mid).status == "ready" for mid in report["material_ids"])
        chunk_counts = {mid: db.query(KnowledgeChunk).filter_by(material_id=mid).count() for mid in report["material_ids"]}
        assert all(count > 0 for count in chunk_counts.values()), chunk_counts
        victim = db.get(Material, report["material_ids"][0])
        victim.status = "deleted"
        db.commit()
        again = import_course_library(db, settings)
        assert again["added"] == 0 and again["skipped"] == 30 and again["deleted"] == 1
        assert db.query(Material).count() == before + 31
        assert victim.status == "deleted"
        assert db.get(Material, teacher.id).stored_name == "teacher-copy.md"


def test_imported_material_is_downloadable_and_indexed(client):
    from app.services.library import import_course_library, load_library
    with client.app.state.Session() as db:
        report = import_course_library(db, client.app.state.settings)
    auth = login(client)
    for course_id in (1, 2, 3):
        expected = next(item for item in load_library() if item["course_id"] == course_id)
        listed = client.get(f"/api/courses/{course_id}/materials", headers=auth).json()
        row = next(row for row in listed if row["filename"] == expected["filename"])
        download = client.get(f"/api/materials/{row['id']}/download", headers=auth)
        assert download.status_code == 200 and download.content == expected["content"]
        assert "attachment" in download.headers["content-disposition"]
        detail = client.get(f"/api/materials/{row['id']}", headers=auth).json()
        assert detail["segments"] and row["status"] == "ready"
    assert report["added"] == 30


def test_backup_failure_does_not_write_materials(client, monkeypatch):
    from app.services import library
    with client.app.state.Session() as db:
        before = db.query(Material).count()
        def fail(_):
            raise OSError("backup unavailable")
        monkeypatch.setattr(library, "backup_database", fail)
        with pytest.raises(OSError, match="backup unavailable"):
            library.import_course_library(db, client.app.state.settings)
        assert db.query(Material).count() == before


def test_import_refuses_uncommitted_business_changes(client):
    from app.services.library import import_course_library
    with client.app.state.Session() as db:
        db.add(Material(course_id=1, filename="pending.md", stored_name="pending.md"))
        with pytest.raises(ValueError, match="未提交"):
            import_course_library(db, client.app.state.settings)


def test_interrupted_processing_material_is_reported_incomplete_without_reset(client):
    from app.services.library import import_course_library
    with client.app.state.Session() as db:
        imported = import_course_library(db, client.app.state.settings)
        victim = db.get(Material, imported["material_ids"][0])
        victim.status = "processing"
        db.commit()
        result = import_course_library(db, client.app.state.settings)
        assert result["added"] == 0
        assert len(result["failed"]) == 1
        assert result["failed"][0]["id"] == victim.id
        assert result["failed"][0]["status"] == "processing"
        assert db.get(Material, victim.id).status == "processing"
