"""Unit tests for image OCR (Q2 #19) — run with: pytest backend/tests/test_image_ocr.py -v"""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("NVIDIA_API_KEY",  "test-key")
os.environ.setdefault("DATABASE_URL",    "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",       "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY",  "test-secret")


# ── _extract_image ───────────────────────────────────────────────────────────

@patch("services.processor.config.IMAGE_OCR_ENABLED", True)
def test_extract_image_routes_to_ocr_when_enabled():
    from services.processor import extract_text
    with patch("services.processor._extract_image", return_value="hello world"):
        result = extract_text("/fake/path.png", "image/png")
        assert result == "hello world"


def test_extract_image_returns_empty_when_gate_off():
    from services.processor import extract_text
    result = extract_text("/fake/path.png", "image/png")
    assert result == ""


@patch("services.processor._extract_image")
def test_extract_image_called_with_path(mock_extract):
    mock_extract.return_value = "some text"
    with patch("services.processor.config.IMAGE_OCR_ENABLED", True):
        from services.processor import extract_text
        result = extract_text("/fake/path.png", "image/png")
        assert result == "some text"
        mock_extract.assert_called_once()
        assert str(mock_extract.call_args[0][0]) == "/fake/path.png"


# ── extract_text mime routing ────────────────────────────────────────────────

def test_extract_text_image_mime_routes_to_extract_image():
    from services.processor import extract_text
    with patch("services.processor.config.IMAGE_OCR_ENABLED", True):
        with patch("services.processor._extract_image", return_value="ocr text"):
            assert extract_text("/f.png", "image/png") == "ocr text"
            assert extract_text("/f.jpeg", "image/jpeg") == "ocr text"
            assert extract_text("/f.webp", "image/webp") == "ocr text"


# ── _process flow ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("services.processor.config.IMAGE_OCR_ENABLED", True)
async def test_process_image_sets_media_type():
    from services.processor import _process
    db = AsyncMock()
    row = MagicMock()
    row.media_type = "document"
    row.ocr_text = None
    row.upload_status = "uploaded"
    db.get.return_value = row

    with patch("services.processor.extract_text", return_value="ocr extracted text"):
        with patch("services.processor.chunk_text", return_value=["chunk1"]):
            with patch("services.processor.embed", return_value=[0.1] * 1024):
                await _process(db, "fake-id", "/fake/path.png", "image/png")

    assert row.media_type == "image"
    assert row.ocr_text == "ocr extracted text"


@pytest.mark.asyncio
@patch("services.processor.config.IMAGE_OCR_ENABLED", True)
async def test_process_image_no_text_ready_zero_chunks():
    """No-text image → ready, 0 chunks, not error."""
    from services.processor import _process
    db = AsyncMock()
    row = MagicMock()
    row.media_type = "document"
    row.ocr_text = None
    row.upload_status = "uploaded"
    db.get.return_value = row

    with patch("services.processor.extract_text", return_value=""):
        await _process(db, "fake-id", "/fake/path.png", "image/png")

    assert row.media_type == "image"
    assert row.ocr_text == ""
    assert row.upload_status == "ready"
    assert row.chunk_total == 0
    assert row.chunk_embedded == 0


@pytest.mark.asyncio
async def test_process_image_gate_off_no_ocr():
    """IMAGE_OCR_ENABLED=false → extract_text returns "" for images → ready/0 chunks not error."""
    from services.processor import _process
    db = AsyncMock()
    row = MagicMock()
    row.media_type = "document"
    row.ocr_text = None
    row.upload_status = "uploaded"
    db.get.return_value = row

    with patch("services.processor.extract_text", return_value=""):
        await _process(db, "fake-id", "/fake/path.png", "image/png")

    assert row.media_type == "image"
    assert row.ocr_text == ""
    assert row.upload_status == "ready"
    assert row.chunk_total == 0
    assert row.chunk_embedded == 0


@pytest.mark.asyncio
async def test_process_image_ocr_text_capped_at_10000():
    from services.processor import _process
    db = AsyncMock()
    row = MagicMock()
    row.media_type = "document"
    row.ocr_text = None
    row.upload_status = "uploaded"
    db.get.return_value = row

    long_text = "word " * 6000  # ~30k chars
    with patch("services.processor.config.IMAGE_OCR_ENABLED", True):
        with patch("services.processor.extract_text", return_value=long_text):
            with patch("services.processor.chunk_text", return_value=["chunk1"]):
                with patch("services.processor.embed", return_value=[0.1] * 1024):
                    await _process(db, "fake-id", "/fake/path.png", "image/png")

    assert row.media_type == "image"
    assert row.ocr_text is not None
    assert len(row.ocr_text) <= 10000


# ── non-image empty text still errors ────────────────────────────────────────

@pytest.mark.asyncio
async def test_process_non_image_empty_text_errors():
    from services.processor import _process
    db = AsyncMock()
    row = MagicMock()
    row.media_type = "document"
    row.ocr_text = None
    row.upload_status = "uploaded"
    db.get.return_value = row

    with patch("services.processor.extract_text", return_value=""):
        await _process(db, "fake-id", "/fake/path.txt", "text/plain")

    assert row.upload_status == "error"
