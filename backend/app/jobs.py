"""Business IDs are the only task payload. Claims live in each business handler."""
from functools import lru_cache
from .config import Settings
from .db import make_database
from .models import Material, Submission, PracticeSession, Report, Assignment

KINDS = {"material": Material, "grade": Submission, "practice_generate": PracticeSession,
         "practice_grade": PracticeSession, "report": Report}
PENDING = {"material": "pending", "grade": "pending", "practice_generate": "pending",
           "practice_grade": "pending_grade", "report": "pending"}


def run_job(factory, settings, kind, object_id):
    if kind not in KINDS:
        raise ValueError("未知任务类型")
    with factory() as db:
        item = db.get(KINDS[kind], object_id)
        if item is None:
            return
        if kind == "material":
            from .routers.materials import process_material
            process_material(db, item, settings)
        elif kind == "grade":
            from .services.grading import grade_submission
            grade_submission(db, item, db.get(Assignment, item.assignment_id), settings)
        elif kind == "practice_generate":
            from .services.practice import process_practice
            process_practice(db, item, settings)
        elif kind == "practice_grade":
            from .services.practice import grade_practice
            grade_practice(db, item, settings)
        else:
            from .services.reporting import process_report
            process_report(db, item, settings)


@lru_cache(maxsize=4)
def get_celery_app(redis_url):
    from celery import Celery
    app = Celery("zhima", broker=redis_url, backend=redis_url)
    app.conf.update(task_serializer="json", accept_content=["json"], result_serializer="json",
        timezone="Asia/Shanghai", enable_utc=True, broker_connection_retry_on_startup=True,
        task_acks_late=True, worker_prefetch_multiplier=1, task_reject_on_worker_lost=True,
        task_publish_retry=False, broker_connection_timeout=3,
        broker_transport_options={"socket_connect_timeout": 3, "socket_timeout": 3}, result_expires=3600)
    app.task(name="zhima.run_job", ignore_result=True)(_worker_job)
    return app


def _worker_job(kind, object_id):
    settings = Settings()
    engine, factory = make_database(settings.database_url)
    try:
        run_job(factory, settings, kind, object_id)
    finally:
        engine.dispose()


def create_celery_app():
    return get_celery_app(Settings().redis_url)


def __getattr__(name):
    # Celery's CLI requires an app object; resolve it lazily for the demo executor.
    if name == "celery_app":
        return create_celery_app()
    raise AttributeError(name)


def enqueue_job(settings, kind, object_id):
    return get_celery_app(settings.redis_url).send_task("zhima.run_job", args=[kind, object_id])


def dispatch_job(request, kind, object_id):
    if kind not in KINDS:
        raise ValueError("未知任务类型")
    settings = request.app.state.settings
    if settings.task_mode == "eager":
        run_job(request.app.state.Session, settings, kind, object_id)
        return True
    try:
        enqueue_job(settings, kind, object_id)
        return True
    except Exception:
        # A concurrent worker may already own the row. Never overwrite that claim.
        with request.app.state.Session() as db:
            db.query(KINDS[kind]).filter_by(id=object_id, status=PENDING[kind]).update(
                {"status": "failed", "error": "任务队列投递失败，请检查 Redis/Celery 后重试"}, synchronize_session=False)
            db.commit()
        return False


def recover_eager_jobs(db):
    # Only the synchronous development executor is known to have stopped here.
    # Celery rows survive API restarts and must remain owned by their worker.
    states = {Material: ["pending", "processing"], Submission: ["pending", "grading"],
              PracticeSession: ["pending", "pending_grade", "generating", "grading"], Report: ["pending", "generating"]}
    for model, statuses in states.items():
        db.query(model).filter(model.status.in_(statuses)).update(
            {"status": "failed", "error": "本地服务重启中断了任务，请重试"}, synchronize_session=False)
    db.commit()


def recover_job(db, kind, object_id):
    """Operator recovery after workers stop; never release a live worker's claim."""
    model = KINDS[kind]
    active = {"material": ["pending", "processing"], "grade": ["pending", "grading"],
              "practice_generate": ["pending", "generating"], "practice_grade": ["pending_grade", "grading"],
              "report": ["pending", "generating"]}[kind]
    values = {"status": "failed", "error": "任务已由管理员恢复，请检查原任务及模型调用结果后重试"}
    if hasattr(model, "attempts"):
        values["attempts"] = model.attempts + 1
    count = db.query(model).filter(model.id == object_id, model.status.in_(active)).update(values, synchronize_session=False)
    db.commit()
    return bool(count)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Stopped-worker task recovery; does not call AI or enqueue jobs")
    parser.add_argument("action", choices=["recover"])
    parser.add_argument("kind", choices=list(KINDS))
    parser.add_argument("object_id", type=int)
    parser.add_argument("--workers-stopped", action="store_true", required=True,
                        help="Confirm all workers are stopped before releasing their claim")
    args = parser.parse_args()
    settings = Settings()
    engine, factory = make_database(settings.database_url)
    try:
        with factory() as db:
            print({"recovered": recover_job(db, args.kind, args.object_id)})
    finally:
        engine.dispose()
