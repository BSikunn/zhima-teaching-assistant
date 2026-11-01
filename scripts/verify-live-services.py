"""Actual Redis/Celery, MinIO and Judge0 acceptance; isolate learning records."""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--paid", action="store_true", help="Allow two real model calls for isolated grade/report acceptance")
    args = parser.parse_args()
    if not args.paid:
        parser.error("Pass --paid for the two small, real grade/report model requests")
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.main import create_app
    from app.jobs import get_celery_app
    from app.services.storage import minio_client
    from urllib.parse import urlsplit, urlunsplit
    import httpx

    target = Settings()
    assert target.task_mode == "celery" and target.storage_backend == "minio"
    validation_id = uuid.uuid4().hex[:12]
    data = ROOT / ".cache" / ("services-validation-" + validation_id)
    app = create_app(data_dir=data)
    broker = urlunsplit(urlsplit(target.redis_url)._replace(path="/15"))
    bucket = "zhima-validation-" + validation_id
    worker_name = "zhima-validation-" + validation_id + "@localhost"
    s = app.state.settings
    for name in ["minio_endpoint", "minio_access_key", "minio_secret_key", "minio_secure"]:
        setattr(s, name, getattr(target, name))
    s.mode, s.task_mode, s.storage_backend, s.minio_bucket, s.redis_url = "deepseek", "celery", "minio", bucket, broker
    storage = minio_client(s)
    storage.make_bucket(bucket)
    worker_environment = {**os.environ, "DATA_DIR": str(data), "DATABASE_URL": s.database_url,
        "REDIS_URL": broker, "MINIO_BUCKET": bucket, "AI_MODE": "deepseek", "TASK_MODE": "celery",
        "STORAGE_BACKEND": "minio", "RETRIEVAL_BACKEND": "lexical", "PYTHONPATH": str(ROOT / "backend")}
    evidence = {"scope": "isolated SQLite, Redis database15 and a temporary private MinIO bucket; own sandbox test code only", "checks": []}
    def check(name, condition, details):
        evidence["checks"].append({"name": name, "passed": bool(condition), "details": details})
        print(("PASS " if condition else "FAIL ") + name, flush=True)
        if not condition:
            raise RuntimeError(name)
    worker = None
    celery = get_celery_app(broker)
    log = (ROOT / "logs" / "services-validation-worker.log").open("ab")
    try:
        worker = subprocess.Popen([sys.executable, "-m", "celery", "-A", "app.jobs:celery_app", "worker", "--pool=threads", "--concurrency=2",
            "--hostname=" + worker_name, "--loglevel=info"], cwd=ROOT, env=worker_environment, stdout=log, stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        ready = False
        for _ in range(20):
            if celery.control.inspect(destination=[worker_name], timeout=1).ping():
                ready = True
                break
            if worker.poll() is not None:
                break
            time.sleep(0.5)
        check("real isolated Celery worker ping", ready, {"pool": "threads", "concurrency": 2})
        with TestClient(app) as client:
            def login(account):
                token = client.post("/api/auth/login", json={"username": account, "password": "Demo12345!"}).json()["access_token"]
                return {"Authorization": "Bearer " + token}
            teacher, student = login("teacher"), login("student")
            lesson = client.post("/api/courses/1/materials", headers=teacher,
                files={"file": ("服务验收资料.txt", "服务验收独立资料：事务通过原子性维护一致的业务更新。".encode())}).json()
            for _ in range(30):
                lesson = next(x for x in client.get("/api/courses/1/materials", headers=teacher).json() if x["id"] == lesson["id"])
                if lesson["status"] in {"ready", "failed"}:
                    break
                time.sleep(0.5)
            check("queued material parsed and stored in MinIO", lesson["status"] == "ready" and lesson["chunks"] > 0, lesson)
            downloaded = client.get(f"/api/materials/{lesson['id']}/download", headers=teacher)
            check("MinIO material download", downloaded.status_code == 200 and "事务" in downloaded.text, {"bytes": len(downloaded.content)})
            submission = client.post("/api/assignments/1/submissions", headers=student,
                json={"code": "SELECT * FROM students WHERE email = NULL;", "request_id": validation_id}).json()
            for _ in range(120):
                submission = client.get(f"/api/submissions/{submission['id']}", headers=student).json()
                if submission["status"] in {"graded", "needs_review", "failed"}:
                    break
                time.sleep(1)
            check("real DeepSeek grading through Redis and Celery", submission["status"] == "graded" and (submission.get("grade") or {}).get("mode") == "deepseek",
                  {"status": submission["status"], "attempts": submission["attempts"], "error": submission.get("error")})
            report = client.post("/api/courses/1/reports", headers=student, json={}).json()
            for _ in range(120):
                report = client.get(f"/api/reports/{report['id']}", headers=student).json()
                if report["status"] in {"ready", "failed"}:
                    break
                time.sleep(1)
            check("real report generated by worker", report["status"] == "ready" and report["ai_mode"] == "deepseek", {"status": report["status"], "error": report.get("error")})
            content = client.get(f"/api/reports/{report['id']}/download", headers=student)
            check("MinIO UTF8 report download", content.status_code == 200 and "数据库" in content.text, {"bytes": len(content.content)})
        # Exercise the real application's sandbox boundary with authored harmless code.
        with httpx.Client(base_url="http://127.0.0.1:8765", trust_env=False, timeout=20) as client:
            token = client.post("/api/auth/login", json={"username": "student", "password": "Demo12345!"}).json()["access_token"]
            auth = {"Authorization": "Bearer " + token}
            programs = [(2, "python", 'print("zhima-service-python")', "zhima-service-python"),
                        (3, "java", 'public class Main { public static void main(String[] args) { System.out.println("zhima-service-java"); } }', "zhima-service-java"),
                        (1, "sql", "SELECT 'zhima-service-sql';", "zhima-service-sql")]
            for course, language, code, marker in programs:
                response = client.post(f"/api/courses/{course}/execute", headers=auth, json={"language": language, "code": code, "stdin": ""})
                response.raise_for_status()
                execution = response.json()
                for _ in range(45):
                    if execution["status"] not in {"pending", "queued", "running"}:
                        break
                    time.sleep(1)
                    execution = client.get(f"/api/executions/{execution['id']}", headers=auth).json()
                result = execution.get("result") or {}
                check("official Judge0 " + language + " execution through app", execution["status"] == "completed" and marker in result.get("stdout", ""),
                      {"status": execution["status"], "stdout": result.get("stdout"), "error": execution.get("error")})
    finally:
        if worker is not None:
            celery.control.broadcast("shutdown", destination=[worker_name])
            try:
                worker.wait(timeout=60)
            except subprocess.TimeoutExpired:
                import psutil
                process = psutil.Process(worker.pid)
                for child in process.children(recursive=True):
                    child.terminate()
                process.terminate()
        log.close()
        app.state.engine.dispose()
        if bucket.startswith("zhima-validation-") and bucket.endswith(validation_id):
            for item in list(storage.list_objects(bucket, recursive=True)):
                storage.remove_object(bucket, item.object_name)
            storage.remove_bucket(bucket)
        (ROOT / "artifacts" / "live-services-acceptance.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
