import asyncio
import httpx
from config import MAX_CONCURRENT_REQUESTS, REQUEST_TIMEOUT

semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
client: httpx.AsyncClient | None = None
