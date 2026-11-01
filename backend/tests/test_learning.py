import uuid
from conftest import login


def submit(client, headers, code="SELECT * FROM students WHERE email = NULL;", **extra):
    return client.post("/api/assignments/1/submissions", headers=headers,
                       json={"code": code, "request_id": str(uuid.uuid4()), **extra})


def test_incorrect_sql_creates_feedback_and_mistake(client, student):
    result = submit(client, student)
    assert result.status_code == 200, result.text
    grade = result.json()
    assert grade["status"] == "graded"
    assert grade["grade"]["score"] < 100
    assert grade["grade"]["error_type"] == "NULL 判断"
    mistakes = client.get("/api/courses/1/mistakes", headers=student).json()
    assert any(m["submission_id"] == grade["id"] and m["topic"] == "NULL 判断" for m in mistakes)


def test_request_id_prevents_duplicate_submissions(client, student):
    key = str(uuid.uuid4())
    first = submit(client, student, request_id=key).json()
    second = submit(client, student, request_id=key).json()
    assert first["id"] == second["id"]
    mistakes = client.get("/api/courses/1/mistakes", headers=student).json()
    assert len([m for m in mistakes if m["submission_id"] == first["id"]]) == 1


def test_correct_sql_does_not_create_mistake(client, student):
    result = submit(client, student, "SELECT * FROM students WHERE email IS NULL;").json()
    assert result["grade"]["score"] == 100
    mistakes = client.get("/api/courses/1/mistakes", headers=student).json()
    assert not any(m["submission_id"] == result["id"] for m in mistakes)


def test_teacher_review_validates_and_updates_dashboard(client, student, teacher):
    result = submit(client, student).json()
    invalid = client.post(f'/api/submissions/{result["id"]}/review', headers=teacher,
                          json={"scores": [101, 20, 20], "feedback": "复核"})
    assert invalid.status_code == 422
    valid = client.post(f'/api/submissions/{result["id"]}/review', headers=teacher,
                        json={"scores": [55, 20, 20], "feedback": "已复核，请补充边界情况"})
    assert valid.status_code == 200, valid.text
    assert valid.json()["grade"]["score"] == 95
    assert valid.json()["grade"]["reviewed"] is True
    dashboard = client.get("/api/courses/1/dashboard", headers=teacher).json()
    record = next(r for r in dashboard["recent_submissions"] if r["id"] == result["id"])
    assert record["score"] == 95


def test_private_submission_and_plan_are_isolated(client, student):
    submission = submit(client, student).json()
    plan = client.post("/api/courses/1/plans", headers=student, json={}).json()
    other = login(client, "student2")
    assert client.get(f'/api/submissions/{submission["id"]}', headers=other).status_code == 403
    assert client.patch(f'/api/plan-items/{plan["items"][0]["id"]}', headers=other,
                        json={"done": True}).status_code == 403


def test_rubric_and_deadline_are_validated(client, teacher, student):
    invalid = client.post("/api/courses/1/assignments", headers=teacher, json={
        "title": "非法作业", "description": "说明", "max_score": 100,
        "rubric": [{"name": "正确性", "max_score": 50}], "status": "published"})
    assert invalid.status_code == 422
    draft = client.post("/api/courses/1/assignments", headers=teacher, json={
        "title": "草稿", "description": "说明", "max_score": 100,
        "rubric": [{"name": "正确性", "max_score": 100}], "status": "draft"}).json()
    assert client.post(f'/api/assignments/{draft["id"]}/submissions', headers=student,
                       json={"code": "SELECT 1", "request_id": "draft"}).status_code == 409


def test_api_timeout_preserves_submission_and_retry_is_idempotent(client, student, monkeypatch):
    import httpx
    def timeout(*args, **kwargs):
        raise httpx.TimeoutException("external timeout")
    client.app.state.settings.mode = "deepseek"
    client.app.state.settings.deepseek_key = "test-external-key"
    monkeypatch.setattr(httpx, "post", timeout)
    failed = submit(client, student).json()
    assert failed["status"] == "failed" and "超时" in failed["error"]
    assert failed["grade"] is None
    client.app.state.settings.mode = "demo"
    retried = client.post(f'/api/submissions/{failed["id"]}/retry', headers=student).json()
    assert retried["status"] == "graded" and retried["attempts"] == 2
    assert client.post(f'/api/submissions/{failed["id"]}/retry', headers=student).status_code == 409
    mistakes = client.get("/api/courses/1/mistakes", headers=student).json()
    assert sum(m["submission_id"] == failed["id"] for m in mistakes) == 1


def test_persistence_after_application_restart(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    first = create_app(tmp_path)
    with TestClient(first) as c:
        headers = login(c)
        submission = submit(c, headers).json()
    first.state.engine.dispose()
    second = create_app(tmp_path)
    with TestClient(second) as c:
        headers = login(c)
        saved = c.get(f'/api/submissions/{submission["id"]}', headers=headers)
        assert saved.status_code == 200
        assert saved.json()["grade"]["error_type"] == "NULL 判断"
    second.state.engine.dispose()
