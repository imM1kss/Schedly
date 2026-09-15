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

#base funcs
load_dotenv()
setup_logging()
log = getLogger("parser")

#const
TOKEN = getenv("access_token")
GROUP_ID = getenv("schedule_id")
GATEWAY_API = getenv("API_GATEWAY")

#vk api
api = API(token=TOKEN)
api.API_URL = GATEWAY_API

#cache service
class WallCache:
    def __init__(self, api: API,ttl: int = 100):
        self.api = api
        self.ttl = ttl

        self._cached_posts: List[WallWallpostFull] = []
        self._last_updated: float = 0.0
        self._lock = asyncio.Lock()

    async def get_posts(
            self,
            count: int = 1,
            force_refresh: bool = False
    ) -> List[WallWallpostFull]:
        # current time 
        cur_time = time.monotonic()

        #if cache is frash give it without lock
        if not force_refresh and (cur_time - self._last_updated < self.ttl):
            print("return cache")
            return self._cached_posts[:count]
        

        async with self._lock:
            cur_time = time.monotonic()
            if not force_refresh and (cur_time - self._last_updated < self.ttl):
                print("return cache")
                return self._cached_posts[:count]

             # getting group id
            group_id_response = await self.api.groups.get_by_id(group_id=GROUP_ID)
            if group_id_response and group_id_response.groups:
                group = group_id_response.groups[0]  # take the first group from .groups list
                group_id = group.id # call .id attribute
            

             #response to vk wall
            response = await self.api.wall.get(
                owner_id = -group_id,
                count=count
            )

            self._cached_posts = response.items
            self._last_updated = cur_time
            log.info("[CACHE] parser cached new data from vk wall")

            return self._cached_posts[:count]

#init cache service
Cache = WallCache(api)



async def run_parser():
    while True:
        try:
            # main code
            print(await Cache.get_posts())

        # Exception handler 
        except Exception:
            log.exception("Exception: ")

        await asyncio.sleep(100)

if __name__ == "__main__":
    try:
        asyncio.run(run_parser())
    except KeyboardInterrupt:
         log.info("Parser truned off")



