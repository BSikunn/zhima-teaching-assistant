import pytest
import httpx
from test_learning import submit


@pytest.mark.parametrize("code", ["not SQL email = NULL nonsense", "SELECT 'email = NULL';", "SELECT * FROM students WHERE email = NULL; DROP TABLE students;"])
def test_unsupported_sql_never_creates_numeric_demo_grade(client, student, code):
    record = submit(client, student, code).json()
    assert record["status"] == "needs_review"
    assert record["grade"]["score"] is None
    mistakes = client.get("/api/courses/1/mistakes", headers=student).json()
    assert not any(m["submission_id"] == record["id"] for m in mistakes)


def test_model_cannot_save_out_of_range_citation(client, student, monkeypatch):
    client.app.state.settings.mode = "deepseek"
    client.app.state.settings.deepseek_key = "test-key"
    def bad_model(*args, **kwargs):
        return httpx.Response(200, request=httpx.Request("POST", "https://example.invalid"),
                              json={"choices": [{"message": {"content": '{"content":"根据课程资料 [999]，这是答案。"}'}}]})
    monkeypatch.setattr(httpx, "post", bad_model)
    result = client.post("/api/courses/1/chat", headers=student, json={"question": "最左前缀原则"})
    assert result.status_code == 502
    assert "引用" in result.json()["detail"]
    assert client.get("/api/courses/1/conversations", headers=student).json() == []


def test_changing_assignment_meaning_disables_old_demo_rule(client, teacher, student):
    assignment = client.get("/api/courses/1/assignments", headers=teacher).json()[0]
    assignment["description"] = "查询 email 非空的学生，返回全部列。"
    assert client.put("/api/assignments/1", headers=teacher, json=assignment).status_code == 200
    result = submit(client, student, "SELECT * FROM students WHERE email IS NULL;").json()
    assert result["status"] == "needs_review"
    assert result["grade"]["score"] is None


def test_invalid_ai_mode_refuses_silent_demo_fallback(tmp_path, monkeypatch):
    from app.config import Settings
    monkeypatch.setenv("AI_MODE", "deepseak")
    with pytest.raises(ValueError, match="AI_MODE"):
        Settings(tmp_path)
