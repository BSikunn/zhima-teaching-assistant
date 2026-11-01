"""The network boundary is replaced; query and result processing stay real."""
from types import SimpleNamespace
import time

import pytest

from app.services import web_search as search


def settings(**changes):
    values = dict(web_search_enabled=True, web_search_provider="ddgs",
                  web_search_backend="brave", web_search_timeout=1,
                  web_search_max_results=3, web_search_cache_ttl=300)
    values.update(changes)
    return SimpleNamespace(**values)


@pytest.fixture(autouse=True)
def clear_cache():
    search._cache.clear()
    yield
    search._cache.clear()


def row(url="https://docs.python.org/3/tutorial/", **changes):
    result = {"title": "<b>Python</b> Tutorial", "href": url,
              "body": "Actual search engine excerpt about Python."}
    result.update(changes)
    return result


def test_returns_deduplicated_bounded_web_sources(monkeypatch):
    monkeypatch.setattr(search, "_search_provider", lambda **kw: [
        row(body="<b>Excerpt</b> " + "x" * 1000),
        row("https://docs.python.org/3/tutorial/#section"),
        row("https://www.python.org/"),
    ])
    result = search.web_search(settings(web_search_max_results=1), "Python tutorial")
    assert result["status"] == "success"
    assert result["query"] == "Python tutorial"
    assert result["provider"] == "ddgs"
    assert len(result["sources"]) == 1
    source = result["sources"][0]
    assert source["source_type"] == "web"
    assert source["title"] == "Python Tutorial"
    assert source["url"] == "https://docs.python.org/3/tutorial/"
    assert source["text"].startswith("Excerpt ")
    assert len(source["text"]) <= 800
    assert source["location"] == "网页搜索摘要"
    assert source["retrieved_at"] == result["checked_at"]


def test_empty_results_do_not_invent_sources(monkeypatch):
    monkeypatch.setattr(search, "_search_provider", lambda **kw: [])
    result = search.web_search(settings(), "unmatched query")
    assert result["status"] == "empty"
    assert result["sources"] == []


def test_empty_search_is_not_sticky_after_transient_no_results(monkeypatch):
    results = iter([[], [row()]])
    monkeypatch.setattr(search, "_search_provider", lambda **kw: next(results))
    assert search.web_search(settings(), "Python tutorial")["status"] == "empty"
    assert search.web_search(settings(), "Python tutorial")["status"] == "success"


def test_provider_failure_is_explicit_without_exception_secrets(monkeypatch):
    def fail(**kw):
        raise RuntimeError("provider failure api_key=DO_NOT_LEAK")
    monkeypatch.setattr(search, "_search_provider", fail)
    result = search.web_search(settings(), "Python tutorial")
    assert result["status"] == "failed"
    assert result["sources"] == []
    assert "DO_NOT_LEAK" not in result["detail"]


def test_failures_are_retried_instead_of_cached(monkeypatch):
    responses = iter([RuntimeError("transient"), [row()]])
    def provider(**kw):
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response
    monkeypatch.setattr(search, "_search_provider", provider)
    assert search.web_search(settings(), "Python tutorial")["status"] == "failed"
    assert search.web_search(settings(), "Python tutorial")["status"] == "success"


def test_cache_isolated_by_query_backend_and_limit_and_returns_copies(monkeypatch):
    def provider(**kw):
        return [row(body=kw["query"]), row("https://www.python.org/")]
    monkeypatch.setattr(search, "_search_provider", provider)
    first = search.web_search(settings(), "First query")
    first["sources"][0]["text"] = "corrupted consumer data"
    def should_be_cached(**kw):
        raise RuntimeError("unexpected network request")
    monkeypatch.setattr(search, "_search_provider", should_be_cached)
    assert search.web_search(settings(), "First query")["sources"][0]["text"] == "First query"
    assert search.web_search(settings(), "Other query")["status"] == "failed"
    assert search.web_search(settings(web_search_backend="bing"), "First query")["status"] == "failed"
    assert search.web_search(settings(web_search_max_results=1), "First query")["status"] == "failed"


def test_expired_cache_is_refreshed(monkeypatch):
    monkeypatch.setattr(search, "_search_provider", lambda **kw: [row(body="first")])
    assert search.web_search(settings(), "Python")["sources"][0]["text"] == "first"
    monkeypatch.setattr(search, "_search_provider", lambda **kw: [row(body="fresh")])
    assert search.web_search(settings(web_search_cache_ttl=0), "Python")["sources"][0]["text"] == "fresh"


