"""Unit tests — run with: pytest backend/tests/test.py -v"""
import os
import sys
import pytest

# allow imports from backend/ without installing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("NVIDIA_API_KEY",  "test-key")
os.environ.setdefault("DATABASE_URL",    "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",       "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY",  "test-secret")


# ── model router ──────────────────────────────────────────────────────────────

from llm.router import classify


@pytest.mark.parametrize("msg,expected", [
    ("write a python function to sort a list", "coder"),
    ("fix this bug in my code",                "coder"),
    ("implement a binary search algorithm",    "coder"),
    ("explain why recursion works",            "reasoning"),
    ("what is the difference between tcp and udp", "reasoning"),
    ("how does garbage collection work",       "reasoning"),
    ("hello, how are you?",                    "llama"),
    ("tell me a joke",                         "llama"),
    ("what is the weather today",              "reasoning"),
])
def test_classify(msg, expected):
    assert classify(msg) == expected


# ── cache key generation ──────────────────────────────────────────────────────

from cache.keys import normalize, make_key


def test_normalize_strips_whitespace():
    assert normalize("  Hello  ") == "hello"


def test_normalize_lowercase():
    assert normalize("UPPER CASE") == "upper case"


def test_make_key_deterministic():
    assert make_key("hello") == make_key("hello")


def test_make_key_different_inputs():
    assert make_key("hello") != make_key("world")


def test_make_key_format():
    key = make_key("test")
    assert len(key) == 64  # sha256 hex digest


# ── auth / password hashing ───────────────────────────────────────────────────

from auth.security import verify_password
from passlib.context import CryptContext

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def test_verify_password_correct():
    hashed = _pwd.hash("mypassword")
    assert verify_password("mypassword", hashed) is True


def test_verify_password_wrong():
    hashed = _pwd.hash("mypassword")
    assert verify_password("wrongpassword", hashed) is False


# ── circuit breaker ───────────────────────────────────────────────────────────

import asyncio
import llm.circuit_breaker as cb


def _clear():
    cb._failures.clear()
    cb._open.clear()
    cb._open_time.clear()


def test_circuit_breaker_closed_initially():
    _clear()
    assert cb.is_open("test-model") is False


def test_circuit_breaker_opens_after_threshold():
    _clear()
    for _ in range(3):
        asyncio.run(cb.record_failure("test-model"))
    assert cb.is_open("test-model") is True


def test_circuit_breaker_resets_on_success():
    _clear()
    asyncio.run(cb.record_failure("test-model"))
    asyncio.run(cb.record_failure("test-model"))
    cb.record_success("test-model")
    assert cb.is_open("test-model") is False


# ── config guards ─────────────────────────────────────────────────────────────

def test_models_dict_has_required_keys():
    from config import MODELS
    assert "llama" in MODELS
    assert "coder" in MODELS
    assert "reasoning" in MODELS


def test_models_values_non_empty():
    from config import MODELS
    for name, model_id in MODELS.items():
        assert model_id, f"MODELS['{name}'] is empty"
