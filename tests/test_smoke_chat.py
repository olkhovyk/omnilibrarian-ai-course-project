import importlib.util
from pathlib import Path


def _load_smoke_chat_module():
    module_path = Path("scripts") / "smoke_chat.py"
    spec = importlib.util.spec_from_file_location("smoke_chat", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_smoke_chat_loads_dotenv_from_project_root():
    smoke_chat = _load_smoke_chat_module()

    assert smoke_chat.DOTENV_PATH == smoke_chat.PROJECT_ROOT / ".env"