@pytest.mark.parametrize("url", [
    "javascript:alert(1)", "file:///secret", "http://127.0.0.1/data",
    "https://[::1]/", "https://192.168.1.1/", "http://2130706433/",
    "http://localhost/", "https://service.internal/", "https://printer.local/",
    "https://admin:secret@example.com/", "https://example.com:9999/",
    "https://example.com\\@localhost/", "https://example.com\n.evil.org/",
])
def test_rejects_nonpublic_or_unsafe_result_urls(monkeypatch, url):
    monkeypatch.setattr(search, "_search_provider", lambda **kw: [row(url)])
    result = search.web_search(settings(), "query")
    assert result["sources"] == []
    assert result["status"] == "empty"


def test_disabled_search_never_uses_network(monkeypatch):
    monkeypatch.setattr(search, "_search_provider", lambda **kw: pytest.fail("network disabled"))
    assert search.web_search(settings(web_search_enabled=False), "query")["status"] == "disabled"


def test_course_title_only_enriches_relevant_questions():
    citations = [{"text": "Python 变量与赋值的知识点", "filename": "lecture.md"}]
    assert search.build_search_query("什么是变量？", "Python程序设计", citations) == "什么是变量？ Python程序设计"
    assert search.build_search_query("北京天气怎么样？", "Python程序设计", citations) == "北京天气怎么样？"
    assert search.build_search_query("Python列表推导式", "Python", []) == "Python列表推导式"


def test_query_limits_do_not_send_document_or_history_content(monkeypatch):
    observed = []
    def provider(**kw):
        observed.append(kw["query"])
        return [row()]
    monkeypatch.setattr(search, "_search_provider", provider)
    result = search.web_search(settings(), "天气 " * 200, "编程课程",
                               [{"text": "PRIVATE_DOCUMENT"}], [{"content": "PRIVATE_HISTORY"}])
    assert len(result["query"]) <= 200
    assert observed == [result["query"]]
    assert "PRIVATE_" not in result["query"]


def test_total_timeout_returns_without_waiting_for_provider(monkeypatch):
    def slow(**kw):
        time.sleep(0.5)
        return [row()]
    monkeypatch.setattr(search, "_search_provider", slow)
    start = time.monotonic()
    result = search.web_search(settings(web_search_timeout=0.05), "slow query")
    assert time.monotonic() - start < 0.3
    assert result["status"] == "failed"
    assert result["sources"] == []


def test_unsupported_backend_fails_without_network(monkeypatch):
    monkeypatch.setattr(search, "_search_provider", lambda **kw: pytest.fail("unsafe backend"))
    assert search.web_search(settings(web_search_backend="auto"), "query")["status"] == "failed"


def test_unrelated_search_rows_are_not_presented_as_evidence(monkeypatch):
    monkeypatch.setattr(search, "_search_provider", lambda **kw: [row()])
    result = search.web_search(settings(), "故宫博物院开放时间")
    assert result["status"] == "empty"
    assert result["sources"] == []


def test_duplicate_fragments_are_collapsed(monkeypatch):
    monkeypatch.setattr(search, "_search_provider", lambda **kw: [
        row(), row("https://docs.python.org/3/tutorial/#lists"), row("https://www.python.org/")])
    result = search.web_search(settings(), "Python tutorial")
    assert [source["url"] for source in result["sources"]] == [
        "https://docs.python.org/3/tutorial/", "https://www.python.org/"]


def test_library_unavailable_engine_cannot_fall_back_to_auto(monkeypatch):
    import ddgs
    from ddgs.engines import ENGINES
    monkeypatch.setitem(ENGINES, "text", {})
    contacted = []
    monkeypatch.setattr(ddgs, "DDGS", lambda **kw: contacted.append(kw))
    with pytest.raises(ValueError):
        search._search_provider(query="Python", backend="yahoo", max_results=3, timeout=1)
    assert contacted == []


def test_cache_cannot_grow_without_bound(monkeypatch):
    monkeypatch.setattr(search, "_search_provider", lambda **kw: [row(body=kw["query"])])
    for index in range(140):
        search.web_search(settings(), f"Python item {index}")
    assert len(search._cache) <= 128
