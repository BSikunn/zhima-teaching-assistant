from pathlib import Path
from app.config import Settings


def test_default_data_and_frontend_root_are_inside_project():
    settings = Settings()
    project = Path.cwd().resolve()
    assert settings.root == project
    assert settings.data_dir == project / "data"
    assert settings.uploads.is_relative_to(project)
