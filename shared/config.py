from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to the repo root (this file's grandparent) rather than the
# process CWD, so settings load correctly regardless of where the interpreter is
# launched from (e.g. a Jupyter kernel started in notebooks/).
_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # OpenRouter
    openrouter_api_key: str = ""

    # Source APIs
    ncbi_api_key: str = ""
    semantic_scholar_api_key: str = ""
    unpaywall_email: str = ""

    # AWS / S3
    aws_bucket_name: str = "rag-medical-papers"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    # Set to a MinIO endpoint (e.g. http://minio:9000) for local testing; leave
    # empty to use real AWS S3.
    s3_endpoint_url: str = ""

    # PostgreSQL
    database_url: str = "postgresql://rag:changeme@localhost:5432/rag_registry"

    # Celery
    celery_broker_url: str = "amqp://guest:guest@localhost:5672//"
    celery_result_backend: str = "redis://localhost:6379/0"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    # qdrant_api_key: str = ""

    # Grobid
    grobid_url: str = "http://localhost:8070"

    # MLflow
    mlflow_tracking_uri: str = "http://localhost:5000"


settings = Settings()
