"""Explicit, small paid acceptance for course, general and real web-assisted chat."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
CASES = {"course": (1, "SQL 中 email IS NULL 与 email = NULL 的差异是什么？", False),
         "general": (2, "法国的首都是哪座城市？请直接回答。", False),
         "web_general": (3, "故宫博物院 开放时间", True),
         "web_course": (2, "Python 列表推导式", True)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--paid", action="store_true")
    parser.add_argument("--case", choices=list(CASES))
    args = parser.parse_args()
    if not args.paid:
        parser.error("Use --paid to allow the small real DeepSeek acceptance requests")
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(data_dir=ROOT / ".cache" / "tmp" / ("hybrid-ai-" + datetime.now().strftime("%Y%m%d-%H%M%S")))
    app.state.settings.mode = "deepseek"
    app.state.settings.web_search_enabled = True
    evidence = {"model": app.state.settings.deepseek_model, "cases": []}
    with TestClient(app) as client:
        login = client.post("/api/auth/login", json={"username": "student", "password": "Demo12345!"}).json()
        headers = {"Authorization": "Bearer " + login["access_token"]}
        for name, (cid, question, web) in CASES.items():
            if args.case and args.case != name:
                continue
            response = client.post(f"/api/courses/{cid}/chat", headers=headers, json={"question": question, "web_search": web})
            data = response.json()
            answer = data.get("answer", {})
            passed = response.status_code == 200 and bool(answer.get("content")) and "没有找到足够依据" not in answer.get("content", "")
            if name == "general":
                passed = passed and "巴黎" in answer["content"] and answer["answer_basis"] == "model"
            if name.startswith("web_"):
                passed = passed and answer.get("web_search", {}).get("status") == "success" and any(c.get("source_type") == "web" for c in answer.get("citations", []))
            if name == "course":
                passed = passed and any(c.get("source_type") == "course" for c in answer.get("citations", []))
            evidence["cases"].append({"name": name, "question": question, "passed": bool(passed), "http_status": response.status_code, "response": data})
            print(("PASS " if passed else "FAIL ") + name, flush=True)
            if response.status_code == 200:
                history = client.get(f"/api/conversations/{data['conversation_id']}", headers=headers).json()
                assert history["messages"][-1]["content"] == answer["content"]
                assert history["messages"][-1]["web_search"] == answer["web_search"]
    app.state.engine.dispose()
    target = ROOT / "artifacts" / ("hybrid-live-" + (args.case or "all") + ".json")
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    if not all(item["passed"] for item in evidence["cases"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
