import json
import sqlite3
from pathlib import Path

from app.models import User, Conversation, Message, Submission, Mistake, StudyPlan, PlanItem, Assignment


def test_upgrade_archives_dependents_and_preserves_owned_history(client):
    from app.migration import upgrade_database
    from conftest import login
    old_token = login(client)
    with client.app.state.Session() as db:
        db.add(User(id=99, username="retired", name="旧学生", role="student", password_hash="old"))
        db.flush()
        kept = Submission(assignment_id=1, student_id=1, request_id="historical", code="old", status="graded",
                          grade={"score": 67, "mode": "demo"}, is_seed=True)
        removed = Submission(assignment_id=1, student_id=99, request_id="retired", code="private", status="graded")
        db.add_all([kept, removed])
        conversation = Conversation(course_id=1, user_id=99, title="old conversation")
        plan = StudyPlan(course_id=1, student_id=99, title="old plan")
        db.add_all([conversation, plan])
        db.flush()
        db.add(Message(conversation_id=conversation.id, role="user", content="private question"))
        db.add(PlanItem(plan_id=plan.id, title="private plan"))
        db.add(Mistake(submission_id=removed.id, student_id=99, course_id=1, topic="old", detail="private"))
        db.commit()
        kept_id = kept.id
        secret = client.app.state.settings.jwt_secret
        report = upgrade_database(db, client.app.state.settings)
        assert report["archived"]["users"] == 1
        archive = json.loads(Path(report["archive_path"]).read_text(encoding="utf-8"))
        assert archive["tables"]["messages"][0]["content"] == "private question"
        assert archive["tables"]["plan_items"][0]["title"] == "private plan"
        assert db.get(User, 99) is None
        assert db.get(Submission, kept_id).grade == {"score": 67, "mode": "demo"}
        assert db.get(Submission, kept_id).is_seed is True
        assert secret != client.app.state.settings.jwt_secret
        assert client.get("/api/courses", headers=old_token).status_code == 401
        assert client.get("/api/courses", headers=login(client)).status_code == 200
        rotated = client.app.state.settings.jwt_secret
        counts = {"assignments": db.query(Assignment).count(), "submissions": db.query(Submission).count()}
        again = upgrade_database(db, client.app.state.settings)
        assert again["already_applied"] is True
        assert client.app.state.settings.jwt_secret == rotated
        assert counts == {"assignments": db.query(Assignment).count(), "submissions": db.query(Submission).count()}
        with sqlite3.connect(report["backup"]["database"]) as old:
            assert old.execute("SELECT name FROM users WHERE id=99").fetchone()[0] == "旧学生"


def test_upgrade_backup_failure_leaves_database_and_secret_untouched(client, monkeypatch):
    from app import migration
    with client.app.state.Session() as db:
        db.add(User(id=99, username="retired", name="旧学生", role="student", password_hash="old"))
        db.commit()
        secret = client.app.state.settings.jwt_secret
        def fail(_):
            raise OSError("backup unavailable")
        monkeypatch.setattr(migration, "backup_database", fail)
        import pytest
        with pytest.raises(OSError, match="backup unavailable"):
            migration.upgrade_database(db, client.app.state.settings)
        assert db.get(User, 99) is not None
        assert client.app.state.settings.jwt_secret == secret


def test_dashboard_ignores_samples_and_counts_questions_separately(client, teacher):
    with client.app.state.Session() as db:
        db.add(Submission(assignment_id=1, student_id=1, request_id="sample", code="sample", is_seed=True,
                          grade={"score": 100}, status="graded"))
        conversation = Conversation(course_id=2, user_id=1, title="Python question")
        db.add(conversation)
        db.flush()
        db.add_all([Message(conversation_id=conversation.id, role="user", content="one"),
                    Message(conversation_id=conversation.id, role="assistant", content="answer"),
                    Message(conversation_id=conversation.id, role="user", content="two")])
        db.commit()
    database = client.get("/api/courses/1/dashboard", headers=teacher).json()
    assert database["submission_count"] == 0
    python = client.get("/api/courses/2/dashboard", headers=teacher).json()
    assert python["conversation_count"] == 1
    assert python["question_count"] == 2
    assert all("SQL" not in topic["name"] and "NULL" not in topic["name"] for topic in python["topics"])


