import re
from random import randint
from vkbottle.bot import BotLabeler, Message, MessageEvent
from vkbottle import GroupEventType

from services.database import Database, async_session
from bots.vk.keyboards import group_selection_kb, close_kb

labeler = BotLabeler()

# Костыльный кэш/список доступных групп (можно расширить или считывать из конфига/парсера)
AVAILABLE_GROUPS = ["2514", "2515", "2516", "2411", "2412", "2311"]

@labeler.message(text=["бот привяжи", "бот группа", "/start"])
async def cmd_bind_group(message: Message):
    kb = group_selection_kb(AVAILABLE_GROUPS, page=0)
    await message.answer("Выберите номер группы для этой беседы:", keyboard=kb)

@labeler.message(text=["бот расписание", "бот пары"])
async def cmd_get_schedule(message: Message):
    peer_id = message.peer_id
    async with async_session() as session:
        db = Database(session)
        # Ищем группу, привязанную к данному чату VK
        group = await db.groups.get_by(vk_id=peer_id)
        if not group:
            await message.answer("Этот чат еще не привязан к группе. Напишите: 'бот привяжи'.")
            return

        # Забираем последние пары по group.id
        schedules = await db.schedule.get_latest_for_group(group_id=group.id)
        if not schedules:
            await message.answer(f"Расписание для группы {group.code} пока не загружено.")
            return

        lines = [f"📅 Расписание группы {group.code}:", "-------------------------"]
        for sch in schedules:
            lines.append(f"Пара {sch.period}: {sch.subject.title} [каб. {sch.classroom}]")
        lines.append("-------------------------")

        await message.answer("\n".join(lines), keyboard=close_kb())

@labeler.raw_event(GroupEventType.MESSAGE_EVENT, dataclass=MessageEvent)
async def handle_callbacks(event: MessageEvent):
    payload = event.object.payload or {}
    act = payload.get("act")
    peer_id = event.object.peer_id

    if act == "close":
        await event.ctx_api.messages.delete(
            peer_id=peer_id,
            conversation_message_ids=[event.object.conversation_message_id],
            delete_for_all=True
        )
        return

    if act == "nav_groups":
        page = payload.get("page", 0)
        kb = group_selection_kb(AVAILABLE_GROUPS, page=page)
        await event.edit_message(message=f"Выберите группу (Стр. {page + 1}):", keyboard=kb)
        return

    if act == "select_group":
        group_name = payload.get("name")
        clean_code = re.sub(r"\D", "", group_name)

        async with async_session() as session:
            db = Database(session)
            # Привязываем или обновляем vk_id беседы
            group = await db.groups.get_by(code=clean_code)
            if not group:
                # Создаем группу в БД, если ее еще нет
                group = await db.groups.add(code=clean_code, vk_id=peer_id)
            else:
                group.vk_id = peer_id
            await session.commit()

        await event.ctx_api.messages.delete(
            peer_id=peer_id,
            conversation_message_ids=[event.object.conversation_message_id],
            delete_for_all=True
        )
        await event.ctx_api.messages.send(
            peer_id=peer_id,
            random_id=randint(1, 100000),
            message=f" Беседа успешно привязана к группе: {clean_code}!"
        )