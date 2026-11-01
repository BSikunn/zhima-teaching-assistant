import json
from types import SimpleNamespace

import httpx
import pytest

from app.config import Settings
from app.models import AgentConfig, Assignment, KnowledgeChunk, Material, Submission
from app.services.generation import GenerationError, answer_question, deepseek_json
from conftest import login


def test_explicit_data_dir_isolated_from_production_environment(tmp_path, monkeypatch):
    for name, value in {"AI_MODE": "deepseek", "TASK_MODE": "celery", "STORAGE_BACKEND": "minio", "RETRIEVAL_BACKEND": "vector"}.items():
        monkeypatch.setenv(name, value)
    settings = Settings(tmp_path)
    assert (settings.mode, settings.task_mode, settings.storage_backend, settings.retrieval_backend) == ("demo", "eager", "local", "lexical")


def test_configured_deepseek_model_used_without_leaking_provider_errors(tmp_path, monkeypatch):
    settings = Settings(tmp_path)
    settings.deepseek_key = "private-key"
    settings.deepseek_model = "configured-model"
    captured = {}
    def post(url, **kwargs):
        captured.update(kwargs["json"])
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok":true}'}}]}, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", post)
    assert deepseek_json(settings, "system", "user") == {"ok": True}
    assert captured["model"] == "configured-model"


@pytest.mark.parametrize("content", ["没有注明来源的回答", "引用不存在 [2]"])
def test_generated_grounded_answer_requires_valid_citation(tmp_path, monkeypatch, content):
    settings = Settings(tmp_path)
    settings.mode = "deepseek"
    config = SimpleNamespace(persona="助教", prompt="依据资料", max_hint_level=1, hint_first=True)
    monkeypatch.setattr("app.services.generation.deepseek_json", lambda *args: {"content": content})
    with pytest.raises(GenerationError):
        answer_question(settings, "问题", [{"chunk_id": 1, "text": "依据"}], config, 3, [])


def test_vector_results_revalidated_against_sql_course_and_material_state(client, monkeypatch):
    from app.services.retrieval import retrieve
    settings = client.app.state.settings
    settings.retrieval_backend = "vector"
    with client.app.state.Session() as db:
        valid = db.query(KnowledgeChunk).filter_by(course_id=1).first()
        foreign = Material(course_id=2, filename="other.txt", stored_name="other.txt", status="ready")
        removed = Material(course_id=1, filename="gone.txt", stored_name="gone.txt", status="deleted")
        db.add_all([foreign, removed]); db.flush()
        wrong = KnowledgeChunk(course_id=2, material_id=foreign.id, text="伪造", location="第 1 段")
        stale = KnowledgeChunk(course_id=1, material_id=removed.id, text="旧内容", location="第 1 段")
        db.add_all([wrong, stale]); db.commit()
        monkeypatch.setattr("app.services.vectors.search", lambda *args, **kwargs: [
            {"chunk_id": wrong.id, "text": "来自索引的伪造正文"}, {"chunk_id": stale.id}, {"chunk_id": valid.id, "text": "伪造正文"}])
        found = retrieve(db, 1, "问题", settings=settings)
        assert [item["chunk_id"] for item in found] == [valid.id]
        assert found[0]["text"] == valid.text


def test_duplicate_grade_job_does_not_call_provider_or_overwrite_review(client, monkeypatch):
    from app.services.grading import grade_submission
    settings = client.app.state.settings
    settings.mode = "deepseek"
    calls = []
    def generate(*args):
        calls.append(1)
        return {"scores": [60, 20, 20], "feedback": "通过", "hints": [], "error_type": ""}
    monkeypatch.setattr("app.services.grading.deepseek_json", generate)
    with client.app.state.Session() as db:
        assignment = db.get(Assignment, 1)
        submission = Submission(assignment_id=1, student_id=1, request_id="duplicate-job", code="SELECT 1")
        db.add(submission); db.commit()
        grade_submission(db, submission, assignment, settings)
        reviewed = {**submission.grade, "reviewed": True, "feedback": "教师最终复核"}
        submission.grade = reviewed; db.commit()
        grade_submission(db, submission, assignment, settings)
        assert len(calls) == 1
        assert submission.grade == reviewed
        assert submission.attempts == 1


