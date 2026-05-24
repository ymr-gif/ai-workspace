import logging
import uuid
from pathlib import Path

from core.db import AsyncSessionLocal
from llm.embeddings import embed
from models import File, FileChunk

logger = logging.getLogger("processor")

CHUNK_SIZE    = 1800   # ~450 tokens
CHUNK_OVERLAP = 200


def extract_text(storage_path: str, mime_type: str) -> str:
    path = Path(storage_path)
    mt   = (mime_type or "").lower()

    if mt == "application/pdf" or path.suffix.lower() == ".pdf":
        return _extract_pdf(path)

    if mt in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ) or path.suffix.lower() in (".docx", ".doc"):
        return _extract_docx(path)

    # plain text, code, markdown, etc.
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.warning("[processor] text read failed path=%s err=%s", path, e)
        return ""


def _extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        logger.warning("[processor] pypdf not installed")
        return ""
    except Exception as e:
        logger.warning("[processor] pdf failed path=%s err=%s", path, e)
        return ""


def _extract_docx(path: Path) -> str:
    try:
        from docx import Document
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        logger.warning("[processor] python-docx not installed")
        return ""
    except Exception as e:
        logger.warning("[processor] docx failed path=%s err=%s", path, e)
        return ""


def chunk_text(text: str) -> list[str]:
    if not text.strip():
        return []
    chunks = []
    start  = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            for sep in ["\n\n", "\n", ". ", " "]:
                idx = text.rfind(sep, start + CHUNK_SIZE // 2, end)
                if idx > 0:
                    end = idx + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - CHUNK_OVERLAP
        if start >= end:
            start = end
    return chunks


async def extract_url_text(url: str) -> tuple[str, str]:
    """Fetch URL, extract readable text. Returns (text, title)."""
    import httpx
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("[processor] beautifulsoup4 not installed")
        return "", url

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()

        soup  = BeautifulSoup(resp.text, "lxml")
        title = (soup.find("title") or {}).get_text(strip=True) if soup.find("title") else url

        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        return text, title

    except Exception as e:
        logger.warning("[processor] url fetch failed url=%s err=%s", url, e)
        return "", url


async def process_file_async(file_id: uuid.UUID, storage_path: str, mime_type: str) -> None:
    """Background task: extract → chunk → embed → save."""
    async with AsyncSessionLocal() as db:
        try:
            await _process(db, file_id, storage_path, mime_type)
        except Exception:
            logger.exception("[processor] failed file_id=%s", file_id)
            row = await db.get(File, file_id)
            if row:
                row.upload_status = "error"
                await db.commit()


async def _process(db, file_id: uuid.UUID, storage_path: str, mime_type: str) -> None:
    row = await db.get(File, file_id)
    if not row:
        return

    row.upload_status = "processing"
    await db.commit()

    text = extract_text(storage_path, mime_type)
    if not text.strip():
        row.upload_status = "error"
        await db.commit()
        logger.warning("[processor] empty text file_id=%s", file_id)
        return

    chunks  = chunk_text(text)
    saved   = 0

    for i, chunk in enumerate(chunks):
        emb = await embed(chunk, input_type="passage")
        if emb:
            db.add(FileChunk(
                file_id     = file_id,
                chunk_index = i,
                content     = chunk,
                token_count = len(chunk.split()),
                embedding   = emb,
            ))
            saved += 1

    await db.commit()
    row.upload_status = "ready"
    await db.commit()
    logger.info("[processor] done file_id=%s chunks=%d/%d", file_id, saved, len(chunks))
