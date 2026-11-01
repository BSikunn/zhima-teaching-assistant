"""Copy and verify existing local uploads/reports before enabling MinIO."""
from hashlib import sha256
from io import BytesIO
import mimetypes
from pathlib import Path
from .storage import minio_client, _key


def _sources(settings):
    sources = []
    for directory, prefix in [(settings.uploads, "uploads/"), (settings.data_dir / "objects", "")]:
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or ".health" in path.relative_to(directory).parts:
                continue
            if not path.resolve().is_relative_to(directory.resolve()):
                raise ValueError("本地对象路径越界")
            sources.append((_key(prefix + path.relative_to(directory).as_posix()), path))
    return sources


def _target(settings):
    return {"endpoint": settings.minio_endpoint, "secure": settings.minio_secure, "bucket": settings.minio_bucket}


def migrate_local_objects(settings, client=None):
    if settings.storage_backend != "minio":
        raise ValueError("迁移目标必须是 MinIO")
    client = client or minio_client(settings)
    sources = _sources(settings)
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)
    report = {"version": 1, "target": _target(settings), "source_dir": str(settings.data_dir.resolve()),
              "copied": 0, "existing": 0, "verified": 0, "objects": []}
    for key, path in sources:
        content = path.read_bytes()
        checksum = sha256(content).hexdigest()
        try:
            response = client.get_object(settings.minio_bucket, key)
            try:
                current = response.read()
            finally:
                response.close()
                response.release_conn()
        except Exception as error:
            if getattr(error, "code", "") not in {"NoSuchKey", "NoSuchObject"}:
                raise RuntimeError("MinIO 读取失败；迁移停止且保留所有本地原件") from None
            current = None
        if current is not None:
            if sha256(current).hexdigest() != checksum:
                raise ValueError(f"目标对象内容冲突，未覆盖: {key}")
            report["existing"] += 1
        else:
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            client.put_object(settings.minio_bucket, key, BytesIO(content), len(content), content_type=content_type)
            report["copied"] += 1
        verified = client.get_object(settings.minio_bucket, key)
        try:
            if sha256(verified.read()).hexdigest() != checksum:
                raise ValueError("对象存储写入后校验不一致")
        finally:
            verified.close()
            verified.release_conn()
        report["verified"] += 1
        report["objects"].append({"key": key, "bytes": len(content), "sha256": checksum})
    return report


def validate_migration_receipt(settings, receipt, client=None):
    """Read-only activation gate: bind the target and recheck current local/remote bytes."""
    if (receipt.get("version") != 1 or receipt.get("target") != _target(settings)
            or Path(receipt.get("source_dir", "")).resolve() != settings.data_dir.resolve()):
        raise ValueError("迁移目标或来源目录已变化，请重新迁移并校验")
    objects = receipt.get("objects")
    if (not isinstance(objects, list) or receipt.get("verified") != len(objects)
            or receipt.get("verified") != receipt.get("copied", 0) + receipt.get("existing", 0)):
        raise ValueError("文件迁移回执不完整")
    recorded = {item["key"]: (item["bytes"], item["sha256"]) for item in objects}
    current = {key: (path.stat().st_size, sha256(path.read_bytes()).hexdigest()) for key, path in _sources(settings)}
    if len(recorded) != len(objects) or current != recorded:
        raise ValueError("本地文件已变化，请重新迁移并校验；未激活新配置")
    client = client or minio_client(settings)
    if not client.bucket_exists(settings.minio_bucket):
        raise ValueError("迁移目标存储桶不存在")
    for key, (size, checksum) in recorded.items():
        try:
            response = client.get_object(settings.minio_bucket, key)
            try:
                content = response.read()
            finally:
                response.close()
                response.release_conn()
        except Exception:
            raise ValueError("目标文件缺失或无法读取，未激活新配置") from None
        if len(content) != size or sha256(content).hexdigest() != checksum:
            raise ValueError("目标文件内容已变化，未激活新配置")
    return True
