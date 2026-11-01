"""Install a pinned official community MinIO binary entirely inside this project.

Run with .venv/Scripts/python.exe after loading scripts/env.ps1. This does not
start a server, edit credentials, or change application data.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
VERSION = "RELEASE.2025-04-22T22-12-26Z"
ASSET = f"minio.windows-amd64.{VERSION}.exe"
RELEASE = f"https://github.com/minio/minio/releases/tag/{VERSION}"
SOURCE = f"https://github.com/minio/minio/releases/download/{VERSION}/{ASSET}"
SHA256 = "2ceb3b3d68bdf1c4def9702cb02c5c8adb235197d1c8f2eaad24136833ab9a57"
CHECKSUM_SHA256 = "472c2863cfb43a653b85f156a51bbd59f4a72b81caced3dd779397ad57d888c1"
CACHE = ROOT / ".cache" / "service-downloads" / "minio"
TARGET = ROOT / ".runtime" / "tools" / "minio"


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def download(client, url: str, destination: Path, expected: str) -> None:
    if destination.is_file() and digest(destination) == expected:
        print(f"Verified cached {destination.name}", flush=True)
        return
    partial = destination.with_name(destination.name + ".part")
    for attempt in range(1, 4):
        try:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                with partial.open("wb") as output:
                    for chunk in response.iter_bytes(1024 * 1024):
                        output.write(chunk)
            actual = digest(partial)
            if actual != expected:
                raise ValueError(f"SHA-256 mismatch for {destination.name}: {actual}")
            partial.replace(destination)
            print(f"Downloaded and verified {destination.name}", flush=True)
            return
        except Exception:
            if attempt == 3:
                raise
            print(f"Retrying {destination.name} (attempt {attempt + 1}/3)", flush=True)
            time.sleep(attempt)
        finally:
            partial.unlink(missing_ok=True)


def main() -> None:
    if sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise RuntimeError("This pinned portable binary requires Windows AMD64")
    import httpx

    CACHE.mkdir(parents=True, exist_ok=True)
    TARGET.mkdir(parents=True, exist_ok=True)
    binary = TARGET / "minio.exe"
    checksum_file = CACHE / (ASSET + ".sha256sum")
    with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(120, connect=30)) as client:
        download(client, SOURCE + ".sha256sum", checksum_file, CHECKSUM_SHA256)
        publisher_digest = checksum_file.read_text(encoding="utf-8").split()[0]
        if publisher_digest != SHA256:
            raise ValueError("Publisher checksum differs from the pinned release checksum")
        download(client, SOURCE, binary, publisher_digest)
    probe_env = os.environ.copy()
    probe_env["XDG_CONFIG_HOME"] = str(TARGET / "config")
    probe = subprocess.run([str(binary), "--version"], check=True, capture_output=True,
                           text=True, encoding="utf-8", timeout=30, cwd=ROOT, env=probe_env)
    if VERSION not in probe.stdout or "AGPLv3" not in probe.stdout:
        raise RuntimeError("The downloaded binary did not identify as the expected community release")
    manifest = {
        "product": "MinIO Community Server", "version": VERSION,
        "platform": "windows-amd64", "license": "GNU AGPLv3",
        "release_url": RELEASE, "binary_url": SOURCE,
        "source_commit": "0d7408fc9969caf07de6a8c3a84f9fbb10a6739e",
        "license_url": "https://github.com/minio/minio/blob/"
                       "0d7408fc9969caf07de6a8c3a84f9fbb10a6739e/LICENSE",
        "checksum_url": SOURCE + ".sha256sum", "sha256": digest(binary),
        "checksum_file_sha256": digest(checksum_file),
        "binary_path": ".runtime/tools/minio/minio.exe",
        "size_bytes": binary.stat().st_size,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "version_probe": probe.stdout.strip(),
        "notes": "Official archived community release; no AIStor license or account required. "
                 "Upstream community project is archived and no longer maintained. "
                 "This installer does not start the server or modify application data.",
    }
    (TARGET / "download-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(probe.stdout.strip())
    print(f"Portable MinIO ready: {binary}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"MinIO installation failed ({type(error).__name__}): {error}", file=sys.stderr)
        sys.exit(1)
