import os
import asyncio
from random import randint
from vkbottle.bot import Bot
from dotenv import load_dotenv

from bots.vk.handlers import labeler
from services.database import Database, async_session
from services.logging_config import setup_logging
from logging import getLogger

load_dotenv()
setup_logging()
logger = getLogger("vk_bot")

TOKEN = os.getenv("VK_token")
bot = Bot(token=TOKEN)
labeler.load(bot.labeler)

async def periodic_check_and_notify():
    """Фоновая проверка расписания в БД каждые 5 минут и рассылка в привязанные чаты"""
    while True:
        try:
            async with async_session() as session:
                db = Database(session)
                # Берем все группы, у которых заполнен vk_id чата
                groups = await db.groups.get_all_by()
                for grp in groups:
                    if not grp.vk_id:
                        continue
                    
                    # Проверяем, появились ли неотправленные данные на сегодня/завтра
                    new_sched = await db.schedule.get_unnotified(group_id=grp.id)
                    if new_sched:
                        lines = [f"Новое расписание для {grp.code}:"]
                        for item in new_sched:
                            lines.append(f"({item.period}) {item.subject.title} [{item.classroom}]")
                        
                        await bot.api.messages.send(
                            peer_id=grp.vk_id,
                            message="\n".join(lines),
                            random_id=randint(1, 1000000)
                        )
                        await db.schedule.mark_as_notified(group_id=grp.id)
                        await session.commit()
        except Exception:
            logger.exception("Ошибка в фоновой рассылке расписания")
        
        await asyncio.sleep(300)

if __name__ == "__main__":
    logger.info("Запуск VK-бота...")
    bot.loop_wrapper.add_task(periodic_check_and_notify())
    bot.run_forever()