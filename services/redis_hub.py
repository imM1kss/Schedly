# imports
import json
import redis.asyncio as aioredis

from typing import Any, List
from redis.commands.core import Script

LUA_SCRIPT = """
-- KEYS[1] - list key
-- ARGV[1] - .doc id
-- ARGV[2] - max list length (100)
local items = redis.call('LRANGE', KEYS[1], 0, -1)

for i, v in ipairs(items) do
    if v == ARGV[1] then
        return 0
    end
end

redis.call('RPUSH', KEYS[1], ARGV[1])

if redis.call('LLEN', KEYS[1]) > tonumber(ARGV[2]) then
    redis.call('LPOP', KEYS[1])
end

return 1
"""

class RedisHub:
    def __init__(self, url: str = "redis://localhost:6379/0"):
        self._url = url
        self._pool: aioredis.ConnectionPool | None = None
        self._client: aioredis.Redis | None = None
        self._script: Script | None = None

        self.loadhistory = DownloadHistory(self)
        self.session = Session(self)
        self.cache = Cache(self)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.disconnect()

    async def connect(self) -> None:
        self._pool = aioredis.ConnectionPool.from_url(
            self._url,
            max_connections = 20,
            decode_responses = True,
            protocol = 2
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
                "RedisHub not initialized"
            )
        return self._client

class DownloadHistory:
    def __init__(self, hub: RedisHub):
        self.hub = hub

    async def check(self, target: str, doc_id: str | int, limit: int = 100) -> bool:
        if not self.hub._script:
             raise RuntimeError(
                 "RedisHub not initialized"
             )

        key = f"parser:history:{target}"
        result = await self.hub._script(keys=[key], args=[str(doc_id), limit])
        return bool(result)

    async def get(self, target: str) -> int | None:
        if not self.hub._script:
            raise RuntimeError(
                "RedisHub not initialized"
            )

        key = f"parser:last_seen:{target}"
        result = await self.hub.client.get(key)
        return int(result) if result is not None else None

class Session:
    def __init__(self, hub: RedisHub):
        self.hub = hub

class Cache:
    def __init__(self, hub: RedisHub):
        self.hub = hub

    async def get_json(self, key:str) -> Any | None:

        if not self.hub._client:
            raise RuntimeError("RedisHub not initialized")

        data = await self.hub.client.get(key)
        if data:
            return json.loads(data)
        return
    

    async def set_json(self, key:str, value: Any, ttl:int = 100) -> None:

        if not self.hub._client:
            raise RuntimeError("RedisHub not initialized")

        data = json.dumps(value, ensure_ascii=False, default=str)
        await self.hub.client.set(key, data, ex=ttl)


      