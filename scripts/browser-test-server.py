"""Run browser acceptance against project-local disposable data, with no paid calls."""
from datetime import datetime
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.main import create_app
import uvicorn

if __name__ == "__main__":
    data = ROOT / ".cache" / "tmp" / ("browser-acceptance-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    uvicorn.run(create_app(data_dir=data), host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8766)
