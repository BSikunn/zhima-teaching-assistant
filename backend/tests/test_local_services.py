from io import BytesIO
import os
from pathlib import Path
import pytest

from app.config import Settings


def test_isolated_apps_never_inherit_live_sandbox_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("JUDGE0_URL", "https://ce.judge0.com")
    monkeypatch.setenv("JUDGE0_KEY", "private")
    monkeypatch.setenv("JUDGE0_API_HOST", "private.example")
    s = Settings(tmp_path)
    assert (s.judge0_url, s.judge0_key, s.judge0_host) == ("", "", "")


class MissingObject(Exception):
    code = "NoSuchKey"


class ObjectResponse(BytesIO):
    def release_conn(self):
        pass


class ObjectStore:
    def __init__(self):
        self.files = {}
    def bucket_exists(self, bucket):
        return True
    def get_object(self, bucket, key):
        if key not in self.files:
            raise MissingObject()
        return ObjectResponse(self.files[key])
    def put_object(self, bucket, key, data, size, **kwargs):
        self.files[key] = data.read()


def test_storage_migration_preserves_uploads_reports_and_is_idempotent(tmp_path):
    from app.services.storage_migration import migrate_local_objects
    s = Settings(tmp_path)
    (s.uploads / "lesson.md").write_text("课程讲义", encoding="utf-8")
    report = s.data_dir / "objects" / "reports" / "1" / "study.md"
    report.parent.mkdir(parents=True)
    report.write_text("历史报告", encoding="utf-8")
    s.storage_backend = "minio"
    store = ObjectStore()
    result = migrate_local_objects(s, client=store)
    assert result["copied"] == result["verified"] == 2
    assert store.files["uploads/lesson.md"].decode() == "课程讲义"
    assert store.files["reports/1/study.md"].decode() == "历史报告"
    assert report.read_text(encoding="utf-8") == "历史报告"
    rerun = migrate_local_objects(s, client=store)
    assert rerun["copied"] == 0 and rerun["existing"] == rerun["verified"] == 2


def test_storage_migration_refuses_conflicting_remote_object(tmp_path):
    from app.services.storage_migration import migrate_local_objects
    s = Settings(tmp_path)
    s.storage_backend = "minio"
    (s.uploads / "lesson.md").write_bytes(b"local")
    store = ObjectStore()
    store.files["uploads/lesson.md"] = b"different remote history"
    with pytest.raises(ValueError, match="冲突"):
        migrate_local_objects(s, client=store)
    assert store.files["uploads/lesson.md"] == b"different remote history"


def test_activation_verification_rejects_changed_sources_or_target(tmp_path):
    from app.services.storage_migration import migrate_local_objects, validate_migration_receipt
    s = Settings(tmp_path)
    s.storage_backend = "minio"
    source = s.uploads / "lesson.md"
    source.write_bytes(b"initial")
    store = ObjectStore()
    receipt = migrate_local_objects(s, client=store)
    validate_migration_receipt(s, receipt, client=store)
    source.write_bytes(b"new data after migration")
    with pytest.raises(ValueError, match="本地文件已变化"):
        validate_migration_receipt(s, receipt, client=store)
    assert store.files["uploads/lesson.md"] == b"initial"
    source.write_bytes(b"initial")
    s.minio_bucket += "-other"
    with pytest.raises(ValueError, match="迁移目标"):
        validate_migration_receipt(s, receipt, client=store)


def test_activation_verification_requires_actual_remote_content(tmp_path):
    from app.services.storage_migration import migrate_local_objects, validate_migration_receipt
    s = Settings(tmp_path)
    s.storage_backend = "minio"
    (s.uploads / "lesson.md").write_bytes(b"initial")
    store = ObjectStore()
    receipt = migrate_local_objects(s, client=store)
    store.files["uploads/lesson.md"] = b"remote corruption"
    with pytest.raises(ValueError, match="目标文件"):
        validate_migration_receipt(s, receipt, client=store)


def test_failed_migration_rerun_invalidates_previous_success_receipt(tmp_path, monkeypatch):
    import importlib.util
    import sys
    from app.config import ROOT
    spec = importlib.util.spec_from_file_location("local_services_cli", ROOT / "scripts" / "local-services.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    settings = Settings(tmp_path / "data")
    folder = tmp_path / ".runtime" / "services"
    folder.mkdir(parents=True)
    receipt = folder / "storage-migration.json"
    receipt.write_text('{"verified":38,"copied":38,"existing":0}', encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr("app.config.Settings", lambda: settings)
    monkeypatch.setattr(sys, "argv", ["local-services.py", "migrate-storage"])
    def fail(*args, **kwargs):
        raise RuntimeError("migration interrupted")
    monkeypatch.setattr("app.services.storage_migration.migrate_local_objects", fail)
    with pytest.raises(RuntimeError, match="interrupted"):
        module.main()
    assert not receipt.exists()


def test_service_process_record_cannot_target_unrelated_process():
    from app.services.local_runtime import owned_process
    import psutil
    current = psutil.Process()
    with pytest.raises(RuntimeError, match="其他项目"):
        owned_process({"project": "C:/different-project", "pid": os.getpid(), "created": current.create_time()}, "redis")
    from app.config import ROOT
    with pytest.raises(RuntimeError, match="身份"):
        owned_process({"project": str(ROOT), "pid": os.getpid(), "created": current.create_time(), "executable": current.exe()}, "redis")
