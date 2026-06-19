"""LLM_BACKEND switch — run with: pytest backend/tests/test_backend_mode.py -v

Verifies the inert NIM ⇄ home-server config flag and that importlib.reload
(the /admin/env/reload runtime-toggle path) re-applies the override block.
No NIM, no llama.cpp server required.
"""
import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("NVIDIA_API_KEY",  "test-key")
os.environ.setdefault("DATABASE_URL",    "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",       "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY",  "test-secret")

import config as cfg


@pytest.fixture(autouse=True)
def _restore_config():
    """Reload to baseline (nim) after each test so the shared module isn't polluted."""
    yield
    os.environ.pop("LLM_BACKEND", None)
    os.environ["NVIDIA_API_KEY"] = "test-key"
    importlib.reload(cfg)


def _reload_homeserver(monkeypatch, *, with_key: bool):
    monkeypatch.setenv("LLM_BACKEND", "homeserver")
    # empty (not deleted): config.py re-runs load_dotenv on reload, which would
    # repopulate a deleted key from .env. An empty env var is left untouched (override=False).
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key" if with_key else "")
    importlib.reload(cfg)


def test_default_is_nim_and_inert():
    importlib.reload(cfg)
    assert cfg.LLM_BACKEND == "nim"
    assert cfg.NIM_URL == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert cfg.NIM_EMBEDDING_URL == "https://integrate.api.nvidia.com/v1/embeddings"
    assert cfg.MODELS["llama"] == "meta/llama-3.1-8b-instruct"
    assert cfg.MODELS["reasoning"] == "meta/llama-3.3-70b-instruct"
    assert cfg.MODEL_EMBEDDING == "nvidia/nv-embedqa-e5-v5"
    assert cfg.DEFAULT_CONTEXT_WINDOW == 131072


def test_homeserver_override(monkeypatch):
    _reload_homeserver(monkeypatch, with_key=True)
    assert cfg.LLM_BACKEND == "homeserver"
    # endpoints repointed at the LAN llama.cpp services
    assert cfg.NIM_URL == "http://llamacpp:8080/v1/chat/completions"
    assert cfg.NIM_EMBEDDING_URL == "http://llamacpp-embed:8081/v1/embeddings"
    # three roles collapse to one Mixtral alias
    assert set(cfg.MODELS.values()) == {"mixtral"}
    # 1024-d embedder kept (no re-embed); embedding dim unchanged
    assert cfg.MODEL_EMBEDDING == "bge-large-en-v1.5"
    assert cfg.EMBEDDING_DIM == 1024
    # context sized to 32k for the budget allocator
    assert cfg.DEFAULT_CONTEXT_WINDOW == 32768
    assert cfg.CONTEXT_WINDOWS == {"mixtral": 32768}


def test_homeserver_context_limit_via_router(monkeypatch):
    _reload_homeserver(monkeypatch, with_key=True)
    import llm.router as router
    # the served alias resolves to 32k
    assert router.get_context_limit("mixtral") == 32768
    # a stale NIM id (from a module-level-frozen caller) falls through to DEFAULT = 32k — safe sizing
    assert router.get_context_limit("meta/llama-3.3-70b-instruct") == 32768


def test_homeserver_boots_without_nim_key(monkeypatch):
    # the NVIDIA_API_KEY guard must NOT fire in homeserver mode
    _reload_homeserver(monkeypatch, with_key=False)
    assert cfg.LLM_BACKEND == "homeserver"
    assert cfg.NVIDIA_API_KEY in (None, "")


def test_nim_mode_still_requires_key(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "nim")
    monkeypatch.setenv("NVIDIA_API_KEY", "")   # empty so load_dotenv won't repopulate from .env
    with pytest.raises(RuntimeError, match="NVIDIA_API_KEY"):
        importlib.reload(cfg)


def test_homeserver_env_overrides(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "homeserver")
    monkeypatch.setenv("HOMESERVER_CHAT_URL", "http://192.168.1.50:8080/v1/chat/completions")
    monkeypatch.setenv("HOMESERVER_MODEL", "mixtral-8x22b")
    monkeypatch.setenv("HOMESERVER_CTX", "16384")
    importlib.reload(cfg)
    assert cfg.NIM_URL == "http://192.168.1.50:8080/v1/chat/completions"
    assert set(cfg.MODELS.values()) == {"mixtral-8x22b"}
    assert cfg.DEFAULT_CONTEXT_WINDOW == 16384
    assert cfg.CONTEXT_WINDOWS == {"mixtral-8x22b": 16384}
