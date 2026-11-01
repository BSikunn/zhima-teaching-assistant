"""Judge0 adapter. User code is sent only to the configured remote sandbox."""
import base64
import math

import httpx
from fastapi import HTTPException

from ..models import Execution
from ..security import require_course


def headers(settings):
    key = getattr(settings, "judge0_key", "")
    host = getattr(settings, "judge0_host", "")
    return ({"X-RapidAPI-Key": key, "X-RapidAPI-Host": host} if host else {"X-Auth-Token": key}) if key else {}


def endpoint(settings):
    url = getattr(settings, "judge0_url", "").rstrip("/")
    if not url:
        raise HTTPException(503, "未配置 Judge0，代码执行暂不可用")
    return url


def course_language(course):
    code = course.code.upper().split("-", 1)[0]
    return {"DB": "sql", "PY": "python", "JAVA": "java"}.get(code)


def available_languages(settings):
    response = httpx.get(endpoint(settings) + "/languages", headers=headers(settings), timeout=15)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list) or len(data) > 500:
        raise ValueError("invalid language list")
    return [{"id": entry["id"], "name": entry["name"][:200],
             "language": entry["name"].lower().split(" ", 1)[0]}
            for entry in data if isinstance(entry, dict) and type(entry.get("id")) is int
            and entry["id"] > 0 and isinstance(entry.get("name"), str)
            and entry["name"].lower().split(" ", 1)[0] in {"python", "java", "sql"}]


def submit_execution(db, user, course_id, language, code, stdin, settings):
    course = require_course(db, user, course_id, teacher=user.role != "student")
    url = endpoint(settings)
    if (language != course_language(course) or not isinstance(code, str) or not code.strip()
            or len(code) > 20000 or not isinstance(stdin, str) or len(stdin) > 10000):
        raise HTTPException(422, "执行语言或代码/输入长度无效")
    item = Execution(course_id=course_id, user_id=user.id, language=language, code=code, stdin=stdin)
    db.add(item)
    db.commit()
    try:
        # Query the actual instance: language IDs differ between Judge0 releases.
        available = [entry for entry in available_languages(settings) if entry["language"] == language]
        if not available:
            item.status, item.error = "failed", "Judge0 实例不支持所选语言"
            db.commit()
            raise HTTPException(422, item.error)
        response = httpx.post(url + "/submissions", params={"base64_encoded": "true", "wait": "false"},
            headers=headers(settings), timeout=15, json={
                "language_id": available[-1]["id"],
                "source_code": base64.b64encode(code.encode("utf-8")).decode("ascii"),
                "stdin": base64.b64encode(stdin.encode("utf-8")).decode("ascii"),
                "cpu_time_limit": 2, "wall_time_limit": 5, "memory_limit": 128000,
                "max_file_size": 64, "enable_network": False,
                "number_of_runs": 1})
        response.raise_for_status()
        token = response.json().get("token")
        if not isinstance(token, str) or not token or len(token) > 100 or any(c not in "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-_" for c in token):
            raise ValueError("invalid token")
        item.token, item.status = token, "queued"
        db.commit()
    except HTTPException:
        raise
    except Exception:
        item.status, item.error = "failed", "Judge0 请求失败，请检查沙箱服务状态"
        db.commit()
    return item


def refresh_execution(db, item, settings):
    if item.status not in {"queued", "running"} or not item.token:
        return item
    try:
        response = httpx.get(endpoint(settings) + "/submissions/" + item.token,
            params={"base64_encoded": "true", "fields": "stdout,stderr,compile_output,message,status,time,memory"},
            headers=headers(settings), timeout=15)
        response.raise_for_status()
        data = response.json()
        status_id = data["status"]["id"]
        if type(status_id) is not int or not 1 <= status_id <= 14:
            raise ValueError("invalid status")
        elapsed = float(data["time"]) if data.get("time") is not None else None
        memory = data.get("memory")
        if ((elapsed is not None and (not math.isfinite(elapsed) or elapsed < 0))
                or (memory is not None and (type(memory) is not int or memory < 0))):
            raise ValueError("invalid resources")
        result = {"status": {"id": status_id, "description": str(data["status"].get("description", ""))[:200]},
                  "time": elapsed, "memory": memory}
        for name in ("stdout", "stderr", "compile_output", "message"):
            value = data.get(name)
            if value and (not isinstance(value, str) or len(value) > 90000):
                raise ValueError("sandbox output exceeds cap")
            result[name] = base64.b64decode(value, validate=True).decode("utf-8", errors="replace")[:65536] if value else ""
        item.result = result
        item.status = "queued" if status_id == 1 else "running" if status_id == 2 else "completed" if status_id == 3 else "failed"
        item.error = result["status"]["description"] if status_id > 3 else ""
        db.commit()
    except Exception:
        # Preserve token so a transient status request can be retried without resubmitting code.
        item.error = "Judge0 状态查询失败，请稍后刷新"
        db.commit()
    return item
