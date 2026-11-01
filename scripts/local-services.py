"""Manage only this project's portable Redis, MinIO and Celery processes."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop", "status", "migrate-storage"])
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(args.env_file, override=True)
    from app.config import Settings
    from app.services.local_runtime import start_services, stop_services, probe
    s = Settings()
    if args.action == "start":
        result = start_services(s)
    elif args.action == "stop":
        result = stop_services(s)
    elif args.action == "migrate-storage":
        from app.services.storage_migration import migrate_local_objects
        folder = ROOT / ".runtime" / "services"
        folder.mkdir(parents=True, exist_ok=True)
        receipt = folder / "storage-migration.json"
        receipt.unlink(missing_ok=True)  # A failed rerun must invalidate an older success.
        result = migrate_local_objects(s)
        temporary = folder / "storage-migration.pending.json"
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, receipt)
        result = {k: v for k, v in result.items() if k != "objects"}
    else:
        result = {}
        for kind in ["redis", "minio", "celery"]:
            try:
                result[kind] = bool(probe(s, kind))
            except Exception:
                result[kind] = False
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error) if isinstance(error, (RuntimeError, ValueError)) else "服务操作失败，请检查项目日志", file=sys.stderr)
        sys.exit(1)
