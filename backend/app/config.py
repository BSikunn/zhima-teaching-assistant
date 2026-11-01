import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
for _cache_variable, _cache_subdirectory in {
    "NLTK_DATA": "nltk", "TIKTOKEN_CACHE_DIR": "tiktoken", "HF_HOME": "huggingface",
    "TORCH_HOME": "torch", "XDG_CACHE_HOME": "runtime",
}.items():
    os.environ.setdefault(_cache_variable, str(ROOT / ".cache" / _cache_subdirectory))


class Settings:
    def __init__(self, data_dir: Path | None = None):
        self.root = ROOT
        self.data_dir = Path(data_dir or os.getenv("DATA_DIR") or ROOT / "data").resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.uploads = self.data_dir / "uploads"
        self.uploads.mkdir(exist_ok=True)
        self.database_url = os.getenv("DATABASE_URL") if data_dir is None else None
        self.database_url = self.database_url or f"sqlite:///{self.data_dir / 'zhima.db'}"
        secret_file = self.data_dir / ".jwt-secret"
        if not secret_file.exists():
            import secrets
            secret_file.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        self.jwt_secret = os.getenv("JWT_SECRET") or secret_file.read_text(encoding="utf-8").strip()
        isolated = data_dir is not None
        if os.getenv("AI_MODE", "demo") not in {"demo", "deepseek"}:
            raise ValueError("AI_MODE 仅支持 demo 或 deepseek，请检查项目 .env")
        self.mode = "demo" if isolated else os.getenv("AI_MODE", "demo")
        if self.mode not in {"demo", "deepseek"}:
            raise ValueError("AI_MODE 仅支持 demo 或 deepseek，请检查项目 .env")
        self.deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
        self.ai_timeout = float(os.getenv("AI_TIMEOUT", "90"))
        self.task_mode = "eager" if isolated else os.getenv("TASK_MODE", "eager")
        self.redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        self.storage_backend = "local" if isolated else os.getenv("STORAGE_BACKEND", "local")
        self.minio_endpoint = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
        self.minio_access_key = os.getenv("MINIO_ACCESS_KEY", "")
        self.minio_secret_key = os.getenv("MINIO_SECRET_KEY", "")
        self.minio_bucket = os.getenv("MINIO_BUCKET", "zhima")
        self.minio_secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        self.retrieval_backend = "lexical" if isolated else os.getenv("RETRIEVAL_BACKEND", "lexical")
        if self.retrieval_backend == "keyword":
            self.retrieval_backend = "lexical"
        self.index_url = os.getenv("INDEX_URL", "http://127.0.0.1:8767").rstrip("/")
        self.index_token = os.getenv("INDEX_TOKEN", "")
        self.index_timeout = float(os.getenv("INDEX_TIMEOUT", "120"))
        self.embedding_model_path = str(Path(os.getenv("EMBEDDING_MODEL_PATH", str(ROOT / "models" / "bge-small-zh-v1.5"))).resolve())
        self.chroma_dir = self.data_dir / "chroma"
        self.judge0_url = "" if isolated else os.getenv("JUDGE0_URL", "").rstrip("/")
        self.judge0_key = "" if isolated else os.getenv("JUDGE0_KEY") or os.getenv("JUDGE0_API_KEY", "")
        self.judge0_host = "" if isolated else os.getenv("JUDGE0_API_HOST", "")
        if self.task_mode not in {"eager", "celery"}:
            raise ValueError("TASK_MODE 仅支持 eager 或 celery")
        if self.storage_backend not in {"local", "minio"}:
            raise ValueError("STORAGE_BACKEND 仅支持 local 或 minio")
        if self.retrieval_backend not in {"lexical", "vector"}:
            raise ValueError("RETRIEVAL_BACKEND 仅支持 lexical 或 vector")
        self.max_upload_bytes = 20 * 1024 * 1024
        self.web_search_enabled = False if isolated else os.getenv("WEB_SEARCH_ENABLED", "true").lower() == "true"
        self.web_search_provider = os.getenv("WEB_SEARCH_PROVIDER", "ddgs")
        self.web_search_backend = os.getenv("WEB_SEARCH_BACKEND", "yahoo")
        self.web_search_timeout = min(max(float(os.getenv("WEB_SEARCH_TIMEOUT", "10")), 1), 20)
        self.web_search_max_results = min(max(int(os.getenv("WEB_SEARCH_MAX_RESULTS", "3")), 1), 5)
        self.web_search_cache_ttl = 300
