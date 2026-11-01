from types import SimpleNamespace
import pytest

from app.models import Message
from app.services.generation import GenerationError


def no_web(*args, **kwargs):
    return {"sources": [], "status": "failed", "query": "问题", "provider": "test", "detail": "搜索暂不可用"}


def test_unrelated_question_still_calls_model_and_persists_basis(client, student, monkeypatch):
    client.app.state.settings.mode = "deepseek"
    client.app.state.settings.web_search_enabled = True
    monkeypatch.setattr("app.services.workflow.retrieve", lambda *a, **k: [])
    monkeypatch.setattr("app.services.workflow.web_search", no_web)
    calls = []
    def model(settings, system, question):
        calls.append(question)
        return {"content": "法国的首都是巴黎。", "answer_scope": "general"}
    monkeypatch.setattr("app.services.generation.deepseek_json", model)
    result = client.post("/api/courses/1/chat", headers=student, json={"question": "法国首都是哪里"})
    assert result.status_code == 200, result.text
    data = result.json()
    answer = data["answer"]
    assert calls and "巴黎" in answer["content"]
    assert "没有找到足够依据" not in answer["content"]
    assert answer["citations"] == [] and answer["answer_basis"] == "model"
    assert answer["web_search"]["status"] == "failed"
    history = client.get(f"/api/conversations/{data['conversation_id']}", headers=student).json()
    assert history["messages"][-1]["answer_basis"] == "model"
    assert history["messages"][-1]["web_search"]["status"] == "failed"


def test_course_and_web_sources_keep_distinct_verified_numbers(client, student, monkeypatch):
    settings = client.app.state.settings
    settings.mode, settings.web_search_enabled = "deepseek", True
    course_source = {"chunk_id": 1, "material_id": 1, "filename": "课程讲义.md", "location": "第1段", "text": "NULL 使用 IS NULL 判断。"}
    monkeypatch.setattr("app.services.workflow.retrieve", lambda *a, **k: [course_source])
    monkeypatch.setattr("app.services.workflow.web_search", lambda *a, **k: {
        "sources": [{"source_type": "web", "title": "MySQL参考手册", "url": "https://dev.mysql.com/doc/refman/8.0/en/working-with-null.html", "text": "NULL comparisons", "retrieved_at": "2026-10-31T12:00:00+08:00"}],
        "status": "success", "query": "MySQL NULL", "provider": "test", "detail": "找到1条搜索摘要"})
    monkeypatch.setattr("app.services.generation.deepseek_json", lambda *a: {"content": "使用 IS NULL [1]；官方手册也说明这一用法 [2]。", "answer_scope": "course"})
    response = client.post("/api/courses/1/chat", headers=student, json={"question": "如何判断SQL空值"})
    assert response.status_code == 200, response.text
    answer = response.json()["answer"]
    assert answer["answer_basis"] == "course+web"
    assert [x["source_type"] for x in answer["citations"]] == ["course", "web"]
    assert [x["number"] for x in answer["citations"]] == [1, 2]
    assert answer["citations"][1]["url"].startswith("https://dev.mysql.com/")


def test_index_failure_and_disabled_web_do_not_block_general_answer(client, student, monkeypatch):
    settings = client.app.state.settings
    settings.mode, settings.web_search_enabled = "deepseek", True
    def broken(*a, **k):
        raise GenerationError("private backend error")
    monkeypatch.setattr("app.services.workflow.retrieve", broken)
    def must_not_search(*a, **k):
        pytest.fail("request disabled web search")
    monkeypatch.setattr("app.services.workflow.web_search", must_not_search)
    monkeypatch.setattr("app.services.generation.deepseek_json", lambda *a: {"content": "列表保持顺序，字典按键保存值。", "answer_scope": "general"})
    response = client.post("/api/courses/2/chat", headers=student, json={"question": "列表和字典的区别", "web_search": False})
    assert response.status_code == 200, response.text
    answer = response.json()["answer"]
    assert answer["retrieval_status"] == "failed" and answer["web_search"]["status"] == "disabled"
    assert "private" not in response.text


def test_fabricated_citation_in_general_answer_is_rejected(client, student, monkeypatch):
    client.app.state.settings.mode = "deepseek"
    client.app.state.settings.web_search_enabled = True
    monkeypatch.setattr("app.services.workflow.retrieve", lambda *a, **k: [])
    monkeypatch.setattr("app.services.workflow.web_search", no_web)
    monkeypatch.setattr("app.services.generation.deepseek_json", lambda *a: {"content": "这是答案 [99]", "answer_scope": "general"})
    response = client.post("/api/courses/1/chat", headers=student, json={"question": "课程外问题"})
    assert response.status_code == 502
    with client.app.state.Session() as db:
        assert db.query(Message).count() == 0


def test_unused_sources_are_not_displayed_and_original_numbers_survive(tmp_path, monkeypatch):
    from app.config import Settings
    from app.services.generation import generate_chat_answer
    settings = Settings(tmp_path)
    settings.mode = "deepseek"
    config = SimpleNamespace(persona="课程助教", prompt="课程内启发", max_hint_level=1, hint_first=True)
    sources = [{"source_type": "course", "filename": "课程", "text": "SQL"},
               {"source_type": "web", "title": "法国", "url": "https://example.org/france", "text": "巴黎是法国首都。"}]
    monkeypatch.setattr("app.services.generation.deepseek_json", lambda *a: {"content": "法国首都是巴黎 [2]。", "answer_scope": "general"})
    result = generate_chat_answer(settings, "法国首都", sources, config, 1, [])
    assert result["answer_basis"] == "web"
    assert len(result["citations"]) == 1 and result["citations"][0]["number"] == 2


@pytest.mark.parametrize("content", [
    "Python 示例：\n```python\nitems = [10, 20]\nprint(items[0])\n```",
    "数组取值可以写成 `items[1]`，首项下标是0。",
    "数组下标写法 items[0] 和 matrix[1][2] 不代表文献来源。",
])
def test_array_indices_are_not_treated_as_citations(tmp_path, monkeypatch, content):
    from app.config import Settings
    from app.services.generation import generate_chat_answer
    settings = Settings(tmp_path)
    settings.mode = "deepseek"
    config = SimpleNamespace(persona="课程助教", prompt="依据资料", max_hint_level=1, hint_first=True)
    monkeypatch.setattr("app.services.generation.deepseek_json", lambda *a: {"content": content})
    result = generate_chat_answer(settings, "数组怎么取值", [], config, 1, [])
    assert result["content"] == content and result["citations"] == []


def test_citation_parser_ignores_code_but_preserves_real_evidence(tmp_path, monkeypatch):
    from app.config import Settings
    from app.services.generation import generate_chat_answer
    settings = Settings(tmp_path)
    settings.mode = "deepseek"
    config = SimpleNamespace(persona="课程助教", prompt="依据资料", max_hint_level=1, hint_first=True)
    monkeypatch.setattr("app.services.generation.deepseek_json", lambda *a: {"content": "列表索引从0开始[1]。例子：`items[99]` 可能越界。"})
    result = generate_chat_answer(settings, "列表下标", [{"filename": "讲义", "text": "索引从0开始"}], config, 1, [])
    assert len(result["citations"]) == 1 and result["citations"][0]["number"] == 1