def test_queue_dispatch_failure_saved_and_retryable(client, student, monkeypatch):
    settings = client.app.state.settings
    settings.task_mode = "celery"
    def unavailable(*args, **kwargs):
        raise ConnectionError("secret redis connection detail")
    monkeypatch.setattr("app.jobs.enqueue_job", unavailable)
    response = client.post("/api/assignments/1/submissions", headers=student, json={"code": "SELECT 1", "request_id": "queue-failed"})
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert "secret" not in response.json()["error"]
    assert response.json()["error"]


def test_local_storage_round_trip_and_traversal_rejection(tmp_path):
    from app.services.storage import store_bytes, load_bytes
    settings = Settings(tmp_path)
    store_bytes(settings, "reports/report.md", "中文报告".encode(), "text/markdown")
    assert load_bytes(settings, "reports/report.md").decode() == "中文报告"
    with pytest.raises(ValueError):
        store_bytes(settings, "../escape", b"bad", "text/plain")


def test_eager_job_with_stale_session_cannot_overwrite_processing_claim(client, monkeypatch):
    from app.services.grading import grade_submission
    settings = client.app.state.settings
    settings.mode = "deepseek"
    calls = []
    with client.app.state.Session() as first, client.app.state.Session() as duplicate:
        assignment = first.get(Assignment, 1)
        item = Submission(assignment_id=1, student_id=1, request_id="overlap", code="SELECT 1")
        first.add(item); first.commit()
        stale = duplicate.get(Submission, item.id)
        def generate(*args):
            calls.append(1)
            grade_submission(duplicate, stale, duplicate.get(Assignment, 1), settings)
            return {"scores": [60, 20, 20], "feedback": "完成", "hints": [], "error_type": ""}
        monkeypatch.setattr("app.services.grading.deepseek_json", generate)
        grade_submission(first, item, assignment, settings)
        assert len(calls) == 1
        assert item.status == "graded"


def test_admin_service_probes_have_timestamp_and_no_secrets(client):
    response = client.get("/api/admin/status", headers=login(client, "admin"))
    assert response.status_code == 200
    assert response.json()["checked_at"]
    assert all(service["checked_at"] for service in response.json()["services"])


def test_subtitle_chunks_retain_real_timestamps(tmp_path):
    from app.services.documents import extract_document
    path = tmp_path / "lesson.srt"
    path.write_text("1\n00:00:01,200 --> 00:00:04,500\n解释事务原子性。\n\n2\n00:00:05,000 --> 00:00:08,000\n说明提交与回滚。", encoding="utf-8")
    records = extract_document(path)
    assert "00:00:01,200" in records[0]["location"]
    assert records[0]["text"] == "解释事务原子性。"


def test_duplicate_material_job_does_not_reparse_or_reindex(client, teacher, monkeypatch):
    from app.routers.materials import process_material
    response = client.post("/api/courses/1/materials", headers=teacher, files={"file": ("lesson.txt", "事务知识".encode(), "text/plain")})
    assert response.json()["status"] == "ready"
    def unexpected(*args, **kwargs):
        pytest.fail("already completed material was parsed twice")
    monkeypatch.setattr("app.routers.materials.extract_document", unexpected)
    with client.app.state.Session() as db:
        material = db.get(Material, response.json()["id"])
        process_material(db, material, client.app.state.settings)
        assert material.status == "ready"


