"""Private object storage; object keys never become arbitrary filesystem paths."""
from io import BytesIO
from pathlib import PurePosixPath
import os
import uuid


class StorageError(Exception):
    pass


def _key(key):
    path = PurePosixPath(key)
    if not key or path.is_absolute() or "\\" in key or ":" in key or any(p in {".", ".."} for p in key.split("/")):
        raise ValueError("无效的存储对象键")
    return str(path)


def _path(settings, key):
    # Keep compatibility with the original seeded upload directory.
    base = settings.uploads if key.startswith("uploads/") else settings.data_dir / "objects"
    relative = key.removeprefix("uploads/") if key.startswith("uploads/") else key
    target = (base / relative).resolve()
    if not target.is_relative_to(base.resolve()):
        raise ValueError("无效的存储对象键")
    return target


def minio_client(settings):
    from minio import Minio
    from urllib3 import PoolManager, Timeout
    endpoint = settings.minio_endpoint.removeprefix("https://").removeprefix("http://").rstrip("/")
    return Minio(endpoint, access_key=settings.minio_access_key, secret_key=settings.minio_secret_key,
                 secure=settings.minio_secure, http_client=PoolManager(timeout=Timeout(connect=3, read=5), retries=False))


def store_bytes(settings, key, content, content_type="application/octet-stream"):
    key = _key(key)
    if settings.storage_backend == "local":
        target = _path(settings, key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            temporary.write_bytes(content)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return key
    try:
        client = minio_client(settings)
        if not client.bucket_exists(settings.minio_bucket):
            client.make_bucket(settings.minio_bucket)
        client.put_object(settings.minio_bucket, key, BytesIO(content), len(content), content_type=content_type)
        return key
    except Exception:
        raise StorageError("对象存储写入失败，请检查 MinIO 服务与访问权限") from None


def load_bytes(settings, key):
    key = _key(key)
    if settings.storage_backend == "local":
        return _path(settings, key).read_bytes()
    try:
        response = minio_client(settings).get_object(settings.minio_bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
    except Exception:
        # Preserved uploads and reports may predate MinIO. The validated local
        # object path is a compatibility source, never a newly invented result.
        if _path(settings, key).is_file():
            return _path(settings, key).read_bytes()
        raise StorageError("对象存储读取失败，请检查 MinIO 服务与文件是否存在") from None