def test_legacy_upgrade_keeps_original_account_ids_and_teacher_content(tmp_path):
    from app.config import Settings
    from app.db import Base, make_database
    from app.migration import upgrade_database
    from app.models import Course, Enrollment, AgentConfig, Material, KnowledgeChunk
    from app.security import hash_password
    settings = Settings(tmp_path)
    engine, factory = make_database(settings.database_url)
    Base.metadata.create_all(engine)
    with factory() as db:
        password = hash_password("preserved password")
        for uid, username, role in [(11, "student", "student"), (12, "teacher", "teacher"), (13, "admin", "admin"),
                                    (14, "student2", "student"), (15, "student3", "student"), (16, "student8", "student")]:
            db.add(User(id=uid, username=username, name="旧显示名", role=role, password_hash=password))
        db.flush()
        db.add_all([Course(id=1, teacher_id=12, title="数据库旧课", code="OLD"), Course(id=2, teacher_id=12, title="Python", code="PY")])
        db.flush()
        db.add(Enrollment(user_id=11, course_id=1))
        db.add(AgentConfig(course_id=1, persona="教师自定义人设", prompt="教师自定义提示", max_hint_level=1))
        assignment = Assignment(id=41, course_id=1, title="教师历史作业", description="应保留", rubric=[{"name": "维度", "max_score": 100}])
        db.add(assignment)
        material = Material(course_id=2, filename="teacher.txt", stored_name="teacher.txt", status="ready")
        db.add(material)
        db.flush()
        db.add(KnowledgeChunk(course_id=2, material_id=material.id, text="教师 Python 课程内容", location="段1"))
        db.add(Submission(assignment_id=41, student_id=11, request_id="historical", code="preserved code",
                          grade={"score": 88, "mode": "demo", "reviewed": True}, review_history=[{"score": 88}], is_seed=False))
        db.commit()
        report = upgrade_database(db, settings)
        assert {u.username: u.id for u in db.query(User)} == {"student": 11, "teacher": 12, "admin": 13, "student2": 14, "student3": 15}
        assert db.get(User, 11).password_hash == password
        assert db.get(AgentConfig, 1).persona == "教师自定义人设"
        assert db.get(AgentConfig, 1).max_hint_level == 1
        assert db.get(Assignment, 41).description == "应保留"
        assert db.query(Submission).one().student_id == 11
        assert db.query(Submission).one().review_history == [{"score": 88}]
        assert db.query(Material).filter_by(stored_name="teacher.txt").count() == 1
        assert report["archived"]["users"] == 1
    engine.dispose()


def test_resume_after_secret_persistence_failure_rotates_once(client, monkeypatch):
    from app import migration
    settings = client.app.state.settings
    with client.app.state.Session() as db:
        original = migration._rotate_secret
        def fail(*_):
            raise OSError("secret persist interrupted")
        monkeypatch.setattr(migration, "_rotate_secret", fail)
        import pytest
        with pytest.raises(OSError, match="interrupted"):
            migration.upgrade_database(db, settings)
        monkeypatch.setattr(migration, "_rotate_secret", original)
        resumed = migration.upgrade_database(db, settings)
        rotated = settings.jwt_secret
        assert resumed["already_applied"] is True
        assert not (Path(resumed["backup"]["directory"]) / ".jwt-secret.pending").exists()
        assert (Path(resumed["backup"]["directory"]) / "migration-report.json").is_file()
        migration.upgrade_database(db, settings)
        assert settings.jwt_secret == rotated