def test_chat_vector_failure_keeps_open_conversation_and_exposes_safe_status(client, student, monkeypatch):
    settings = client.app.state.settings
    settings.retrieval_backend = "vector"
    def unavailable(*args, **kwargs):
        raise GenerationError("课程向量索引服务不可用")
    monkeypatch.setattr("app.services.vectors.search", unavailable)
    response = client.post("/api/courses/1/chat", headers=student, json={"question": "事务"})
    assert response.status_code == 200
    assert response.json()["answer"]["retrieval_status"] == "failed"
    assert response.json()["answer"]["citations"] == []
    assert "课程向量索引服务不可用" not in response.text
    assert len(client.get("/api/courses/1/conversations", headers=student).json()) == 1


def test_real_workflow_obeys_configured_hint_cap(client, student, monkeypatch):
    settings = client.app.state.settings
    settings.mode = "deepseek"
    captured = []
    with client.app.state.Session() as db:
        config = db.get(AgentConfig, 1)
        config.max_hint_level = 1
        db.commit()
    def generate(_settings, system, user):
        captured.append(system)
        return {"content": "依据课程资料 [1]，事务有原子性。"}
    monkeypatch.setattr("app.services.generation.deepseek_json", generate)
    response = client.post("/api/courses/1/chat", headers=student, json={"question": "事务 ACID", "hint_level": 3})
    assert response.status_code == 200, response.text
    assert response.json()["answer"]["hint_level"] == 1
    assert "1/1" in captured[0]


def test_disabling_hint_first_cannot_bypass_maximum_hint_level(client):
    from app.services.grading import demo_grade
    config = SimpleNamespace(persona="助教", prompt="依据资料", max_hint_level=1, hint_first=False)
    with client.app.state.Session() as db:
        assignment = db.get(Assignment, 1)
        grade = demo_grade(assignment, "SELECT * FROM students WHERE email = NULL;", config)
        assert "IS NULL" not in grade["hints"][0]
    text = answer_question(client.app.state.settings, "问题", [{"filename": "课程", "location": "第1页", "text": "原文"}], config, 3, [])
    assert "先想一想" in text


def test_celery_cli_entrypoint_exports_real_app():
    from app.jobs import celery_app
    assert "zhima.run_job" in celery_app.tasks


def test_explicit_recovery_only_releases_targeted_unfinished_job(client):
    from app.jobs import recover_job
    with client.app.state.Session() as db:
        item = Submission(assignment_id=1, student_id=1, request_id="lost-worker", code="SELECT 1", status="grading", attempts=1)
        completed = Submission(assignment_id=1, student_id=1, request_id="saved-review", code="SELECT 1", status="graded", attempts=1,
                               grade={"reviewed": True, "feedback": "教师结果"})
        db.add_all([item, completed]); db.commit()
        assert recover_job(db, "grade", item.id)
        db.refresh(item)
        assert item.status == "failed" and item.attempts == 2
        assert not recover_job(db, "grade", completed.id)
        db.refresh(completed)
        assert completed.grade["reviewed"] is True


def test_api_restart_leaves_celery_pending_and_claimed_rows_untouched(client, monkeypatch):
    from app.main import create_app
    settings = client.app.state.settings
    settings.task_mode = "celery"
    with client.app.state.Session() as db:
        pending = Submission(assignment_id=1, student_id=1, request_id="queued-startup", code="SELECT 1", status="pending")
        grading = Submission(assignment_id=1, student_id=1, request_id="worker-startup", code="SELECT 1", status="grading")
        db.add_all([pending, grading]); db.commit()
        ids = pending.id, grading.id
    monkeypatch.setattr("app.main.Settings", lambda *args: settings)
    second = create_app(settings.data_dir)
    try:
        with second.state.Session() as db:
            assert [db.get(Submission, i).status for i in ids] == ["pending", "grading"]
    finally:
        second.state.engine.dispose()


