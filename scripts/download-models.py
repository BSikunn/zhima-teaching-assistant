"""Download a pinned BGE snapshot into this project, without global caches."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))
os.environ.setdefault("TEMP", str(ROOT / ".cache" / "tmp"))
os.environ.setdefault("TMP", str(ROOT / ".cache" / "tmp"))

REVISION = "7999e1d3359715c523056ef9478215996d62a620"
FILES = ["config.json", "config_sentence_transformers.json", "modules.json",
         "sentence_bert_config.json", "special_tokens_map.json", "tokenizer.json",
         "tokenizer_config.json", "vocab.txt", "1_Pooling/config.json", "model.safetensors"]
WEIGHTS_SHA256 = "354763b9b1357bc9c44f62c6be2276321081ed2567773608c0d0785b61d5a026"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    import httpx
    target = ROOT / "models" / "bge-small-zh-v1.5"
    target.mkdir(parents=True, exist_ok=True)
    hashes = {}
    with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(60, connect=20)) as client:
        for filename in FILES:
            destination = target / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            if filename == "model.safetensors" and destination.is_file() and digest(destination) == WEIGHTS_SHA256:
                hashes[filename] = WEIGHTS_SHA256
                continue
            url = f"https://huggingface.co/BAAI/bge-small-zh-v1.5/resolve/{REVISION}/{filename}"
            partial = destination.with_suffix(destination.suffix + ".part")
            try:
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    with partial.open("wb") as output:
                        for block in response.iter_bytes(1024 * 1024):
                            output.write(block)
                value = digest(partial)
                if filename == "model.safetensors" and value != WEIGHTS_SHA256:
                    raise ValueError("BGE weights checksum mismatch")
                if filename.endswith(".json"):
                    json.loads(partial.read_text(encoding="utf-8"))
                partial.replace(destination)
                hashes[filename] = value
                print(f"Saved {filename} ({destination.stat().st_size} bytes)", flush=True)
            finally:
                partial.unlink(missing_ok=True)
    (target / "download-manifest.json").write_text(json.dumps({
        "model": "BAAI/bge-small-zh-v1.5", "revision": REVISION, "sha256": hashes,
        "source": "https://huggingface.co/BAAI/bge-small-zh-v1.5",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Model files ready: {target}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Model download failed ({type(error).__name__}); rerun to retry.", file=sys.stderr)
        sys.exit(1)
