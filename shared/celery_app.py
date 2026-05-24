from celery import Celery
from celery.schedules import crontab

from shared.config import settings

celery_app = Celery("rag_medical")

celery_app.conf.update(
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,  # fair dispatch for long-running tasks
    task_acks_late=True,
)

celery_app.conf.beat_schedule = {
    "fetch-pubmed-daily": {
        "task": "modules.module1_fetch.tasks.fetch_pubmed_batch",
        "schedule": crontab(hour=2, minute=0),
        "kwargs": {"query": "metformin OR diabetes OR renal", "max_results": 500},
    },
    "fetch-europepmc-daily": {
        "task": "modules.module1_fetch.tasks.fetch_europepmc_batch",
        "schedule": crontab(hour=3, minute=0),
        "kwargs": {"query": "clinical pharmacology adverse effects", "max_results": 300},
    },
    "fetch-semanticscholar-daily": {
        "task": "modules.module1_fetch.tasks.fetch_semantic_scholar_batch",
        "schedule": crontab(hour=3, minute=30),
        "kwargs": {"query": "drug mechanism clinical trial", "max_results": 200},
    },
    "fetch-biorxiv-weekly": {
        "task": "modules.module1_fetch.tasks.fetch_biorxiv_batch",
        "schedule": crontab(day_of_week=1, hour=4, minute=0),
    },
}

# Auto-discover tasks from all modules
celery_app.autodiscover_tasks(
    [
        "modules.module1_fetch",
        "modules.module1b_parse",
        "modules.module2_chunk",
        "modules.module3_embed",
        "modules.module4_index",
    ]
)
