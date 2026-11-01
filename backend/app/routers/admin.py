import sys
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import httpx
from sqlalchemy import text
from fastapi import APIRouter, Depends, HTTPException, Request
from ..security import get_user

router = APIRouter(prefix="/api/admin", tags=["管理员"])


def _probe(name, action):
    try:
        state, detail = action()
    except Exception:
        state, detail = "unavailable", "探测未成功，请检查服务、网络与访问凭据"
    return {"name": name, "status": state, "detail": detail,
            "checked_at": datetime.now(timezone.utc).isoformat()}


@router.get("/status")
def status(request: Request, user=Depends(get_user)):
    if user.role != "admin":
        raise HTTPException(403, "仅管理员可查看服务配置")
    s = request.app.state.settings

    def database():
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return "active", "SQLite 查询成功" if s.database_url.startswith("sqlite") else "数据库查询成功"

    def ai():
        if s.mode == "demo":
            return "demo", "当前为明确标注的规则演示模式"
        if not s.deepseek_key:
            return "unconfigured", "尚未配置模型凭据"
        response = httpx.get(s.deepseek_url.rstrip("/") + "/models", timeout=3,
            headers={"Authorization": "Bearer " + s.deepseek_key})
        response.raise_for_status()
        ids = [entry.get("id") for entry in response.json().get("data", [])]
        return ("active", f"认证及模型列表探测成功；当前模型 {s.deepseek_model}") if s.deepseek_model in ids else ("unavailable", "认证成功，但配置的模型未出现在模型列表")

    def queue():
        if s.task_mode == "eager":
            return "local", "本机同步执行；生产异步队列未启用"
        import redis
        from ..jobs import get_celery_app
        connection = redis.Redis.from_url(s.redis_url, socket_connect_timeout=3, socket_timeout=3)
        try:
            connection.ping()
        finally:
            connection.close()
        workers = get_celery_app(s.redis_url).control.inspect(timeout=1).ping()
        return ("active", "Redis PING 成功且 Celery worker 有响应") if workers else ("unavailable", "Redis PING 成功，但 Celery worker 尚无响应")

    def storage():
        if s.storage_backend == "local":
            from ..services.storage import store_bytes, load_bytes, _path
            import uuid
            key = ".health/" + uuid.uuid4().hex
            try:
                store_bytes(s, key, b"probe", "text/plain")
                if load_bytes(s, key) != b"probe":
                    raise ValueError()
            finally:
                _path(s, key).unlink(missing_ok=True)
            return "local", "项目文件存储读写探测成功"
        from ..services.storage import minio_client
        exists = minio_client(s).bucket_exists(s.minio_bucket)
        return ("active", "MinIO 存储桶访问成功") if exists else ("unavailable", "MinIO 已连接，业务存储桶尚未创建")

    def retrieval():
        if s.retrieval_backend == "lexical":
            return "local", "当前使用课程隔离关键词检索"
        response = httpx.get(s.index_url + "/health", timeout=3,
            headers={"Authorization": "Bearer " + s.index_token})
        response.raise_for_status()
        if response.json().get("status") != "ok":
            raise ValueError()
        return "active", "Chroma/BGE 索引服务健康探测成功"

    def sandbox():
        if not s.judge0_url:
            return "unconfigured", "尚未配置代码沙箱"
        response = httpx.get(s.judge0_url + "/languages", timeout=3,
            headers={"X-Auth-Token": s.judge0_key} if s.judge0_key else {})
        response.raise_for_status()
        if not isinstance(response.json(), list):
            raise ValueError()
        return "active", "Judge0 语言列表探测成功"

    def internet_search():
        if not s.web_search_enabled:
            return "unconfigured", "当前关闭联网补充；模型仍可回答通用问题"
        from copy import copy
        from ..services.web_search import web_search
        probe_settings = copy(s)
        probe_settings.web_search_timeout = 3
        result = web_search(probe_settings, "Python 列表推导式")
        return ("active", "真实网页搜索探测成功") if result["status"] == "success" else ("unavailable", result["detail"])

    checks = [("FastAPI + Python " + sys.version.split()[0], lambda: ("active", "当前请求正常响应")),
              ("SQLAlchemy 数据库", database), ("DeepSeek API", ai), ("Redis + Celery", queue),
              ("MinIO / 文件存储", storage), ("Chroma + BGE + LlamaIndex 检索", retrieval), ("网页搜索", internet_search), ("Judge0 代码沙箱", sandbox)]
    with ThreadPoolExecutor(max_workers=len(checks)) as executor:
        futures = [executor.submit(_probe, name, action) for name, action in checks]
        services = [future.result() for future in futures]
    return {"mode": s.mode, "model": s.deepseek_model, "python": sys.version.split()[0],
            "data_dir": str(s.data_dir), "task_mode": s.task_mode, "storage_backend": s.storage_backend,
            "retrieval_backend": s.retrieval_backend, "services": services,
            "checked_at": datetime.now(timezone.utc).isoformat()}
