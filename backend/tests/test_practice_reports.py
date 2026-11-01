import json
from types import SimpleNamespace

import pytest

from conftest import login


def create_practice(client, student, mode="quiz", count=2):
    client.app.state.settings.mode = "demo"
    response = client.post("/api/courses/1/practice-sessions", headers=student,
                           json={"mode": mode, "count": count})
    assert response.status_code == 200, response.text
    return response.json()


def test_practice_hides_answers_and_enforces_owner(client, student, teacher):
    item = create_practice(client, student)
    assert item["status"] == "ready"
    assert len(item["questions"]) == 2
    assert all(q["prompt"] and q["topic"] for q in item["questions"])
    assert "reference_answer" not in json.dumps(item)
    other = login(client, "student2")
    assert client.get(f"/api/practice-sessions/{item['id']}", headers=other).status_code == 403
    assert client.get(f"/api/practice-sessions/{item['id']}", headers=teacher).status_code == 200
    assert "reference_answer" not in client.get(f"/api/practice-sessions/{item['id']}", headers=teacher).text


def test_practice_answers_are_idempotent_and_conflicts_rejected(client, student):
    item = create_practice(client, student)
    path = f"/api/practice-sessions/{item['id']}/answers"
    body = {"answers": ["我的答案", "我的第二个答案"], "request_id": "practice-1"}
    first = client.post(path, headers=student, json=body)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "graded"
    assert first.json()["feedback"]["mode"] == "demo"
    second = client.post(path, headers=student, json=body)
    assert second.status_code == 200
    assert second.json()["feedback"] == first.json()["feedback"]
    body["answers"][0] = "changed"
    assert client.post(path, headers=student, json=body).status_code == 409


def test_practice_rejects_wrong_answer_count(client, student):
    item = create_practice(client, student)
    response = client.post(f"/api/practice-sessions/{item['id']}/answers", headers=student,
                           json={"answers": ["one"], "request_id": "bad-count"})
    assert response.status_code == 422


def test_invalid_ai_questions_fail_without_demo_fallback_and_retry(client, student, monkeypatch):
    from app.services import practice
    client.app.state.settings.mode = "deepseek"
    monkeypatch.setattr(practice, "deepseek_json", lambda *a: {"questions": [{"prompt": "q"}]})
    response = client.post("/api/courses/1/practice-sessions", headers=student, json={"mode": "quiz", "count": 1})
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["questions"] == []
    monkeypatch.setattr(practice, "deepseek_json", lambda *a: {"questions": [
        {"prompt": "解释事务", "topic": "事务", "reference_answer": "ACID"}]})
    retried = client.post(f"/api/practice-sessions/{response.json()['id']}/retry", headers=student)
    assert retried.status_code == 200
    assert retried.json()["status"] == "ready"
    assert "ACID" not in retried.text


def test_reports_download_utf8_and_deny_other_student(client, student, teacher):
    client.app.state.settings.mode = "demo"
    response = client.post("/api/courses/1/reports", headers=student)
    assert response.status_code == 200, response.text
    item = response.json()
    assert item["status"] == "ready", item
    assert item["scope"] == "personal"
    assert "统计" in item["content"]
    path = f"/api/reports/{item['id']}/download"
    download = client.get(path, headers=student)
    assert download.status_code == 200
    assert download.content.decode("utf-8") == item["content"]
    assert ".md" in download.headers["content-disposition"]
    assert client.get(path, headers=login(client, "student2")).status_code == 403
    assert client.get(path, headers=teacher).status_code == 200
    assert client.post("/api/courses/1/reports", headers=teacher).json()["scope"] == "course"


def test_judge0_unconfigured_is_explicitly_unavailable(client, student):
    client.app.state.settings.judge0_url = ""
    response = client.post("/api/courses/1/execute", headers=student,
                           json={"language": "python", "code": "print(1)", "stdin": ""})
    assert response.status_code == 503
    assert "Judge0" in response.text


