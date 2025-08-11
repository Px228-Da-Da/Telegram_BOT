from aiogram import Router, types
from aiogram.filters import Command
from config import PM_IDS
from db import get_conn
from utils.time import now_ts
from keyboards import pm_menu, exec_menu

router = Router()

@router.message(Command("start", "help"))
async def cmd_start(message: types.Message):
    tg_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name or ""
    role = "pm" if tg_id in PM_IDS else "exec"

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO users(tg_id, username, full_name, role, is_active)
    VALUES (?, ?, ?, ?, 1)
    ON CONFLICT(tg_id) DO UPDATE SET
        username=excluded.username,
        full_name=excluded.full_name,
        role=excluded.role,
        is_active=1
    """, (tg_id, username, full_name, role))
    conn.commit()
    conn.close()

    if role == "pm":
        await message.answer(f"Привет, {full_name}! Вы вошли как **PM**.", parse_mode="Markdown", reply_markup=pm_menu())
    else:
        await message.answer(f"Привет, {full_name}! Вы вошли как **исполнитель**.", parse_mode="Markdown", reply_markup=exec_menu())
