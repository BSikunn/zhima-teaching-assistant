"""Small, explicitly requested paid acceptance run against the private DeepSeek config."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--paid", action="store_true", help="Allow nine small DeepSeek requests")
    args = parser.parse_args()
    if not args.paid:
        parser.error("Use --paid to authorize the real provider acceptance requests")
    import httpx
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.main import create_app
    from app.services.vectors import index_material
    from app.models import Material, KnowledgeChunk

    private = Settings()
    if not private.deepseek_key:
        raise RuntimeError("Private DeepSeek key is missing")
    models = httpx.get(private.deepseek_url.rstrip("/") + "/models",
        headers={"Authorization": "Bearer " + private.deepseek_key}, timeout=30)
    models.raise_for_status()
    available = [m["id"] for m in models.json()["data"]]
    if private.deepseek_model not in available:
        raise RuntimeError("Configured DeepSeek model is not available; update DEEPSEEK_MODEL")
    data_dir = ROOT / ".cache" / "tmp" / ("live-ai-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    app = create_app(data_dir=data_dir)
    s = app.state.settings
    s.mode, s.deepseek_model, s.retrieval_backend = "deepseek", private.deepseek_model, "vector"
    s.index_url, s.index_token, s.index_timeout = private.index_url, private.index_token, private.index_timeout
    with app.state.Session() as db:
        for material in db.query(Material).filter_by(status="ready"):
            index_material(s, material.course_id, material.id,
                db.query(KnowledgeChunk).filter_by(material_id=material.id).all())
    evidence = {"model": s.deepseek_model, "available_models": available, "checks": [],
        "data_dir": str(data_dir), "basis": "isolated acceptance database; actual API requests"}
    def check(name, condition, details):
        evidence["checks"].append({"name": name, "passed": bool(condition), "details": details})
        print(("PASS " if condition else "FAIL ") + name, flush=True)
        if not condition:
            save()
            raise RuntimeError(name + " failed")
    def save():
        (ROOT / "artifacts" / "live-ai-acceptance.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    with TestClient(app) as client:
        token = client.post("/api/auth/login", json={"username": "student", "password": "Demo12345!"}).json()["access_token"]
        headers = {"Authorization": "Bearer " + token}
        prompts = {1: "SQL 中如何正确判断一个字段为空？", 2: "Python 中列表和字典分别有什么用途？", 3: "Java 中如何理解类、对象和封装？"}
        for course_id, question in prompts.items():
            response = client.post(f"/api/courses/{course_id}/chat", headers=headers, json={"question": question})
            data = response.json()
            answer = data.get("answer") or {}
            check(f"course {course_id} grounded DeepSeek answer", response.status_code == 200 and bool(answer.get("citations")) and answer.get("mode") == "deepseek",
                {"status": response.status_code, "response": data})
            assignments = client.get(f"/api/courses/{course_id}/assignments", headers=headers).json()
            assignment = assignments[0]
            code = {1: "SELECT * FROM students WHERE email = NULL;", 2: "print(sum([1, 2, 3]))", 3: "public class Main { public static void main(String[] args) { System.out.println(6); } }"}[course_id]
            result = client.post(f"/api/assignments/{assignment['id']}/submissions", headers=headers,
                json={"code": code, "request_id": f"live-acceptance-{course_id}"})
            graded = result.json()
            check(f"course {course_id} actual LLM grading", result.status_code == 200 and graded.get("status") in {"graded", "needs_review"} and (graded.get("grade") or {}).get("mode") == "deepseek",
                {"status": result.status_code, "response": graded})
        practice = client.post("/api/courses/2/practice-sessions", headers=headers, json={"mode": "quiz", "count": 1}).json()
        check("generated Python quiz hides answer", practice.get("status") == "ready" and "reference_answer" not in json.dumps(practice), practice)
        graded = client.post(f"/api/practice-sessions/{practice['id']}/answers", headers=headers,
            json={"answers": ["Python 中列表保存有序元素，字典按键保存值；遍历时注意索引与键的区别。"], "request_id": "live-quiz-answer"}).json()
        check("actual quiz grading", graded.get("status") == "graded" and (graded.get("feedback") or {}).get("mode") == "deepseek", graded)
        report = client.post("/api/courses/2/reports", headers=headers, json={}).json()
        check("actual report generation", report.get("status") == "ready" and report.get("ai_mode") == "deepseek", report)
        download = client.get(f"/api/reports/{report['id']}/download", headers=headers)
        check("UTF-8 report download", download.status_code == 200 and "Python" in download.text, {"bytes": len(download.content)})
    app.state.engine.dispose()
    save()


if __name__ == "__main__":
    main()