def test_llamaindex_splitter_preserves_location_without_tokenizer_download(tmp_path, monkeypatch):
    from app.services.documents import extract_document
    import llama_index.core.node_parser.text.sentence as sentence_module
    def forbidden_default_tokenizer():
        pytest.fail("default tokenizer may download resources outside offline deployment")
    monkeypatch.setattr(sentence_module, "get_tokenizer", forbidden_default_tokenizer)
    path = tmp_path / "large.txt"
    path.write_text("事务保证多个数据库操作作为整体完成。" * 100, encoding="utf-8")
    chunks = extract_document(path, use_llamaindex=True)
    assert len(chunks) > 1
    assert all(item["location"] == "第 1 段" and len(item["text"]) <= 700 for item in chunks)


def test_minio_reads_migrated_local_report_when_remote_is_unavailable(tmp_path, monkeypatch):
    from app.services.storage import store_bytes, load_bytes, StorageError
    settings = Settings(tmp_path)
    store_bytes(settings, "reports/historical.md", "历史学习报告".encode(), "text/markdown")
    settings.storage_backend = "minio"
    def unavailable(*args):
        raise ConnectionError("private connection detail")
    monkeypatch.setattr("app.services.storage.minio_client", unavailable)
    assert load_bytes(settings, "reports/historical.md").decode() == "历史学习报告"
    with pytest.raises(StorageError, match="对象存储读取失败"):
        load_bytes(settings, "reports/missing.md")
    with pytest.raises(ValueError, match="无效的存储对象键"):
        load_bytes(settings, "../outside.md")


def test_real_chat_prompt_applies_hint_first_without_bypassing_cap(tmp_path, monkeypatch):
    settings = Settings(tmp_path)
    settings.mode, settings.deepseek_key = "deepseek", "test-private-key"
    prompts = []
    def provider(url, **kwargs):
        prompts.append(kwargs["json"]["messages"][0]["content"])
        return httpx.Response(200, request=httpx.Request("POST", url), json={"choices": [{"message": {"content": '{"content":"课程依据 [1]"}'}}]})
    monkeypatch.setattr(httpx, "post", provider)
    config = SimpleNamespace(persona="助教", prompt="依据资料", max_hint_level=1, hint_first=True)
    citations = [{"chunk_id": 1, "text": "课程原文"}]
    assert "[1]" in answer_question(settings, "问题", citations, config, 3, [])
    config.hint_first = False
    assert "[1]" in answer_question(settings, "问题", citations, config, 3, [])
    assert "优先启发" in prompts[0]
    assert "直接讲解" in prompts[1]
    assert all("1/1" in prompt and "不得提供高于该级别" in prompt for prompt in prompts)


def test_real_grading_applies_hint_first_and_limits_available_hints(client, monkeypatch):
    from app.services.grading import grade_submission
    settings = client.app.state.settings
    settings.mode, settings.deepseek_key = "deepseek", "test-private-key"
    prompts = []
    def provider(url, **kwargs):
        prompts.append(kwargs["json"]["messages"][0]["content"])
        result = {"scores": [60, 20, 20], "feedback": "评语", "hints": ["基础提示", "第二层提示", "完整答案"], "error_type": ""}
        return httpx.Response(200, request=httpx.Request("POST", url), json={"choices": [{"message": {"content": json.dumps(result)}}]})
    monkeypatch.setattr(httpx, "post", provider)
    with client.app.state.Session() as db:
        config = db.get(AgentConfig, 1)
        config.max_hint_level = 2
        grades = []
        for index, first in enumerate((True, False)):
            config.hint_first = first
            submission = Submission(assignment_id=1, student_id=1, request_id=f"hint-policy-{index}", code="SELECT 1")
            db.add(submission); db.commit()
            grade_submission(db, submission, db.get(Assignment, 1), settings)
            assert submission.status == "graded"
            grades.append(submission.grade)
        assert grades[0]["hints"] == ["基础提示", "第二层提示"]
        assert grades[1]["hints"] == ["第二层提示"]
        assert "优先启发" in prompts[0]
        assert "直接讲解" in prompts[1]
        assert all("最高提示层级为 2/3" in prompt for prompt in prompts)
