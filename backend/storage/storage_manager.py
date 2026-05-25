import uuid
from pathlib import Path

import aiofiles
from fastapi import UploadFile

from config import STORAGE_DIR

BASE_DIR = Path(STORAGE_DIR)
BASE_DIR.mkdir(parents=True, exist_ok=True)


_READ_CHUNK = 1024 * 1024  # 1 MB


class StorageManager:
    async def save_file(self, file: UploadFile) -> tuple[str, str, int]:
        file_id      = str(uuid.uuid4())
        safe_name    = f"{file_id}_{file.filename}"
        storage_path = BASE_DIR / safe_name

        size_bytes = 0
        async with aiofiles.open(storage_path, "wb") as out:
            while True:
                chunk = await file.read(_READ_CHUNK)
                if not chunk:
                    break
                await out.write(chunk)
                size_bytes += len(chunk)

        return str(storage_path), file.filename, size_bytes

    async def save_text(self, text: str, filename: str) -> tuple[str, int]:
        file_id      = str(uuid.uuid4())
        safe_name    = f"{file_id}_{filename}"
        storage_path = BASE_DIR / safe_name
        content      = text.encode("utf-8")

        async with aiofiles.open(storage_path, "wb") as f:
            await f.write(content)

        return str(storage_path), len(content)
