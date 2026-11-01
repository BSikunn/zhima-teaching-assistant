"""Native Chroma must survive process restart under the Chinese project path."""
import os
import subprocess
import sys
from pathlib import Path


def test_index_survives_compaction_and_fresh_process_restart(tmp_path):
    from app.config import ROOT
    code = '''
import sys,chromadb
from app.index_server import persistent_storage_path
path=persistent_storage_path(sys.argv[1])
client=chromadb.PersistentClient(path=path)
if sys.argv[2]=="write":
    collection=client.create_collection("restart_probe",configuration={"hnsw":{"sync_threshold":10,"batch_size":10}})
    collection.add(ids=[str(i) for i in range(40)],embeddings=[[float(i%3),float(i%5),float(i%7),1.0] for i in range(40)])
else:
    collection=client.get_collection("restart_probe")
assert collection.count()==40
assert collection.query(query_embeddings=[[1.0,2.0,3.0,1.0]],n_results=2)["ids"][0]
client._system.stop()
print("restart-safe")
'''
    env = {**os.environ, "PYTHONPATH": str(ROOT / "backend")}
    for phase in ("write", "read"):
        result = subprocess.run([sys.executable, "-c", code, str(tmp_path / "chroma"), phase],
                                env=env, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=30)
        assert result.returncode == 0, result.stderr
        assert "restart-safe" in result.stdout
