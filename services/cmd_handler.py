import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
from services.old_database import DataBase
import asyncio

load_dotenv()

data = DataBase()

#const
TOKEN = os.getenv("groq_token")


client = AsyncOpenAI(
    api_key=TOKEN, 
    base_url="https://api.groq.com/openai/v1"
)

async def get_groq_response(message:str = None, group_name:str = None):
    if (message in [None,""]) or group_name is None:
        return None
    
    subjects = [(id,name) for id,name in data.get_subjects(group_name=group_name)]

    promt = f'''У тебя есть сообщение пользователя: "{message}". Во-первых, это похоже на домашнее задание?
      Если нет, то верни просто None. Если да, то вот тебе список предметов для этой группы: {subjects}.
      Если это все-таки дз, то верни какой это предмет из списка и какой текст и на сколько пар(по умолчанию 1).
      Если результат положительный, то верни в формате: (<id_предмета>,<текст_дз>,<количество_пар>). Если отрицательный,
      то верни None. А ВОТ ТЕПЕРЬ ВНИМАНИЕ: ВОЗВРАЩАЙ ТОЛЬКО В ТОМ ФОРМАТЕ В КОТОРОМ Я ТЕБЕ ПИСАЛ. НЕ КАКОЙ ОТСЕБЯТЬИНЫ!!!!!.
      нужен только ответ в нужном формате, либо None. !!!! ЕСЛИ В СООБЩЕНИИ ЕСТЬ СЛОВА по типу "бот" или название предмет, то не возвращай его в текст_дз, а просто удали из него'''
    
    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{
            "role":"user",
            "content":promt
        }]
    )

    return response.choices[0].message.content

async def main():
    print("Request to Groq...")

    result = await get_groq_response(message="бот соси хуй", group_name="2514")
    print("Ответ получен: ")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())