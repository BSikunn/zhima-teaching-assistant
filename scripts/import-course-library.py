"""Inspect or explicitly back up and import the bundled, attributed course library."""
import argparse
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "backend"))


def main():
    parser = argparse.ArgumentParser(description="课程资料库：默认只检查；实际导入前请停止 API 与 worker")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true", help="先备份，再导入缺失资料；保留教师删除及原资料")
    action.add_argument("--backup", action="store_true", help="只备份当前库和对象，不写入资料")
    parser.add_argument("--data-dir", type=Path, help="隔离的数据目录；不填则读取项目现有配置")
    parser.add_argument("--backup-directory", type=Path, help="MySQL 已停止服务的一致性备份目录")
    args = parser.parse_args()
    from app.services.library import load_library
    items = load_library()
    if not args.apply and not args.backup:
        print(json.dumps({"action": "inspect", "total": len(items), "courses": {
            str(cid): sum(item["course_id"] == cid for item in items) for cid in (1, 2, 3)},
            "bytes": sum(len(item["content"]) for item in items)}, ensure_ascii=False, indent=2))
        return
    from app.config import Settings
    from app.migration import backup_database
    settings = Settings(data_dir=args.data_dir)
    if args.backup_directory:
        settings.migration_backup_directory = args.backup_directory
    if args.backup:
        report = backup_database(settings)
    else:
        from app.db import make_database
        from app.services.library import import_course_library
        engine, factory = make_database(settings.database_url)
        try:
            with factory() as db:
                report = import_course_library(db, settings)
        finally:
            engine.dispose()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("failed"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
