"""Single-process Chroma/BGE owner. All model files must already exist locally."""
import os
import secrets
from pathlib import Path
from threading import RLock
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from .config import Settings, ROOT


def persistent_storage_path(directory):
    """Windows HNSW file IO requires an ASCII path; relative paths keep data local."""
    directory = Path(directory).resolve()
    if os.name != "nt":
        return str(directory)
    relative = os.path.relpath(directory, Path.cwd())
    if relative.isascii():
        return relative
    if str(directory).isascii():
        return str(directory)
    raise ValueError("请从项目根目录启动索引，使 Chroma 使用项目内 ASCII 相对路径")


class SearchInput(BaseModel):
    course_id: int = Field(gt=0)
    question: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=3, ge=1, le=50)


class MaterialInput(BaseModel):
    course_id: int = Field(gt=0)
    material_id: int = Field(gt=0)


class ChunkInput(BaseModel):
    chunk_id: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=100000)
    location: str = Field(max_length=100)


class UpsertInput(MaterialInput):
    chunks: list[ChunkInput] = Field(max_length=10000)


def create_app():
    settings = Settings()
    app = FastAPI(title="智码课程索引", docs_url=None, redoc_url=None)
    lock = RLock()
    state = {}

    def initialize():
        with lock:
            if state:
                return state["collection"], state["model"]
            os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))
            os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
            if not Path(settings.embedding_model_path).is_dir():
                raise HTTPException(503, "项目内 BGE 模型尚未准备好")
            try:
                import chromadb
                from chromadb.config import Settings as ChromaSettings
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer(settings.embedding_model_path, local_files_only=True,
                    cache_folder=str(ROOT / ".cache" / "huggingface"), trust_remote_code=False)
                client = chromadb.PersistentClient(path=persistent_storage_path(settings.chroma_dir),
                    settings=ChromaSettings(anonymized_telemetry=False))
                collection = client.get_or_create_collection("zhima_knowledge", metadata={"hnsw:space": "cosine"})
                state.update(client=client, collection=collection, model=model)
                return collection, model
            except Exception:
                raise HTTPException(503, "BGE/Chroma 初始化失败，请检查项目模型和依赖") from None

    def authenticated(authorization: str = Header(default=""), x_index_token: str = Header(default="")):
        token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else x_index_token
        if not settings.index_token:
            raise HTTPException(503, "索引服务尚未配置访问令牌")
        if not secrets.compare_digest(token, settings.index_token):
            raise HTTPException(401, "索引访问令牌无效")

    @app.get("/health")
    def health():
        collection, model = initialize()
        with lock:
            count = collection.count()
            dimensions = model.get_sentence_embedding_dimension()
        return {"status": "ok", "backend": "chroma-bge", "chunks": count, "dimensions": dimensions}

    @app.post("/materials/upsert", dependencies=[Depends(authenticated)])
    def upsert(body: UpsertInput):
        collection, model = initialize()
        if len({item.chunk_id for item in body.chunks}) != len(body.chunks):
            raise HTTPException(422, "知识块编号重复")
        with lock:
            embeddings = model.encode([item.text for item in body.chunks], normalize_embeddings=True, show_progress_bar=False).tolist() if body.chunks else []
            collection.delete(where={"$and": [{"course_id": body.course_id}, {"material_id": body.material_id}]})
            for offset in range(0, len(body.chunks), 128):
                items = body.chunks[offset:offset + 128]
                collection.upsert(ids=[str(item.chunk_id) for item in items],
                    embeddings=embeddings[offset:offset + 128], documents=[item.text for item in items],
                    metadatas=[{"course_id": body.course_id, "material_id": body.material_id,
                                "chunk_id": item.chunk_id, "location": item.location} for item in items])
        return {"ok": True, "chunks": len(body.chunks)}

    @app.post("/materials/delete", dependencies=[Depends(authenticated)])
    def delete(body: MaterialInput):
        collection, _ = initialize()
        with lock:
            collection.delete(where={"$and": [{"course_id": body.course_id}, {"material_id": body.material_id}]})
        return {"ok": True}

    @app.post("/search", dependencies=[Depends(authenticated)])
    def search(body: SearchInput):
        collection, model = initialize()
        with lock:
            if collection.count() == 0:
                return {"matches": []}
            vector = model.encode(["为这个句子生成表示以用于检索相关文章：" + body.question], normalize_embeddings=True, show_progress_bar=False).tolist()
            result = collection.query(query_embeddings=vector, where={"course_id": body.course_id},
                                      n_results=min(body.limit, collection.count()), include=["distances", "metadatas"])
        matches = []
        for metadata, distance in zip(result["metadatas"][0], result["distances"][0]):
            score = 1.0 - distance
            if score >= 0.35:
                matches.append({"chunk_id": metadata["chunk_id"], "score": round(score, 6)})
        return {"matches": matches}

    return app


app = create_app()
