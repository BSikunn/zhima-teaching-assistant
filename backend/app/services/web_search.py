"""Search-engine excerpts only: no arbitrary page fetches or model calls."""
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from html import unescape
import ipaddress
from queue import Empty, Queue
import re
from threading import BoundedSemaphore, Lock, Thread
import time
from urllib.parse import urlsplit, urlunsplit

from .retrieval import tokens

_cache = OrderedDict()
_cache_lock = Lock()
_worker_slots = BoundedSemaphore(4)
_ALLOWED_BACKENDS = {"yahoo", "brave", "duckduckgo", "startpage", "mojeek"}


def _plain(value, limit):
    if not isinstance(value, str):
        return ""
    return " ".join(unescape(re.sub(r"<[^>]*>", " ", value[:10000])).split())[:limit]


def build_search_query(question, course_title="", citations=None):
    """Send only a short question, optionally enriched with its relevant course."""
    query = _plain(question, 200)
    title = _plain(course_title, 60)
    terms = tokens(query)
    context_terms = tokens(title)
    for source in (citations or [])[:5]:
        if isinstance(source, dict):
            context_terms.update(tokens(_plain(source.get("text", ""), 2000)))
    overlap = terms & context_terms
    related = bool(terms and overlap and len(overlap) / len(terms) >= 0.28
                   and (len(terms) <= 2 or len(overlap) >= 2))
    if related and title and title.casefold() not in query.casefold():
        query = f"{query} {title}"[:200]
    return query


def _public_url(value):
    if not isinstance(value, str) or len(value) > 2048 or re.search(r"[\s\\\x00-\x1f]", value):
        return ""
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").rstrip(".").lower().encode("idna").decode("ascii")
        if parts.scheme not in {"https", "http"} or parts.username is not None or parts.password is not None:
            return ""
        if parts.port not in {None, 80, 443} or not host or "." not in host:
            return ""
        if host.endswith((".localhost", ".local", ".internal", ".lan", ".home", ".invalid", ".test", ".onion")):
            return ""
        if not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", host):
            return ""
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            return ""
        # Reject numeric/hex dotted IPv4 spellings as well as ordinary IP literals.
        if all(re.fullmatch(r"(?:[0-9]+|0x[0-9a-f]+)", label) for label in host.split(".")):
            return ""
        return urlunsplit((parts.scheme, host, parts.path or "/", parts.query, ""))
    except (ValueError, UnicodeError):
        return ""


def _search_provider(*, query, backend, max_results, timeout):
    # Import lazily so disabled/offline instances never initialize network code.
    from ddgs import DDGS
    from ddgs.engines import ENGINES
    from ddgs.exceptions import DDGSException

    # DDGS falls back to "auto" for an unavailable engine. Refuse that fallback,
    # which would silently add providers beyond the user's configured list.
    if any(name not in ENGINES["text"] for name in backend.split(",")):
        raise ValueError("configured search engine is unavailable")
    try:
        return DDGS(timeout=min(timeout, 5)).text(
            query, backend=backend, max_results=max_results, region="wt-wt", safesearch="moderate")
    except DDGSException as error:
        if str(error) == "No results found.":
            return []
        raise


def _bounded_search(timeout, **arguments):
    # A timed-out caller never waits for executor shutdown. Stuck providers retain
    # their slot until finished, bounding outstanding work across all requests.
    if not _worker_slots.acquire(blocking=False):
        raise RuntimeError("search workers busy")
    completed = Queue(maxsize=1)
    provider = _search_provider

    def run():
        try:
            completed.put((True, provider(timeout=timeout, **arguments)))
        except Exception as error:
            completed.put((False, error))
        finally:
            _worker_slots.release()

    Thread(target=run, daemon=True, name="web-search").start()
    try:
        success, value = completed.get(timeout=timeout)
    except Empty:
        raise TimeoutError("search deadline exceeded") from None
    if not success:
        raise value
    return value


def web_search(settings, question, course_title="", citations=None, history=None):
    """Return genuine, bounded search excerpts and an explicit retrieval status.

    ``history`` is accepted for the chat interface; private conversation and
    document bodies are never included in outbound search requests.
    """
    query = build_search_query(question, course_title, citations)
    provider = getattr(settings, "web_search_provider", "ddgs")
    checked_at = datetime.now(timezone.utc).isoformat()
    result = {"sources": [], "status": "failed", "query": query,
              "provider": provider, "checked_at": checked_at, "detail": ""}
    if not getattr(settings, "web_search_enabled", True):
        return {**result, "status": "disabled", "detail": "联网搜索已关闭"}
    if not query:
        return {**result, "status": "empty", "detail": "没有可搜索的问题"}
    backend = ",".join(dict.fromkeys(
        str(getattr(settings, "web_search_backend", "yahoo")).lower().replace(" ", "").split(",")))
    if provider != "ddgs" or not backend or any(name not in _ALLOWED_BACKENDS for name in backend.split(",")):
        return {**result, "detail": "搜索提供方或后端配置不可用"}
    try:
        limit = min(max(int(getattr(settings, "web_search_max_results", 3)), 1), 5)
        timeout = min(max(float(getattr(settings, "web_search_timeout", 10)), 0.05), 20)
        ttl = min(max(float(getattr(settings, "web_search_cache_ttl", 300)), 0), 3600)
        key = (provider, backend, query, limit)
        with _cache_lock:
            cached = _cache.get(key)
            if cached and time.monotonic() - cached[0] < ttl:
                _cache.move_to_end(key)
                return deepcopy(cached[1])
            _cache.pop(key, None)
        rows = _bounded_search(timeout, query=query, backend=backend, max_results=limit)
        if not isinstance(rows, list):
            raise ValueError("malformed search response")
        seen = set()
        query_terms = tokens(query)
        for row in rows[:30]:
            if not isinstance(row, dict):
                continue
            url = _public_url(row.get("href") or row.get("url"))
            title = _plain(row.get("title"), 200)
            text = _plain(row.get("body") or row.get("text"), 800)
            if not url or url in seen or not title or not text:
                continue
            if query_terms and not query_terms.intersection(tokens(title + " " + text)):
                continue
            seen.add(url)
            result["sources"].append({"source_type": "web", "title": title, "url": url,
                                      "text": text, "location": "网页搜索摘要", "retrieved_at": checked_at})
            if len(result["sources"]) >= limit:
                break
        result["status"] = "success" if result["sources"] else "empty"
        result["detail"] = "已获取网页搜索摘要" if result["sources"] else "没有找到可引用的相关网页摘要"
        if ttl and result["sources"]:
            with _cache_lock:
                _cache[key] = (time.monotonic(), deepcopy(result))
                _cache.move_to_end(key)
                while len(_cache) > 128:
                    _cache.popitem(last=False)
        return result
    except Exception as error:
        # Provider exception messages can contain URLs, proxies or credentials.
        # Never return or log them as chat content; never fabricate search success.
        detail = "联网搜索超时" if isinstance(error, TimeoutError) else "联网搜索暂不可用"
        return {**result, "sources": [], "status": "failed", "detail": detail}
