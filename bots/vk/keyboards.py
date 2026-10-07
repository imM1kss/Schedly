from vkbottle import Keyboard, KeyboardButtonColor, Callback

ITEMS_PER_PAGE = 6

def group_selection_kb(groups: list[str], page: int = 0) -> Keyboard:
    kb = Keyboard(inline=True)
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    cur_names = groups[start_idx:end_idx]

    for i, name in enumerate(cur_names):
        kb.add(Callback(name, payload={"act": "select_group", "name": name}), color=KeyboardButtonColor.PRIMARY)
        if (i + 1) % 2 == 0 and (i + 1) != len(cur_names):
            kb.row()

    kb.row()
    total_pages = (len(groups) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    if page > 0:
        kb.add(Callback("<- Назад", payload={"act": "nav_groups", "page": page - 1}), color=KeyboardButtonColor.SECONDARY)
    if (page + 1) < total_pages:
        kb.add(Callback("Вперёд ->", payload={"act": "nav_groups", "page": page + 1}), color=KeyboardButtonColor.SECONDARY)
    
    kb.row()
    kb.add(Callback("Закрыть", payload={"act": "close"}), color=KeyboardButtonColor.NEGATIVE)
    return kb

def close_kb() -> Keyboard:
    kb = Keyboard(inline=True)
    kb.add(Callback("Закрыть", payload={"act": "close"}), color=KeyboardButtonColor.NEGATIVE)
    return kb