def test_duplicate_worker_delivery_does_not_regenerate_or_regrade(client, student, monkeypatch):
    from app.models import PracticeSession
    from app.services import practice
    item = create_practice(client, student, count=1)
    def should_not_call(*args):
        raise AssertionError("duplicate delivery invoked paid model")
    monkeypatch.setattr(practice, "deepseek_json", should_not_call)
    with client.app.state.Session() as db:
        row = db.get(PracticeSession, item["id"])
        practice.process_practice(db, row, SimpleNamespace(mode="deepseek"))
        assert row.status == "ready"
    body = {"answers": ["answer"], "request_id": "unique"}
    assert client.post(f"/api/practice-sessions/{item['id']}/answers", headers=student, json=body).status_code == 200
    with client.app.state.Session() as db:
        row = db.get(PracticeSession, item["id"])
        practice.grade_practice(db, row, SimpleNamespace(mode="deepseek"))
        assert row.status == "graded"


def test_interview_reveals_one_round_at_a_time_and_feedback_persists(client, student):
    item = create_practice(client, student, mode="interview", count=2)
    assert len(item["questions"]) == 1
    assert item["current_round"] == 1
    path = f"/api/practice-sessions/{item['id']}/answers"
    body = {"answers": ["第一轮回答"], "request_id": "round-1"}
    first = client.post(path, headers=student, json=body)
    assert first.status_code == 200, first.text
    data = first.json()
    assert data["status"] == "ready"
    assert data["current_round"] == 2
    assert len(data["questions"]) == 2
    assert len(data["feedback"]["items"]) == 1
    assert "reference_answer" in data["feedback"]["items"][0]
    assert "reference_answer" not in data["questions"][1]
    assert client.post(path, headers=student, json=body).json() == data
    second = client.post(path, headers=student, json={"answers": ["第一轮回答", "第二轮回答"], "request_id": "round-2"})
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "graded"
    assert len(second.json()["feedback"]["items"]) == 2
    reloaded = client.get(f"/api/practice-sessions/{item['id']}", headers=student).json()
    assert reloaded["feedback"] == second.json()["feedback"]


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -1, 101, True])
def test_practice_rejects_invalid_scores_without_persisting_feedback(client, student, monkeypatch, score):
    from app.services import practice
    item = create_practice(client, student, count=1)
    client.app.state.settings.mode = "deepseek"
    monkeypatch.setattr(practice, "deepseek_json", lambda *args: {"items": [{"score": score, "feedback": "建议"}], "summary": "建议"})
    response = client.post(f"/api/practice-sessions/{item['id']}/answers", headers=student,
                           json={"answers": ["答"], "request_id": "invalid-score"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "failed"
    assert response.json()["feedback"] is None


def test_stale_worker_cannot_overwrite_newer_practice_attempt(client, student, monkeypatch):
    from app.models import PracticeSession
    from app.services import practice
    item = create_practice(client, student, count=1)
    with client.app.state.Session() as db:
        row = db.get(PracticeSession, item["id"])
        row.status = "pending"
        db.commit()
        def interrupted_provider(*args):
            with client.app.state.Session() as other_db:
                newer = other_db.get(PracticeSession, item["id"])
                newer.status, newer.attempts = "ready", newer.attempts + 1
                newer.questions = [{"prompt": "newer", "topic": "事务", "reference_answer": "new"}]
                other_db.commit()
            return {"questions": [{"prompt": "stale", "topic": "事务", "reference_answer": "old"}]}
        monkeypatch.setattr(practice, "deepseek_json", interrupted_provider)
        practice.process_practice(db, row, SimpleNamespace(mode="deepseek"))
        db.refresh(row)
        assert row.questions[0]["prompt"] == "newer"


def test_report_uses_only_personal_nonseed_scores_and_excludes_nonfinite(client, student):
    from app.models import Assignment, Submission, User
    client.app.state.settings.mode = "demo"
    with client.app.state.Session() as db:
        user = db.query(User).filter_by(username="student").one()
        other = db.query(User).filter_by(username="student2").one()
        assignment = db.query(Assignment).filter_by(course_id=1).first()
        for owner, seed, score, request in [(user.id, False, 80, "real"), (user.id, True, 10, "seed-extra"),
                                             (other.id, False, 20, "other-real"), (user.id, False, "Infinity", "bad-legacy")]:
            db.add(Submission(assignment_id=assignment.id, student_id=owner, request_id=request,
                              code="answer", status="graded", grade={"score": score}, is_seed=seed))
        db.commit()
    response = client.post("/api/courses/1/reports", headers=student)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ready", response.text
    stats = response.json()["statistics"]
    assert stats["submissions"] == 2
    assert stats["average_score"] == 80


def test_judge0_enforces_course_language_and_remote_resource_caps(client, student, monkeypatch):
    import httpx
    from app.services import execution
    client.app.state.settings.judge0_url = "https://sandbox.example"
    payloads = []
    def get_remote(url, **kwargs):
        return httpx.Response(200, request=httpx.Request("GET", url), json=[{"id": 91, "name": "Java (JDK 17)"},
                               {"id": 71, "name": "Python (3.8.1)"}, {"id": 82, "name": "SQL (SQLite 3.27.2)"}])
    def post_remote(url, **kwargs):
        payloads.append(kwargs["json"])
        return httpx.Response(201, request=httpx.Request("POST", url), json={"token": "safe-token"})
    monkeypatch.setattr(execution.httpx, "get", get_remote)
    monkeypatch.setattr(execution.httpx, "post", post_remote)
    wrong = client.post("/api/courses/1/execute", headers=student, json={"language": "python", "code": "print(1)"})
    assert wrong.status_code == 422
    assert payloads == []
    good = client.post("/api/courses/1/execute", headers=student, json={"language": "sql", "code": "select 1;"})
    assert good.status_code == 200, good.text
    assert good.json()["status"] == "queued"
    assert payloads[0]["language_id"] == 82
    assert payloads[0]["cpu_time_limit"] <= 2
    assert payloads[0]["memory_limit"] <= 128000
    assert payloads[0]["enable_network"] is False
    assert payloads[0]["max_file_size"] <= 64
    denied = client.get(f"/api/executions/{good.json()['id']}", headers=login(client, "student2"))
    assert denied.status_code == 403


def test_interview_serializer_hides_future_questions():
    from app.routers.practice import practice_dict
    item = SimpleNamespace(id=1, course_id=1, user_id=1, mode="interview", ai_mode="demo", count=2,
                           status="ready", error="", created_at=None, answers=[], feedback=None,
                           questions=[{"prompt": "first", "topic": "A", "reference_answer": "secret A"},
                                      {"prompt": "future", "topic": "B", "reference_answer": "secret B"}])
    data = practice_dict(item)
    assert data["questions"] == [{"prompt": "first", "topic": "A"}]


def test_practice_rejects_blank_feedback_and_report_narrative(client, student, monkeypatch):
    from app.services import practice, reporting
    item = create_practice(client, student, count=1)
    client.app.state.settings.mode = "deepseek"
    monkeypatch.setattr(practice, "deepseek_json", lambda *args: {"items": [{"score": 80, "feedback": "  "}], "summary": "  "})
    graded = client.post(f"/api/practice-sessions/{item['id']}/answers", headers=student,
                         json={"answers": ["answer"], "request_id": "blank-feedback"})
    assert graded.json()["status"] == "failed"
    monkeypatch.setattr(reporting, "deepseek_json", lambda *args: {"content": "  "})
    report = client.post("/api/courses/1/reports", headers=student)
    assert report.json()["status"] == "failed"


def test_course_permission_rechecked_on_practice_and_report_download(client, student):
    from app.models import Enrollment, User
    practice = create_practice(client, student, count=1)
    report = client.post("/api/courses/1/reports", headers=student).json()
    with client.app.state.Session() as db:
        user = db.query(User).filter_by(username="student").one()
        db.query(Enrollment).filter_by(user_id=user.id, course_id=1).delete()
        db.commit()
    for path in [f"/api/practice-sessions/{practice['id']}", f"/api/reports/{report['id']}/download"]:
        assert client.get(path, headers=student).status_code == 403
    assert client.post("/api/courses/1/practice-sessions", headers=student, json={"count": 1}).status_code == 403


def test_judge0_status_is_bounded_and_recovers_without_resubmitting(client, student, monkeypatch):
    import base64
    import httpx
    from app.models import Execution, User
    from app.services import execution
    client.app.state.settings.judge0_url = "https://sandbox.example"
    with client.app.state.Session() as db:
        user = db.query(User).filter_by(username="student").one()
        item = Execution(course_id=1, user_id=user.id, language="sql", code="select 1", token="valid-token", status="queued")
        db.add(item)
        db.commit()
        item_id = item.id
    responses = [{"status": {"id": 3, "description": "Accepted"}, "time": "Infinity", "memory": 1024,
                  "stdout": base64.b64encode(b"1").decode(), "stderr": None, "compile_output": None, "message": None},
                 {"status": {"id": 3, "description": "Accepted"}, "time": "0.01", "memory": 1024,
                  "stdout": base64.b64encode(b"1").decode(), "stderr": None, "compile_output": None, "message": None}]
    def remote_get(url, **kwargs):
        return httpx.Response(200, request=httpx.Request("GET", url), json=responses.pop(0))
    monkeypatch.setattr(execution.httpx, "get", remote_get)
    bad = client.get(f"/api/executions/{item_id}", headers=student)
    assert bad.status_code == 200
    assert bad.json()["status"] == "queued"
    assert bad.json()["result"] is None
    recovered = client.get(f"/api/executions/{item_id}", headers=student).json()
    assert recovered["status"] == "completed"
    assert recovered["result"]["stdout"] == "1"
    assert recovered["error"] == ""


def test_language_list_reports_actual_course_supported_languages(client, student, monkeypatch):
    from app.services import execution
    import httpx
    client.app.state.settings.judge0_url = ""
    unavailable = client.get("/api/courses/1/execution-languages", headers=student).json()
    assert unavailable["available"] is False
    client.app.state.settings.judge0_url = "https://sandbox.example"
    monkeypatch.setattr(execution.httpx, "get", lambda url, **kwargs: httpx.Response(200,
        request=httpx.Request("GET", url), json=[{"id": 82, "name": "SQL (SQLite)"}, {"id": 71, "name": "Python (3.8)"}]))
    available = client.get("/api/courses/1/execution-languages", headers=student).json()
    assert available["languages"] == [{"id": 82, "name": "SQL (SQLite)", "language": "sql"}]


def test_report_range_includes_practice_without_submissions(client, student):
    create_practice(client, student, count=1)
    report = client.post("/api/courses/1/reports", headers=student).json()
    assert report["statistics"]["submissions"] == 0
    assert report["statistics"]["practice_sessions"] == 1
    assert report["statistics"]["range_start"] is not None


def test_real_function_tools_enforce_permission_and_queue_actual_records(client):
    from app.jobs import run_job
    from app.models import Enrollment, PracticeSession, User
    from app.services.agent_tools import build_agent_tools
    from fastapi import HTTPException
    client.app.state.settings.mode = "demo"
    with client.app.state.Session() as db:
        user = db.query(User).filter_by(username="student").one()
        def enqueue(kind, item_id):
            run_job(client.app.state.Session, client.app.state.settings, kind, item_id)
        tools = {tool.metadata.name: tool for tool in build_agent_tools(db, user, client.app.state.settings, enqueue)}
        result = tools["generate_practice"].call(course_id=2, count=1).raw_output
        assert result["status"] == "ready"
        row = db.get(PracticeSession, result["id"])
        assert row.course_id == 2 and row.user_id == user.id
        db.query(Enrollment).filter_by(course_id=2, user_id=user.id).delete()
        db.commit()
        for name in ["generate_practice", "generate_report"]:
            with pytest.raises(HTTPException) as caught:
                tools[name].call(course_id=2)
            assert caught.value.status_code == 403
        with pytest.raises(HTTPException) as caught:
            tools["execute_code"].call(course_id=2, language="python", code="print(1)")
        assert caught.value.status_code == 403


def test_concurrent_delivery_cannot_claim_active_generation(client, student, monkeypatch):
    from app.models import PracticeSession, User
    from app.services import practice
    with client.app.state.Session() as db:
        user = db.query(User).filter_by(username="student").one()
        row = PracticeSession(course_id=1, user_id=user.id, mode="quiz", count=1)
        db.add(row)
        db.commit()
        calls = []
        def provider(*args):
            calls.append("paid-call")
            with client.app.state.Session() as other:
                duplicate = other.get(PracticeSession, row.id)
                practice.process_practice(other, duplicate, SimpleNamespace(mode="deepseek"))
                assert duplicate.status == "generating"
            return {"questions": [{"prompt": "question", "topic": "事务", "reference_answer": "reference"}]}
        monkeypatch.setattr(practice, "deepseek_json", provider)
        practice.process_practice(db, row, SimpleNamespace(mode="deepseek"))
        assert row.status == "ready"
        assert row.attempts == 1
        assert len(calls) == 1


def test_report_accepts_observed_provider_json_object_metadata(client, student, monkeypatch):
    from app.services import reporting
    client.app.state.settings.mode = "deepseek"
    # Actual DeepSeek live response adds this harmless response-format marker.
    monkeypatch.setattr(reporting, "deepseek_json", lambda *args: {
        "type": "json_object", "content": "## 学习建议\n\n当前样本少，先完成列表与字典练习并核对边界条件。"})
    response = client.post("/api/courses/2/reports", headers=student)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ready", response.text
    assert "学习建议" in response.json()["content"]
    download = client.get(f"/api/reports/{response.json()['id']}/download", headers=student)
    assert download.status_code == 200
    assert download.content.decode("utf-8") == response.json()["content"]


@pytest.mark.parametrize("metadata", [{"type": "executable"}, {"statistics": {"submissions": 999}}])
def test_report_still_rejects_unsupported_provider_metadata(client, student, monkeypatch, metadata):
    from app.services import reporting
    client.app.state.settings.mode = "deepseek"
    monkeypatch.setattr(reporting, "deepseek_json", lambda *args: {"content": "建议", **metadata})
    response = client.post("/api/courses/2/reports", headers=student)
    assert response.json()["status"] == "failed"
    assert response.json()["content"] == ""


def test_report_request_satisfies_deepseek_json_mode_protocol(client, student, monkeypatch):
    import httpx
    from app.services import generation
    client.app.state.settings.mode = "deepseek"
    def provider(url, **kwargs):
        payload = kwargs["json"]
        request = httpx.Request("POST", url)
        # DeepSeek JSON mode requires a literal json keyword in its messages.
        valid = payload.get("response_format") == {"type": "json_object"} and any(
            "json" in message["content"].lower() for message in payload["messages"])
        if not valid:
            return httpx.Response(400, request=request, json={"error": {"message": "JSON mode requires json in messages"}})
        return httpx.Response(200, request=request, json={"choices": [{"message": {"content": '{"content":"Complete one course exercise and review its feedback."}'}}]})
    monkeypatch.setattr(generation.httpx, "post", provider)
    response = client.post("/api/courses/2/reports", headers=student)
    assert response.json()["status"] == "ready", response.text
