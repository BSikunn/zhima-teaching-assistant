"""Explicit, backed-up roster upgrade. Run with API/workers stopped.

    cd backend; python -m app.migration
    python -m app.migration --source ../data/zhima.db  # into an empty DATABASE_URL

Archives contain private historical data and belong only in ignored backups.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
from datetime import datetime, timezone

from sqlalchemy import Column, JSON, MetaData, String, Table, create_engine, func, inspect, select
from sqlalchemy.engine import make_url

from .db import Base, make_database
from .models import Course, User
from .seed import ROSTER, ensure_course_content
from .security import hash_password
from .services.course_content import COURSES

VERSION = "20261029-three-courses-v1"
metadata = MetaData()
runs = Table("migration_runs", metadata, Column("version", String(100), primary_key=True), Column("report", JSON, nullable=False))
source_imports = Table("migration_source_imports", metadata, Column("version", String(100), primary_key=True), Column("receipt", JSON, nullable=False))


def _backup_root(settings):
    root = Path(settings.root).resolve()
    data = Path(settings.data_dir).resolve()
    return (root if data.is_relative_to(root) else data) / ".cache" / "backups" / "upgrade-20261029"


def _write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=lambda v: v.isoformat() if hasattr(v, "isoformat") else str(v)), encoding="utf-8")
    temporary.replace(path)


def backup_database(settings):
    """Take a consistent SQLite backup, uploads and private config before SQL writes."""
    url = make_url(settings.database_url)
    if url.get_backend_name() != "sqlite":
        prepared = getattr(settings, "migration_backup_directory", None)
        if prepared:
            folder = Path(prepared).resolve()
            complete, manifest, dump = folder / "COMPLETE", folder / "manifest.json", folder / "database.sql"
            if not all(file.is_file() and file.stat().st_size > 0 for file in (complete, manifest, dump)):
                raise ValueError("MySQL 备份目录必须包含非空 COMPLETE、manifest.json 和 database.sql")
            document = json.loads(manifest.read_text(encoding="utf-8-sig"))
            if not isinstance(document, dict) or document.get("sql") != "database.sql" or document.get("kind") != "compose-consistent-stop":
                raise ValueError("MySQL 备份清单不是一致性停止备份或未声明 database.sql")
            return {"directory": str(folder), "database": str(dump), "manifest": str(manifest),
                    "kind": "mysql-external", "sha256": hashlib.sha256(dump.read_bytes()).hexdigest()}
        source_backup = getattr(settings, "migration_source_backup", None)
        if source_backup and Path(source_backup["database"]).is_file():
            return source_backup
        raise RuntimeError("非 SQLite 升级须提供 --backup-directory 一致性备份，或通过 --source 迁入空目标库")
    if not url.database or url.database == ":memory:":
        raise ValueError("迁移备份需要磁盘 SQLite 数据库")
    source = Path(url.database).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    folder = _backup_root(settings) / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + secrets.token_hex(3))
    folder.mkdir(parents=True)
    target = folder / "zhima.db"
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original, sqlite3.connect(target) as backup:
        original.backup(backup)
        if backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("SQLite 备份完整性检查失败")
    for name, directory in [("uploads", Path(settings.uploads)), ("objects", Path(settings.data_dir) / "objects")]:
        if directory.exists():
            shutil.copytree(directory, folder / name)
    for name, file in [(".jwt-secret", Path(settings.data_dir) / ".jwt-secret"), (".env", Path(settings.root) / ".env")]:
        if file.is_file():
            shutil.copy2(file, folder / name)
    result = {"directory": str(folder), "database": str(target), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    _write_json(folder / "backup-manifest.json", result)
    return result


def _archived_rows(db, tables, keep_user_ids):
    """Compute a foreign-key closure, so no deleted account's child survives."""
    rows = {table.name: [dict(row) for row in db.execute(select(table)).mappings()] for table in tables}
    removed = {table.name: set() for table in tables}
    by_name = {table.name: table for table in tables}
    def identity(table, row):
        return tuple(row[col.name] for col in table.primary_key)
    removed["users"] = {identity(by_name["users"], row) for row in rows["users"] if row["id"] not in keep_user_ids}
    removed["courses"] = {identity(by_name["courses"], row) for row in rows["courses"] if row["id"] not in COURSES}
    changed = True
    while changed:
        changed = False
        for table in tables:
            for row in rows[table.name]:
                key = identity(table, row)
                if key in removed[table.name]:
                    continue
                for foreign in table.foreign_keys:
                    # Kept courses are explicitly assigned to the retained teacher.
                    if table.name == "courses" and foreign.parent.name == "teacher_id" and row["id"] in COURSES:
                        continue
                    parent = foreign.column.table
                    if parent.name not in removed:
                        continue
                    matches = [p for p in rows[parent.name] if p[foreign.column.name] == row[foreign.parent.name]]
                    if any(identity(parent, p) in removed[parent.name] for p in matches):
                        removed[table.name].add(key)
                        changed = True
                        break
    return {table.name: [row for row in rows[table.name] if identity(table, row) in removed[table.name]] for table in tables}, rows