def test_source_cli_preserves_source_and_copies_local_files(client, tmp_path):
    import hashlib
    import os
    import subprocess
    import sys
    source_settings = client.app.state.settings
    (source_settings.uploads / "teacher.txt").write_text("teacher source", encoding="utf-8")
    client.app.state.engine.dispose()
    source_path = source_settings.data_dir / "zhima.db"
    before = hashlib.sha256(source_path.read_bytes()).hexdigest()
    target = tmp_path / "target"
    env = {**os.environ, "DATA_DIR": str(target), "DATABASE_URL": "sqlite:///" + str(target / "zhima.db"),
           "JWT_SECRET": "", "AI_MODE": "demo", "STORAGE_BACKEND": "local", "RETRIEVAL_BACKEND": "lexical", "TASK_MODE": "eager",
           "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    backed_up = subprocess.run([sys.executable, "-m", "app.migration", "--backup", "--source", str(source_path)],
                               env=env, text=True, capture_output=True, encoding="utf-8", timeout=30)
    assert backed_up.returncode == 0, backed_up.stderr
    assert Path(json.loads(backed_up.stdout)["database"]).is_file()
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == before
    result = subprocess.run([sys.executable, "-m", "app.migration", "--upgrade", "--source", str(source_path)],
                            env=env, text=True, capture_output=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["migrated"]["users"] == 5
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == before
    assert (target / "uploads" / "teacher.txt").read_text(encoding="utf-8") == "teacher source"
    with sqlite3.connect(target / "zhima.db") as db:
        assert db.execute("SELECT count(*) FROM courses").fetchone()[0] == 3
    rerun = subprocess.run([sys.executable, "-m", "app.migration", "--source", str(source_path)], env=env, text=True, capture_output=True, encoding="utf-8", timeout=30)
    assert rerun.returncode == 0, rerun.stderr
    assert json.loads(rerun.stdout)["already_applied"] is True


def test_source_cli_resumes_committed_import_and_refuses_changed_source(client, tmp_path, monkeypatch, capsys):
    import copy
    import sys
    import pytest
    from app import migration
    from app.db import make_database
    from app.config import Settings
    source_path = client.app.state.settings.data_dir / "zhima.db"
    target_settings = Settings(tmp_path / "resume-target")
    monkeypatch.setattr("app.config.Settings", lambda: copy.copy(target_settings))
    monkeypatch.setattr(sys, "argv", ["app.migration", "--source", str(source_path)])
    upgrade = migration.upgrade_database
    def interrupted(*_):
        raise RuntimeError("interrupted after committed import")
    monkeypatch.setattr(migration, "upgrade_database", interrupted)
    with pytest.raises(RuntimeError, match="committed import"):
        migration.main()
    engine, factory = make_database(target_settings.database_url)
    with factory() as db:
        assert db.query(User).count() == 5
    engine.dispose()
    monkeypatch.setattr(migration, "upgrade_database", upgrade)
    migration.main()
    assert json.loads(capsys.readouterr().out)["already_applied"] is False
    secret = (target_settings.data_dir / ".jwt-secret").read_text(encoding="utf-8")
    migration.main()
    assert json.loads(capsys.readouterr().out)["already_applied"] is True
    assert (target_settings.data_dir / ".jwt-secret").read_text(encoding="utf-8") == secret
    with client.app.state.Session() as db:
        db.get(User, 1).name = "source changed after import"
        db.commit()
    with pytest.raises(RuntimeError, match="源库.*不匹配"):
        migration.main()
    engine, factory = make_database(target_settings.database_url)
    with factory() as db:
        assert db.get(User, 1).name == "张三"
        assert db.query(Assignment).count() == 9
    engine.dispose()


def test_mid_upgrade_failure_rolls_back_deletions_and_can_retry(client, monkeypatch):
    from app import migration
    import pytest
    with client.app.state.Session() as db:
        db.add(User(id=99, username="retired", name="旧学生", role="student", password_hash="old"))
        db.flush()
        db.add(Conversation(course_id=1, user_id=99, title="must survive rollback"))
        db.commit()
        original = migration.ensure_course_content
        secret = client.app.state.settings.jwt_secret
        def fail(*_):
            raise RuntimeError("interrupted after delete")
        monkeypatch.setattr(migration, "ensure_course_content", fail)
        with pytest.raises(RuntimeError, match="after delete"):
            migration.upgrade_database(db, client.app.state.settings)
        assert db.get(User, 99).name == "旧学生"
        assert db.query(Conversation).filter_by(user_id=99).one().title == "must survive rollback"
        assert secret == client.app.state.settings.jwt_secret
        monkeypatch.setattr(migration, "ensure_course_content", original)
        migration.upgrade_database(db, client.app.state.settings)
        assert db.get(User, 99) is None


def test_mysql_requires_complete_external_backup_before_upgrading(client, tmp_path):
    import copy
    import pytest
    from app.migration import backup_database
    settings = copy.copy(client.app.state.settings)
    settings.database_url = "mysql+pymysql://user:password@localhost/zhima"
    with pytest.raises(RuntimeError, match="backup-directory"):
        backup_database(settings)
    folder = tmp_path / "mysql-backup"
    folder.mkdir()
    settings.migration_backup_directory = folder
    (folder / "database.sql").write_text("CREATE TABLE preserved(id INT);", encoding="utf-8")
    (folder / "manifest.json").write_text(json.dumps({"sql": "database.sql", "kind": "compose-consistent-stop"}), encoding="utf-8-sig")
    with pytest.raises(ValueError, match="COMPLETE"):
        backup_database(settings)
    (folder / "COMPLETE").write_text("Backup steps complete", encoding="utf-8")
    receipt = backup_database(settings)
    assert receipt["database"] == str(folder / "database.sql")
    assert receipt["kind"] == "mysql-external"
    assert len(receipt["sha256"]) == 64
