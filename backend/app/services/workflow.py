"""Course retrieval and real web evidence enhance an open LlamaIndex chat flow."""
import asyncio
from .generation import GenerationError, generate_chat_answer
from .retrieval import retrieve
from .web_search import web_search
from ..models import Course


def _intent(question):
    if any(word in question.lower() for word in ("报错", "错误", "debug", "exception")):
        return "code_debugging"
    if any(word in question for word in ("提示", "怎么做", "下一步")):
        return "guided_hint"
    return "open_question"


def run_course_workflow(db, settings, course_id, question, config, hint_level, history, enable_web=None):
    level = min(max(1, hint_level), config.max_hint_level)
    bounded_history = [{"role": item["role"], "content": item["content"][:4000]} for item in history[-6:]]

    def collect():
        try:
            course_sources = retrieve(db, course_id, question, settings=settings)
            retrieval_status = "ready" if course_sources else "empty"
        except GenerationError:
            course_sources, retrieval_status = [], "failed"
        course = db.get(Course, course_id)
        enabled = getattr(settings, "web_search_enabled", False) and enable_web is not False and settings.mode == "deepseek"
        if enabled:
            try:
                search = web_search(settings, question, course_title=course.title if course else "",
                                    citations=course_sources, history=bounded_history)
            except Exception:
                search = {"sources": [], "status": "failed", "detail": "联网检索暂不可用，本次可由模型自身知识回答"}
        else:
            search = {"sources": [], "status": "disabled", "detail": "本次未启用联网检索"}
        sources = [{**s, "source_type": "course"} for s in course_sources] + list(search.get("sources", []))
        return sources, {k: v for k, v in search.items() if k != "sources"}, retrieval_status

    def generate(sources, search, retrieval_status):
        result = generate_chat_answer(settings, question, sources, config, level, bounded_history)
        return {**result, "hint_level": level, "intent": _intent(question),
                "web_search": search, "retrieval_status": retrieval_status}

    if settings.mode == "demo" and settings.retrieval_backend == "lexical":
        return generate(*collect())
    try:
        from workflows import Workflow, step
        from workflows.events import Event, StartEvent, StopEvent

        class IntentEvent(Event):
            intent: str

        class ContextEvent(Event):
            sources: list
            search: dict
            retrieval_status: str

        class CourseWorkflow(Workflow):
            @step
            async def classify(self, ev: StartEvent) -> IntentEvent:
                return IntentEvent(intent=_intent(question))

            @step
            async def fetch_context(self, ev: IntentEvent) -> ContextEvent:
                sources, search, status = collect()
                return ContextEvent(sources=sources, search=search, retrieval_status=status)

            @step
            async def answer(self, ev: ContextEvent) -> StopEvent:
                result = await asyncio.to_thread(generate, ev.sources, ev.search, ev.retrieval_status)
                return StopEvent(result=result)

        async def execute():
            flow = CourseWorkflow(timeout=settings.ai_timeout + settings.index_timeout + getattr(settings, "web_search_timeout", 10) + 10)
            return await flow.run()
        return asyncio.run(execute())
    except Exception as error:
        cause = error
        while cause is not None:
            if isinstance(cause, GenerationError):
                raise cause
            cause = cause.__cause__
        raise GenerationError("问答处理暂时失败，请稍后重试") from None