def _rotate_secret(settings, secret):
    """Persist the same secret used in this process and on the next startup."""
    path = Path(settings.data_dir) / ".jwt-secret"
    temporary = path.with_name(".jwt-secret.pending")
    temporary.write_text(secret, encoding="utf-8")
    temporary.replace(path)
    # A deployment may override the file. Keep its private .env consistent.
    configured_data = Path(os.getenv("DATA_DIR") or Path(settings.root) / "data").resolve()
    if os.getenv("JWT_SECRET") and Path(settings.data_dir).resolve() == configured_data:
        env_path = Path(settings.root) / ".env"
        lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
        lines = [line for line in lines if not line.lstrip().startswith("JWT_SECRET=")]
        lines.append("JWT_SECRET=" + secret)
        temporary_env = env_path.with_suffix(".env.pending")
        temporary_env.write_text("\n".join(lines) + "\n", encoding="utf-8")
        temporary_env.replace(env_path)
        os.environ["JWT_SECRET"] = secret
    settings.jwt_secret = secret


def upgrade_database(db, settings):
    """Versioned upgrade; only a successfully persisted report makes reruns no-ops."""
    if db.new or db.dirty or db.deleted:
        raise ValueError("迁移需要已提交的独立会话，不能丢弃未提交业务更改")
    engine = db.get_bind()
    if inspect(engine).has_table(runs.name):
        old = db.execute(select(runs.c.report).where(runs.c.version == VERSION)).scalar_one_or_none()
        if old:
            # Finish a crash after SQL commit but before persisting secret/report.
            pending = Path(old["backup"]["directory"]) / ".jwt-secret.pending"
            if pending.exists():
                _rotate_secret(settings, pending.read_text(encoding="utf-8"))
                pending.unlink()
            _write_json(Path(old["backup"]["directory"]) / "migration-report.json", old)
            return {**old, "already_applied": True}
    db.rollback()  # release the read transaction before SQLite's backup API
    backup = backup_database(settings)
    Base.metadata.create_all(engine)
    metadata.create_all(engine)
    reflected = MetaData()
    reflected.reflect(bind=engine)
    tables = [table for table in reflected.sorted_tables if table.name not in {runs.name, source_imports.name}]
    users = {user.username: user for user in db.query(User)}
    wanted = {username for _, username, _, _ in ROSTER}
    keep = {user.id for username, user in users.items() if username in wanted}
    archived, before = _archived_rows(db, tables, keep)
    folder = Path(backup["directory"])
    archive_path = folder / "archived-records.json"
    _write_json(archive_path, {"version": VERSION, "tables": archived})
    secret = secrets.token_urlsafe(48)
    pending_secret = folder / ".jwt-secret.pending"
    pending_secret.write_text(secret, encoding="utf-8")
    try:
        # Canonical username identifies ownership. Never match by display name.
        for preferred_id, username, name, role in ROSTER:
            user = users.get(username)
            if user is None:
                occupied = {item.id for item in users.values()}
                user = User(id=preferred_id if preferred_id not in occupied else None, username=username, name=name,
                            role=role, password_hash=hash_password("Demo12345!"))
                db.add(user)
                db.flush()
                users[username] = user
            user.name, user.role = name, role
        teacher_id = users["teacher"].id
        for course in db.query(Course).filter(Course.id.in_(COURSES)):
            course.teacher_id = teacher_id
            course.title, course.code = COURSES[course.id]["title"], COURSES[course.id]["code"]
        db.flush()
        for table in reversed(tables):
            for row in archived[table.name]:
                condition = [col == row[col.name] for col in table.primary_key]
                db.execute(table.delete().where(*condition))
        db.expire_all()
        added = ensure_course_content(db, settings, teacher_id)
        # Check every FK, including future entities, before declaring success.
        for table in tables:
            for foreign in table.foreign_keys:
                child, parent = foreign.parent, foreign.column
                invalid = select(child).where(child.is_not(None), ~child.in_(select(parent))).limit(1)
                if db.execute(invalid).first():
                    raise RuntimeError(f"迁移外键检查失败: {table.name}.{child.name}")
        added["users"] = sum(username not in {row["username"] for row in before["users"]} for _, username, _, _ in ROSTER)
        migrated = {table.name: db.execute(select(func.count()).select_from(table)).scalar_one() for table in tables}
        report = {"version": VERSION, "already_applied": False, "backup": backup, "archive_path": str(archive_path),
                  "archived": {name: len(rows) for name, rows in archived.items()},
                  "preserved": {name: len(rows) - len(archived[name]) for name, rows in before.items()}, "added": added,
                  "migrated": migrated,
                  "jwt_rotated": True, "completed_at": datetime.now(timezone.utc).isoformat()}
        db.execute(runs.insert().values(version=VERSION, report=report))
        db.commit()
    except Exception:
        db.rollback()
        pending_secret.unlink(missing_ok=True)
        raise
    _rotate_secret(settings, secret)
    pending_secret.unlink(missing_ok=True)
    _write_json(folder / "migration-report.json", report)
    return report


