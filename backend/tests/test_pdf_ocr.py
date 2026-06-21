"""Unit tests for scanned-PDF OCR fallback (Q-C5) — run with: pytest backend/tests/test_pdf_ocr.py -v

Covers:
  - Gate off + empty-text PDF → "", no OCR call
  - Gate on + empty-text PDF → OCR fallback via pypdfium2 + extract_image_from_bytes
  - Gate on + real text-layer PDF → pypdf text returned, OCR not called
  - Page cap respected (≤20 pages OCR'd)
  - ImportError / render exception → ""
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("NVIDIA_API_KEY",  "test-key")
os.environ.setdefault("DATABASE_URL",    "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",       "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY",  "test-secret")


# ── helpers ──────────────────────────────────────────────────────────────────

def _mock_pypdf(texts: list[str]):
    """Return sys.modules dict mocking pypdf with given per-page extract_text."""
    fake_reader = MagicMock()
    fake_reader.pages = [MagicMock() for _ in texts]
    for p, t in zip(fake_reader.pages, texts):
        p.extract_text.return_value = t
    fake_mod = MagicMock()
    fake_mod.PdfReader = MagicMock(return_value=fake_reader)
    return {"pypdf": fake_mod}


def _mock_pypdfium2(n_pages: int = 1, doc_raise: Exception | None = None):
    """Return sys.modules dict mocking pypdfium2.

    If doc_raise is set, PdfDocument() raises that exception.
    """
    fake_doc = MagicMock()
    fake_doc.__len__.return_value = n_pages
    pages = []
    for _ in range(n_pages):
        p = MagicMock()
        bm = MagicMock()
        p.render_to_bitmap.return_value = bm
        bm.to_pil.return_value = MagicMock()
        pages.append(p)
    fake_doc.__getitem__.side_effect = lambda i: pages[i]
    fake_mod = MagicMock()
    if doc_raise:
        fake_mod.PdfDocument = MagicMock(side_effect=doc_raise)
    else:
        fake_mod.PdfDocument = MagicMock(return_value=fake_doc)
    return {"pypdfium2": fake_mod}


# ── Gate off + empty-text PDF → "" ──────────────────────────────────────────

@patch("services.processor.config.IMAGE_OCR_ENABLED", False)
def test_gate_off_empty_pdf_returns_empty():
    modules = _mock_pypdf([""])
    with patch.dict("sys.modules", modules):
        from services.processor import _extract_pdf
        result = _extract_pdf(Path("/fake/empty.pdf"))
    assert result == ""


@patch("services.processor.config.IMAGE_OCR_ENABLED", False)
def test_gate_off_pypdf_import_error_returns_empty():
    saved = sys.modules.pop("pypdf", None)
    try:
        from services.processor import _extract_pdf
        result = _extract_pdf(Path("/fake/empty.pdf"))
        assert result == ""
    finally:
        if saved is not None:
            sys.modules["pypdf"] = saved


# ── Gate on + real text-layer PDF → pypdf used, OCR not called ──────────────

@patch("services.processor.config.IMAGE_OCR_ENABLED", True)
def test_text_pdf_uses_pypdf_no_ocr():
    modules = _mock_pypdf(["Hello world", "Page two"])
    with patch.dict("sys.modules", modules):
        from services.processor import _extract_pdf
        with patch("services.processor.extract_image_from_bytes") as mock_ocr:
            result = _extract_pdf(Path("/fake/text.pdf"))
    assert "Hello world" in result
    assert "Page two" in result
    mock_ocr.assert_not_called()


# ── Gate on + empty-text PDF → OCR fallback ─────────────────────────────────

@patch("services.processor.config.IMAGE_OCR_ENABLED", True)
def test_empty_pdf_triggers_ocr_fallback():
    modules = {**_mock_pypdf([""]), **_mock_pypdfium2(1)}
    with patch.dict("sys.modules", modules):
        from services.processor import _extract_pdf
        with patch("services.processor.extract_image_from_bytes", return_value="OCR page text") as mock_ocr:
            result = _extract_pdf(Path("/fake/scanned.pdf"))
    assert "OCR page text" in result
    mock_ocr.assert_called_once()


@patch("services.processor.config.IMAGE_OCR_ENABLED", True)
def test_empty_pdf_multi_page_ocr():
    modules = {**_mock_pypdf(["", "", ""]), **_mock_pypdfium2(3)}
    with patch.dict("sys.modules", modules):
        from services.processor import _extract_pdf
        with patch("services.processor.extract_image_from_bytes", side_effect=["pg1 text", "pg2 text", "pg3 text"]):
            result = _extract_pdf(Path("/fake/multi.pdf"))
    assert "pg1 text" in result
    assert "pg2 text" in result
    assert "pg3 text" in result


# ── Page cap ─────────────────────────────────────────────────────────────────

@patch("services.processor.config.IMAGE_OCR_ENABLED", True)
def test_ocr_page_cap_respected():
    modules = {**_mock_pypdf([""] * 50), **_mock_pypdfium2(50)}
    ocr_call_count = 0
    def ocr_side(_):
        nonlocal ocr_call_count
        ocr_call_count += 1
        return f"page {ocr_call_count}"
    with patch.dict("sys.modules", modules):
        from services.processor import _extract_pdf
        with patch("services.processor.extract_image_from_bytes", side_effect=ocr_side):
            _extract_pdf(Path("/fake/big.pdf"))
    assert ocr_call_count <= 20


# ── OCR fallback ImportError (no pypdfium2) → "" ────────────────────────────

@patch("services.processor.config.IMAGE_OCR_ENABLED", True)
def test_ocr_fallback_import_error_returns_empty():
    modules = _mock_pypdf([""])
    with patch.dict("sys.modules", modules):
        from services.processor import _extract_pdf
        result = _extract_pdf(Path("/fake/scanned.pdf"))
    assert result == ""


# ── OCR fallback exception during PdfDocument → "" ──────────────────────────

@patch("services.processor.config.IMAGE_OCR_ENABLED", True)
def test_ocr_fallback_render_exception_returns_empty():
    modules = {**_mock_pypdf([""]), **_mock_pypdfium2(1, doc_raise=RuntimeError("render fail"))}
    with patch.dict("sys.modules", modules):
        from services.processor import _extract_pdf
        result = _extract_pdf(Path("/fake/bad.pdf"))
    assert result == ""


# ── pypdf exception + gate on → falls through to OCR ────────────────────────

@patch("services.processor.config.IMAGE_OCR_ENABLED", True)
def test_pypdf_exception_falls_through_to_ocr():
    """pypdf ImportError (text stays blank) + gate on → OCR fallback runs."""
    modules = _mock_pypdfium2(1)
    with patch.dict("sys.modules", modules):
        from services.processor import _extract_pdf
        with patch("services.processor.extract_image_from_bytes", return_value="OCR text"):
            result = _extract_pdf(Path("/fake/scanned.pdf"))
    # pypdf isn't mocked → ImportError → text stays ""
    # gate on → OCR fallback runs with pypdfium2
    assert result == "OCR text"
