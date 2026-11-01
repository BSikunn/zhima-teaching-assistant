"""Prepare private target settings; activate only after services and copy verify."""
import argparse
import json
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / ".runtime" / "local-services.env"
sys.path.insert(0, str(ROOT / "backend"))


def main():
    from dotenv import dotenv_values
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "activate"])
    args = parser.parse_args()
    current = dotenv_values(ROOT / ".env")
    if args.action == "prepare":
        if TARGET.exists():
            print("Prepared private settings already exist; reused without printing credentials.")
            return
        values = {"TASK_MODE": "celery", "REDIS_URL": f"redis://:{secrets.token_hex(32)}@127.0.0.1:6379/0",
            "STORAGE_BACKEND": "minio", "MINIO_ENDPOINT": "127.0.0.1:9000", "MINIO_SECURE": "false",
            "MINIO_ACCESS_KEY": "zhima" + secrets.token_hex(7), "MINIO_SECRET_KEY": secrets.token_hex(32), "MINIO_BUCKET": "zhima",
            "JUDGE0_URL": "https://ce.judge0.com", "JUDGE0_KEY": "", "JUDGE0_API_HOST": ""}
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_text("\n".join(f"{k}={json.dumps(v)}" for k, v in values.items()) + "\n", encoding="utf-8")
        print("Prepared private Redis/MinIO/Judge0 settings; active .env has not changed.")
        return
    target = dotenv_values(TARGET)
    if target.get("TASK_MODE") != "celery" or target.get("STORAGE_BACKEND") != "minio":
        raise RuntimeError("Prepared service settings are incomplete")
    receipt = ROOT / ".runtime" / "services" / "storage-migration.json"
    copied = json.loads(receipt.read_text(encoding="utf-8"))
    from dotenv import load_dotenv
    load_dotenv(TARGET, override=True)
    from app.config import Settings
    from app.services.storage_migration import validate_migration_receipt
    from app.services.local_runtime import probe
    settings = Settings()
    validate_migration_receipt(settings, copied)
    if not all(probe(settings, kind) for kind in ["redis", "minio", "celery"]):
        raise RuntimeError("Prepared services failed readiness checks; active settings were preserved")
    current.update(target)
    temporary = ROOT / ".runtime" / "activated-services.env"
    temporary.write_text("\n".join(f"{k}={json.dumps(v or '', ensure_ascii=False)}" for k, v in current.items()) + "\n", encoding="utf-8")
    os.replace(temporary, ROOT / ".env")
    print("Activated service settings; credentials were not printed.")


if __name__ == "__main__":
    main()
