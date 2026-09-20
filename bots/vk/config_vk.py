from vkbottle.bot import Bot

import dotenv
import os
from random import randint

dotenv.load_dotenv()

bot = Bot(token=os.getenv("VK_token"))

async def send_message(peer_id:int = None, text:str = None) -> None:
    if peer_id is None and text is None:
        raise ValueError("Error")
    await bot.api.messages.send(peer_id=peer_id, message = text, random_id=randint(0,10000))