def import_sqlite_source(engine, settings, source_path):
    """Commit imported rows and their provenance together; resume only that source."""
    import copy
    source_path = Path(source_path).resolve()
    source_settings = copy.copy(settings)
    source_settings.database_url = "sqlite:///" + str(source_path)
    source_settings.uploads = source_path.parent / "uploads"
    source_settings.data_dir = source_path.parent
    snapshot = backup_database(source_settings)
    Base.metadata.create_all(engine)
    metadata.create_all(engine)
    with engine.begin() as target:
        old = target.execute(select(source_imports.c.receipt).where(source_imports.c.version == VERSION)).scalar_one_or_none()
        if old:
            if old["source_path"] != str(source_path) or old["source_sha256"] != snapshot["sha256"]:
                raise RuntimeError("源库身份或内容与已导入回执不匹配，拒绝覆盖目标历史")
            original_snapshot = Path(old["backup"]["database"])
            if not original_snapshot.is_file() or hashlib.sha256(original_snapshot.read_bytes()).hexdigest() != old["source_sha256"]:
                raise RuntimeError("原始源库备份缺失或校验失败，不能继续升级")
            settings.migration_source_backup = old["backup"]
            return old
        if any(target.execute(select(table).limit(1)).first() for table in Base.metadata.sorted_tables) or target.execute(select(runs).limit(1)).first():
            raise RuntimeError("--source 只允许迁入空目标库或恢复同一源库的导入，避免覆盖现有历史")
        # Import the immutable backup snapshot, keeping reads consistent with its hash.
        snapshot_path = Path(snapshot["database"])
        source_engine = create_engine("sqlite://", creator=lambda: sqlite3.connect(snapshot_path.as_uri() + "?mode=ro", uri=True))
        try:
            source_meta = MetaData()
            source_meta.reflect(bind=source_engine)
            for name in ("uploads", "objects"):
                source_folder = Path(snapshot["directory"]) / name
                target_folder = Path(settings.data_dir) / name
                if not source_folder.exists():
                    continue
                files = [file for file in source_folder.rglob("*") if file.is_file()]
                for file in files:
                    destination = target_folder / file.relative_to(source_folder)
                    if destination.exists() and destination.read_bytes() != file.read_bytes():
                        raise RuntimeError(f"目标存储存在冲突文件: {destination.name}")
                for file in files:
                    destination = target_folder / file.relative_to(source_folder)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file, destination)
            with source_engine.connect() as source:
                for table in Base.metadata.sorted_tables:
                    if table.name in source_meta.tables:
                        values = [dict(row) for row in source.execute(select(source_meta.tables[table.name])).mappings()]
                        if values:
                            target.execute(table.insert(), values)
        finally:
            source_engine.dispose()
        receipt = {"source_path": str(source_path), "source_sha256": snapshot["sha256"], "backup": snapshot,
                   "status": "imported", "imported_at": datetime.now(timezone.utc).isoformat()}
        target.execute(source_imports.insert().values(version=VERSION, receipt=receipt))
    settings.migration_source_backup = snapshot
    return receipt


def main():
    parser = argparse.ArgumentParser(description="备份并迁移智码助教数据库；请先停止 API 和 worker")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--backup", action="store_true", help="仅备份，不执行迁移或轮换 JWT")
    action.add_argument("--upgrade", action="store_true", help="备份并升级（默认动作）")
    parser.add_argument("--source", type=Path, help="保留原件的 SQLite 源库，迁入 DATABASE_URL 指定的空库")
    parser.add_argument("--backup-directory", type=Path, help="已有 MySQL 一致性备份目录，含 COMPLETE、manifest.json 和 database.sql")
    args = parser.parse_args()
    from .config import Settings
    settings = Settings()
    if args.source and args.backup_directory:
        parser.error("--source 与 --backup-directory 不能同时使用")
    if args.backup_directory:
        settings.migration_backup_directory = args.backup_directory
    if args.backup:
        if args.source:
            settings.database_url = "sqlite:///" + str(args.source.resolve())
            settings.data_dir = args.source.resolve().parent
            settings.uploads = settings.data_dir / "uploads"
        print(json.dumps(backup_database(settings), ensure_ascii=False, indent=2))
        return
    engine, factory = make_database(settings.database_url)
    try:
        if args.source:
            import_sqlite_source(engine, settings, args.source)
        with factory() as db:
            report = upgrade_database(db, settings)
    finally:
        engine.dispose()
    # Only counts/paths appear in stdout; archives and secrets stay private.
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
