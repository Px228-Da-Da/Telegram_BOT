# common.py
from aiogram import Router, types
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import PM_IDS
from db import get_conn
from utils.time import now_ts, humanize_ts
from keyboards import pm_menu, exec_menu
from services.direct import validate_token

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject):
    # Логика регистрации/обновления пользователя
    tg_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name or ""
    role = "pm" if tg_id in PM_IDS else "exec"

    conn = get_conn()
    conn.execute("""
    INSERT INTO users(tg_id, username, full_name, role, is_active) VALUES (?, ?, ?, ?, 1)
    ON CONFLICT(tg_id) DO UPDATE SET
        username=excluded.username, full_name=excluded.full_name, role=excluded.role, is_active=1
    """, (tg_id, username, full_name, role))
    conn.commit()
    
    # ОБРАБОТКА DEEPLINK
    if command.args and command.args.startswith("claim_"):
        token = command.args.replace("claim_", "")
        task_id = validate_token(token)
        if task_id:
            task = conn.execute("SELECT * FROM tasks WHERE id = ? AND status = 'new'", (task_id,)).fetchone()
            if task:
                text = (f"<b>Вам предложена задача #{task['id']}</b>: {task['title']}\n\n"
                        f"Уровень: {task['level']}\n"
                        f"Дедлайн: {humanize_ts(task['deadline_ts'])}")
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🖐 Принять", callback_data=f"exec_take_{task['id']}")]
                ])
                await message.answer(text, reply_markup=kb)
            else:
                await message.answer("Эта задача уже недоступна (взята другим исполнителем или удалена).")
        else:
            await message.answer("Ссылка недействительна или ее срок истек.")
        conn.close()
        return

    conn.close()
    # Стандартное приветствие
    if role == "pm":
        await message.answer(f"Привет, {full_name}! Вы вошли как PM.", reply_markup=pm_menu())
    else:
        await message.answer(f"Привет, {full_name}! Вы вошли как исполнитель.", reply_markup=exec_menu())

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("Это бот для распределения задач. Используйте меню для навигации.")
