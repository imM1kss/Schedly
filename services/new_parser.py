#imports
import requests
import asyncio
import time
import io
import aiohttp

from docx import Document
from pathlib import Path
from vkbottle import API
from dotenv import load_dotenv
from os import getenv
from services.logging_config import setup_logging
from logging import getLogger
from typing import List
from vkbottle_types.objects import WallWallpostFull
from services.redis_hub import RedisHub
from urllib.parse import quote
from vkbottle.http import AiohttpClient


#base funcs
load_dotenv()
setup_logging()
log = getLogger("parser")
rhub = RedisHub()

#const
TOKEN = getenv("access_token")
GROUP_ID = getenv("schedule_id")
VK_GATEWAY_API = getenv("API_GATEWAY_VK")
YCF_PROXY_URL = getenv("YCF_PROXY_URL")
YCF_SECRET = getenv("YCF_SECRET")

#vk api


api = API(token=TOKEN)
api.API_URL = VK_GATEWAY_API

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


async def get_unprocessed_docx(api: API, group_id: int) -> List[dict]:
    posts = await get_posts(api, group_id, count=5)
    new_files = []

    for post in posts:

        attachments = post.get("attachments") or []

        for att in attachments:
            if att.get("type") == "doc":
                doc = att.get('doc') or {}

                title = doc.get('title', "")
                url = doc.get("url")
                doc_id = doc.get("id")

                if title.lower().endswith(".docx") and url and doc_id:
                    is_new = await rhub.loadhistory.check(target="schedule", doc_id=doc_id)
                    if is_new:
                        new_files.append({"title":title, "url":url})
                        log.info(f"New schedule file finded succesful: {title}")

    return new_files

async def download_docx(title: str, url: str) -> Document | None:

    log.info(f"Starting secure download {title} via YCF")
    safe_target_url = quote(url, safe="")
    request_url = f"{YCF_PROXY_URL}?target_url={safe_target_url}"

    headers = {
        "x-proxy-secret": YCF_SECRET
    }
    for att in range(3):
        try:
            connector = aiohttp.TCPConnector(force_close=True, enable_cleanup_closed=True)
            async with aiohttp.ClientSession(connector=connector) as session:

                async with session.get(request_url, headers=headers) as response:
                    if response.status == 403:
                        log.error("YCF access denied (Invalid Secret Code)")
                        return None
                    elif response.status != 200:
                        log.error(f"Error proxing {title}. Status YCF {response.status}")
                        return None

                    file_bytes = await response.read()

            virtual_file = io.BytesIO(file_bytes)
            doc = Document(virtual_file)
            if doc:
                log.info(f"Document {title} downloaded succesful")
                return doc
        except (aiohttp.ClientError, ConnectionResetError) as e:
            log.warning(f"Network error during download {title} | {att} atts/3")
            await asyncio.sleep(2)
        except Exception:
            log.exception(F"Critical error during read {title}: ")
            return None
    log.error(f"Failed to download {title} after 3 attemps")
    return None




async def run_parser():
    async with rhub:
        while True:
            try:
                # main code
                
                group_id = int(GROUP_ID) if GROUP_ID and GROUP_ID.isdigit() else 12345678

                files = await get_unprocessed_docx(api, group_id)

                for fl in files:
                    doc = await download_docx(title=fl["title"], url=fl["url"])
                    if doc:
                        log.info(f"Ready to parse tables from {fl["title"]}")




            # Exception handler 
            except Exception:
                log.exception("Exception: ")

            await asyncio.sleep(100)

if __name__ == "__main__":
    try:
        asyncio.run(run_parser())
    except KeyboardInterrupt:
         log.info("Parser truned off")



