#imports
import requests
import asyncio
import time
import io
import aiohttp
import re

from docx import Document
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
from services.database import Database, async_session
from datetime import date
from sqlalchemy.exc import IntegrityError


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

MONTHS = {
    "января":1, "февраля":2, "марта":3, "апреля":4,
    "мая":5, "июня":6, "июля":7, "августа":8,
    "сентября":9, "октября":10, "ноября":11, "декабря":12
}

#vk api


api = API(token=TOKEN)
api.API_URL = VK_GATEWAY_API

#cache service
async def get_posts(
    api: API,
    group_id: int,
    count: int = 3,
    ttl: int = 100
) -> List[dict]:

    cache_key = f"cache:vk:wall:{group_id}"

    cached_posts = await rhub.cache.get_json(cache_key)
    if cached_posts:
        log.info(f"[CACHE] Return {count} posts from Redis cache")
        return cached_posts[:count]

    for att in range(1,4):
        try:
            response = await api.wall.get(
                owner_id = -group_id,
                count = count
            )

            posts_data = [post.model_dump() for post in response.items]
            posts_data.reverse()

            await rhub.cache.set_json(cache_key, posts_data, ttl=ttl)
            log.info(f"[CAHCE] The parser downloaded data from VK wall and cached it in Redis")

            return posts_data[:count]
        except Exception as e:
            log.warning(f"Critical network error during get posts | {att}/3 attemps")
            await asyncio.sleep(2)

    log.error("Failed get posts after 3 attemps")
    return []
    


async def get_unprocessed_docx(api: API, group_id: int, count: int = 3) -> List[dict]:
    posts = await get_posts(api, group_id, count)
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
                        new_files.append({"title":title, "url":url, "doc_id":doc_id})
                        log.info(f"New schedule file finded succesful: {title}")
    return new_files

async def download_docx(title: str, url: str) -> Document | None:

    log.info(f"Starting secure download {title} via YCF")
    safe_target_url = quote(url, safe="")
    request_url = f"{YCF_PROXY_URL}?target_url={safe_target_url}"

    headers = {
        "x-proxy-secret": YCF_SECRET
    }
    for att in range(1,4):
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

def extract_date_from_header(header_cells: List) -> date | None:
    for cell in header_cells:
        clean_str = cell.replace('\xa0', ' ').lower()

        pattern = r"(\d{1,2})\s+([а-я]+)\s+(\d{4})"
        match = re.search(pattern, clean_str, flags=re.IGNORECASE)
        if match:
            day = int(match.group(1))
            month_str = match.group(2)
            year = int(match.group(3))

            month = MONTHS.get(month_str.lower())
            if month:
                return date(year, month, day)
    return None

def clean(raw_cells:tuple) -> List:
    cells = []

    for cell in raw_cells:
        text = cell.text.strip()
        if text and text not in cells:
            cells.append(text)

    if len(cells) == 1:
        cells = cells[0].split("\n")
    
    elif len(cells) > 1:
        pattern = r"^\d+-\d+$"

        for index,cell in enumerate(cells):
            if re.match(pattern, cell):
                return cells[index:]
    
    return cells


async def run_parser():
    vk_connector = aiohttp.TCPConnector(force_close=True, enable_cleanup_closed=True)
    vk_session = aiohttp.ClientSession(connector=vk_connector)
    api.http_client = AiohttpClient(session=vk_session)

    async with rhub:
        while True:
            try:
                # main code
                
                group_id = int(GROUP_ID) if GROUP_ID and GROUP_ID.isdigit() else 12345678

                files = await get_unprocessed_docx(api, group_id, count=3)

                for fl in files:
                    #doc envs
                    doc_title = fl.get("title")
                    doc_id = fl.get("doc_id")
                    doc_url = fl.get("url")

                    if not all([doc_url, doc_title, doc_id]):
                        raise ValueError("doc_url or doc_title or doc_id is empty")

                    doc = await download_docx(title=doc_title, url=doc_url)
                    if doc:
                        log.info(f"Ready to parse tables from {doc_title}")

                        async with async_session() as session:
                            db = Database(session)

                            try:
                                await db.download_history.add(doc_id=int(doc_id), title=doc_title)
                                log.info(f"Document {doc_title} saved in Postgre")
                            except IntegrityError:
                                await session.rollback()
                                log.info(f"Document {doc_title} already exists in the Postgre")

                            if not doc.tables:
                                log.warning(f"Parser didn't find any tables in doc {doc_title}")
                                return
                            
                                
                            for index, row in enumerate(doc.tables[0].rows):
                                cells = clean(row.cells)
                        
                                if index == 0:
                                    schedule_date = extract_date_from_header(cells)
                                    log.info(f"Parser found schedule date {schedule_date} in doc {doc_title}")
                                    continue
                        
                                if not cells:
                                    continue

                                db_groups = await db.groups.get_all_by()
                                
                                group_map = {re.sub(r"\D", "", g.code): g.id for g in db_groups}
                    
                                raw_group = cells[0]
                                group_norm = re.sub(r'\D', '', raw_group)
                    
                                if group_norm in group_map:
                                    group_id = group_map[group_norm]
                    
                                    period = int(re.sub(r'\D', '', cells[1]))
                                    subj_title = cells[2]
                                    classroom = cells[3] if len(cells) > 3 else "Нет"
                    
                                    subject = await db.subjects.ensure(title=subj_title, group_id=group_id)
                                    log.info(f"New schedule {schedule_date} found for group {group_norm}")
                    
                                    try:
                                        await db.schedule.add(
                                            group_id = group_id,
                                            subj_id = subject.id,
                                            period = period,
                                            classroom = classroom,
                                            date = schedule_date
                                        )
                                        log.info(f"Schedule {schedule_date} added for group {group_norm}: {period}, {subj_title} {classroom}")
                                    except IntegrityError:
                                        await session.rollback()


            # Exception handler 
            except Exception:
                log.exception("Exception: ")

            await asyncio.sleep(100)

if __name__ == "__main__":
    try:
        asyncio.run(run_parser())
    except KeyboardInterrupt:
         log.info("Parser truned off")



