import asyncio
import uuid
from pathlib import Path

import aiofiles
from fastapi import UploadFile

from config import STORAGE_DIR

BASE_DIR = Path(STORAGE_DIR)
BASE_DIR.mkdir(parents=True, exist_ok=True)


class StorageManager:
    async def save_file(self, file: UploadFile) -> tuple[str, str, int]:
        file_id      = str(uuid.uuid4())
        safe_name    = f"{file_id}_{file.filename}"
        storage_path = BASE_DIR / safe_name

        content    = await file.read()
        size_bytes = len(content)

        async with aiofiles.open(storage_path, "wb") as f:
            await f.write(content)

        return str(storage_path), file.filename, size_bytes
