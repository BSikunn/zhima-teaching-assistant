"""Project-owned portable processes. No Windows service or system changes."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit

import httpx
import psutil
from ..config import ROOT

RECORDS = ROOT / ".runtime" / "services"
WORKER_NAME = "zhima-local@localhost"
MARKERS = {"redis": "redis-server.exe", "minio": "minio.exe", "celery": "app.jobs:celery_app"}


def owned_process(record, kind):
    if Path(record.get("project", "")).resolve() != ROOT:
        raise RuntimeError("进程记录属于其他项目，拒绝停止")
    try:
        process = psutil.Process(int(record["pid"]))
        if abs(process.create_time() - float(record["created"])) > 0.001:
            raise RuntimeError("托管进程身份已改变")
        command = " ".join(process.cmdline())
        if MARKERS[kind] not in command or str(ROOT).lower() not in command.lower():
            raise RuntimeError("托管进程身份不匹配")
        if Path(process.exe()).resolve() != Path(record["executable"]).resolve():
            raise RuntimeError("托管进程身份不匹配")
        return process
    except psutil.NoSuchProcess:
        return None


def _record(kind):
    path = RECORDS / (kind + ".json")
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _listening(port):
    with socket.socket() as connection:
        connection.settimeout(0.3)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def _redis(settings):
    import redis
    return redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)


def probe(settings, kind):
    if kind == "redis":
        client = _redis(settings)
        try:
            return bool(client.ping())
        finally:
            client.close()
    if kind == "minio":
        response = httpx.get("http://" + settings.minio_endpoint + "/minio/health/live", timeout=2, trust_env=False)
        return response.status_code == 200
    from ..jobs import get_celery_app
    return bool(get_celery_app(settings.redis_url).control.inspect(destination=[WORKER_NAME], timeout=2).ping())


def _spawn(settings, kind, command, directory, environment=None, port=None):
    RECORDS.mkdir(parents=True, exist_ok=True)
    record = _record(kind)
    if record and owned_process(record, kind):
        if not probe(settings, kind):
            raise RuntimeError(f"{kind} 托管进程存在但健康检查失败，请先检查项目日志")
        return "reused"
    if port and _listening(port):
        raise RuntimeError(f"{kind} 端口已被其他进程占用，未覆盖或停止该进程")
    (ROOT / "logs").mkdir(exist_ok=True)
    flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    with (ROOT / "logs" / (kind + ".stdout.log")).open("ab") as stdout, (ROOT / "logs" / (kind + ".stderr.log")).open("ab") as stderr:
        child = subprocess.Popen(command, cwd=directory, env=environment or os.environ.copy(), stdout=stdout, stderr=stderr, creationflags=flags)
    process = psutil.Process(child.pid)
    receipt = {"project": str(ROOT), "pid": child.pid, "created": process.create_time(), "executable": process.exe()}
    (RECORDS / (kind + ".json")).write_text(json.dumps(receipt), encoding="utf-8")
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError(f"{kind} 提前退出；查看项目 logs/{kind}.stderr.log")
        try:
            if probe(settings, kind):
                return "started"
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"{kind} 启动超时，查看项目日志；进程记录已保留")


def start_services(settings):
    result = {}
    if settings.task_mode == "celery":
        redis_address = urlsplit(settings.redis_url)
        if redis_address.hostname not in {"127.0.0.1", "localhost"}:
            raise RuntimeError("便携启动器仅管理本机 Redis；远程服务请独立管理")
        if not redis_address.password:
            raise RuntimeError("本机 Redis 必须配置随机访问密码")
        manifest = ROOT / ".runtime" / "tools" / "redis" / "download-manifest.json"
        executable = Path(json.loads(manifest.read_text(encoding="utf-8"))["executable"])
        directory = settings.data_dir / "redis"
        directory.mkdir(parents=True, exist_ok=True)
        from urllib.parse import unquote
        password = unquote(redis_address.password)
        if not password.isalnum():
            raise RuntimeError("便携 Redis 密码须为随机字母数字")
        configuration = (f"bind 127.0.0.1\nprotected-mode yes\nport {redis_address.port or 6379}\n"
            f"requirepass {password}\ndir .\nsave \"\"\nappendonly yes\nappendfsync everysec\nauto-aof-rewrite-percentage 0\nlogfile \"\"\n")
        (directory / "redis.conf").write_text(configuration, encoding="utf-8")
        result["redis"] = _spawn(settings, "redis", [str(executable), "redis.conf"], directory, port=redis_address.port or 6379)
    if settings.storage_backend == "minio":
        if settings.minio_endpoint != "127.0.0.1:9000" or settings.minio_secure:
            raise RuntimeError("便携 MinIO 启动器仅管理 127.0.0.1:9000")
        executable = ROOT / ".runtime" / "tools" / "minio" / "minio.exe"
        directory = settings.data_dir / "minio"
        certs = settings.data_dir / "minio-certs"
        directory.mkdir(parents=True, exist_ok=True)
        certs.mkdir(exist_ok=True)
        environment = {**os.environ, "MINIO_ROOT_USER": settings.minio_access_key,
            "MINIO_ROOT_PASSWORD": settings.minio_secret_key, "MINIO_BROWSER": "off"}
        command = [str(executable), "server", "--quiet", "--address", "127.0.0.1:9000", "--console-address", "127.0.0.1:9001",
                   "--certs-dir", str(certs), str(directory)]
        result["minio"] = _spawn(settings, "minio", command, ROOT, environment, port=9000)
    if settings.task_mode == "celery":
        command = [str(ROOT / ".venv" / "Scripts" / "python.exe"), "-m", "celery", "-A", "app.jobs:celery_app", "worker",
                   "--pool=threads", "--concurrency=2", "--loglevel=info", "--hostname=" + WORKER_NAME]
        result["celery"] = _spawn(settings, "celery", command, ROOT)
    return result


def stop_services(settings):
    from ..jobs import get_celery_app
    stopped = []
    for kind in ("celery", "minio", "redis"):
        record = _record(kind)
        process = owned_process(record, kind) if record else None
        if not process:
            continue
        if kind == "celery":
            get_celery_app(settings.redis_url).control.broadcast("shutdown", destination=[WORKER_NAME])
            try:
                process.wait(timeout=120)
            except psutil.TimeoutExpired:
                raise RuntimeError("Celery 仍在执行任务，未强制停止；请稍后重试") from None
        elif kind == "redis":
            client = _redis(settings)
            try:
                client.shutdown(nosave=True)
            finally:
                client.close()
            process.wait(timeout=15)
        else:
            # API is stopped and the worker drained before this idle storage process.
            children = process.children(recursive=True)
            for child in children:
                child.terminate()
            process.terminate()
            psutil.wait_procs(children + [process], timeout=15)
        (RECORDS / (kind + ".json")).unlink(missing_ok=True)
        stopped.append(kind)
    return {"stopped": stopped}
