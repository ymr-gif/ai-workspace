from arq import create_pool
from arq.connections import RedisSettings

_pool = None


async def init_arq_pool(redis_url: str):
    global _pool
    _pool = await create_pool(RedisSettings.from_dsn(redis_url))
    return _pool


def get_arq_pool():
    return _pool
