# imports
import json
import redis.asyncio as aioredis

from typing import Any
from redis.commands.core import Script

LUA_SCRIPT = """
local current = redis.call('GET', KEYS[1])

if not current or tonumber(ARGV[1]) > tonumber(current) then
    redis.call('SET', KEYS[1], ARGV[1])
    return 1
else
    return 0
end
"""

class RedisHub:
    def __init__(self, url: str = "redis://localhost:6379/0"):
        self._url = url
        self._pool: aioredis.ConnectionPool | None = None
        self._client: aioredis.Redis | None = None
        self._script: Script | None = None

        self.timestamp = TimeStamp(self)
        self.session = Session(self)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.disconnect()

    async def connect(self) -> None:
        self._pool = aioredis.ConnectionPool.from_url(
            self._url,
            max_connections = 20,
            decode_responses = True
        )
        self._client = aioredis.Redis(connection_pool=self._pool)

        self._script = self._client.register_script(LUA_SCRIPT)

        await self._client.ping()

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
        if self._pool:
            await self._pool.disconnect()

    @property
    def client(self) -> aioredis.Redis:
        if not self._client:
            raise RuntimeError(
                "RedisHub не инициализирован. Вызовите await RedisHub.connect()"
            )
        return self._client

class TimeStamp:
    def __init__(self, hub: RedisHub):
        self.hub = hub

    async def update(self, target: str, new_ts: int | float) -> bool:
        if not self.hub._script:
             raise RuntimeError(
                 "RedisHub не инициализирован"
             )

        key = f"parser:last_seen:{target}"
        result = await self.hub._script(keys=[key], args=[new_ts])
        return bool(result)

    async def last(self, target: str) -> int | None:
        if not self.hub._script:
            raise RuntimeError(
                "RedisHub не инициализирован"
            )

        key = f"parser:last_seen:{target}"
        result = await self.hub.client.get(key)
        return int(result) if result is not None else None

class Session:
    def __init__(self, hub: RedisHub):
        self.hub = hub