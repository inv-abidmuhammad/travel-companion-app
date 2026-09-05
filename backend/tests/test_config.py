"""
This exists because of a real bug: config.py originally pointed at a
bare ".env" (relative to whatever directory uvicorn was launched
from), so it silently loaded nothing and every setting fell back to
its empty-string default — no error, just a confusing 500 later, deep
inside the Gemini client. This test would have caught it before it
ever hit a running server.
"""
from app.config import BACKEND_DIR, Settings


def test_env_file_path_is_anchored_inside_backend_dir():
    # Regression guard: must NOT be a bare relative ".env" — that only
    # works if you happen to launch uvicorn from exactly the right cwd.
    assert Settings.model_config["env_file"] == BACKEND_DIR / ".env"
    assert BACKEND_DIR.name == "backend"


def test_settings_reads_a_real_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("GOOGLE_API_KEY=test-key-123\nMODEL_NAME=gemini-2.5-flash\n")

    class TestSettings(Settings):
        model_config = {**Settings.model_config, "env_file": env_file}

    # Make sure a real shell env var can't mask whether the file was read.
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    settings = TestSettings()
    assert settings.google_api_key == "test-key-123"
    assert settings.model_name == "gemini-2.5-flash"
