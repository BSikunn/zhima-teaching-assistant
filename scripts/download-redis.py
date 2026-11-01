"""Pinned community Redis 7 Windows build, project-local and checksum verified."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "7.4.11"
NAME = f"Redis-{VERSION}-Windows-x64-cygwin.zip"
URL = f"https://github.com/redis-windows/redis-windows/releases/download/{VERSION}/{NAME}"
SHA256 = "835999942bbef27e2b01f4a36955522cf19fff6511e67bbfe3fee322f6586705"


def main():
    import httpx
    cache = ROOT / ".cache" / "downloads"
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / NAME
    if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        partial = archive.with_suffix(".part")
        with httpx.stream("GET", URL, follow_redirects=True, timeout=60) as response:
            response.raise_for_status()
            with partial.open("wb") as output:
                for data in response.iter_bytes(1024 * 1024):
                    output.write(data)
        if hashlib.sha256(partial.read_bytes()).hexdigest() != SHA256:
            raise ValueError("Redis download checksum mismatch")
        partial.replace(archive)
    destination = ROOT / ".runtime" / "tools" / "redis"
    destination.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive) as zipped:
        for item in zipped.infolist():
            target = (destination / item.filename).resolve()
            if not target.is_relative_to(destination.resolve()) or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Unsafe Redis archive path")
        zipped.extractall(destination)
    executables = list(destination.rglob("redis-server.exe"))
    if len(executables) != 1:
        raise ValueError("Redis executable layout is ambiguous")
    executable = executables[0]
    version = subprocess.check_output([str(executable), "--version"], cwd=executable.parent, text=True).strip()
    manifest = {"version": VERSION, "source": URL, "sha256": SHA256,
                "publisher": "redis-windows community Windows build", "executable": str(executable), "version_output": version}
    (destination / "download-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(version)
    print("Redis package verified inside project.")


if __name__ == "__main__":
    main()
