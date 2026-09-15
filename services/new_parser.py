#imports
import requests
import asyncio
import time

from docx import Document
from pathlib import Path
from vkbottle import API
from dotenv import load_dotenv
from os import getenv
from services.logging_config import setup_logging
from logging import getLogger
from typing import List, Optional
from vkbottle_types.objects import WallWallpostFull
from services.redis_hub import RedisHub

#base funcs
load_dotenv()
setup_logging()
log = getLogger("parser")
rhub = RedisHub()

#const
TOKEN = getenv("access_token")
GROUP_ID = getenv("schedule_id")
GATEWAY_API = getenv("API_GATEWAY")

#vk api
api = API(token=TOKEN)
api.API_URL = GATEWAY_API

#cache service
async def get_posts(
    api: API,
    group_id: int,
    count: int = 5,
    ttl: int = 100
) -> List[dict]:

    cache_key = f"cache:vk:wall:{group_id}"

    cached_posts = await rhub.cache.get_json(cache_key)
    if cached_posts:
        log.info(f"[CACHE] Return {count} posts from Redis cache")
        return cached_posts[:count]

    response = await api.wall.get(
        owner_id = -group_id,
        count = count
    )

    posts_data = [post.model_dump() for post in response.items]

    await rhub.cache.set_json(cache_key, posts_data, ttl=ttl)
    log.info(f"[CAHCE] The parser downloaded data from VK wall and cached it in Redis")

    return posts_data[:count]



async def run_parser():
    async with rhub:
        while True:
            try:
                # main code
                group_id = int(GROUP_ID) if GROUP_ID.isdigit() else 12345678
                posts = await get_posts(api, group_id, count=5)
                print(posts)

            # Exception handler 
            except Exception:
                log.exception("Exception: ")

            await asyncio.sleep(100)

if __name__ == "__main__":
    try:
        asyncio.run(run_parser())
    except KeyboardInterrupt:
         log.info("Parser truned off")



