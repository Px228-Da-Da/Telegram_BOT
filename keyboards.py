from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def pm_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="pm_add")],
        [InlineKeyboardButton(text="📋 Очередь", callback_data="pm_queue")],
        [InlineKeyboardButton(text="⏳ В работе", callback_data="pm_inprogress")],
        [InlineKeyboardButton(text="🔎 Поиск", callback_data="pm_search")],
        [InlineKeyboardButton(text="📊 Экспорт", callback_data="pm_export")]
    ])

def exec_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Доступные", callback_data="exec_open")],
        [InlineKeyboardButton(text="🎯 Мои назначения", callback_data="exec_direct")],
        [InlineKeyboardButton(text="👤 Мои задачи", callback_data="exec_my")]
    ])

def pm_review_kb(task_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять работу", callback_data=f"pm_accept_{task_id}")],
        [InlineKeyboardButton(text="❌ Вернуть", callback_data=f"pm_return_{task_id}")]
    ])
