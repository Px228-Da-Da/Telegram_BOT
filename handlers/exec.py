# exec.py
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import json

from config import MAX_ACTIVE_TASKS, PM_IDS
from db import get_conn
from keyboards import pm_review_kb
from utils.time import now_ts, humanize_ts
from scheduler import schedule_reminders_for_task, log_event

router = Router()


def task_card_kb(task_id: int, mode: str):
    """
    Создает клавиатуру для карточки задачи в зависимости от ее статуса.
    """
    if mode == "open" or mode == "direct":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🖐 Принять", callback_data=f"exec_take_{task_id}")]
        ])
    elif mode == "taken":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Сдать", callback_data=f"exec_submit_{task_id}")],
            [InlineKeyboardButton(text="🚫 Отказаться", callback_data=f"exec_drop_{task_id}")]
        ])
    return None

# --- Обработчики меню ---

@router.callback_query(F.data == "exec_open")
async def exec_open(callback: types.CallbackQuery):
    """Показывает список открытых задач, доступных для всех."""
    conn = get_conn()
    tasks = conn.execute("""
        SELECT * FROM tasks
        WHERE status='new' AND publish_mode='open'
        ORDER BY deadline_ts ASC
    """).fetchall()
    conn.close()

    if not tasks:
        await callback.message.answer("Нет доступных открытых задач.")
    else:
        await callback.message.answer("<b>Доступные открытые задачи:</b>")
        for t in tasks:
            text = (f"<b>#{t['id']} — {t['title']}</b>\n"
                    f"Уровень: {t['level']}\n"
                    f"Дедлайн: {humanize_ts(t['deadline_ts'])}")
            await callback.message.answer(text, reply_markup=task_card_kb(t['id'], "open"))
    await callback.answer()


@router.callback_query(F.data == "exec_direct")
async def exec_direct(callback: types.CallbackQuery):
    """Показывает задачи, адресованные конкретному исполнителю."""
    username = (callback.from_user.username or "").lower()
    if not username:
        await callback.message.answer("У вас нет username в Telegram, прямые назначения недоступны.")
        return await callback.answer()

    conn = get_conn()
    all_tasks = conn.execute("""
        SELECT * FROM tasks
        WHERE status='new' AND publish_mode='direct'
    """).fetchall()
    conn.close()

    my_tasks = []
    for t in all_tasks:
        try:
            allowed = json.loads(t["allowed_usernames"] or "[]")
            if username in [a.lower() for a in allowed]:
                my_tasks.append(t)
        except:
            continue

    if not my_tasks:
        await callback.message.answer("Нет назначенных вам задач.")
    else:
        await callback.message.answer("<b>Задачи, назначенные вам:</b>")
        for t in my_tasks:
            text = (f"<b>#{t['id']} — {t['title']}</b>\n"
                    f"Уровень: {t['level']}\n"
                    f"Дедлайн: {humanize_ts(t['deadline_ts'])}")
            await callback.message.answer(text, reply_markup=task_card_kb(t['id'], "direct"))
    await callback.answer()


@router.callback_query(F.data == "exec_my")
async def exec_my(callback: types.CallbackQuery):
    """Показывает задачи, которые исполнитель уже взял в работу."""
    uid = callback.from_user.id
    conn = get_conn()
    tasks = conn.execute("SELECT * FROM tasks WHERE status='taken' AND assigned_to=?", (uid,)).fetchall()
    conn.close()

    if not tasks:
        await callback.message.answer("У вас нет активных задач.")
    else:
        await callback.message.answer("<b>Ваши активные задачи:</b>")
        for t in tasks:
            text = (f"<b>#{t['id']} — {t['title']}</b>\n"
                    f"Уровень: {t['level']}\n"
                    f"Дедлайн: {humanize_ts(t['deadline_ts'])}")
            await callback.message.answer(text, reply_markup=task_card_kb(t['id'], "taken"))
    await callback.answer()


# --- Обработчики действий ---

@router.callback_query(F.data.startswith("exec_take_"))
async def exec_take(callback: types.CallbackQuery):
    """Обрабатывает взятие задачи, проверяет лимиты и ставит напоминания."""
    task_id = int(callback.data.split("_")[2])
    uid = callback.from_user.id

    conn = get_conn()
    cur = conn.cursor()

    active_count = cur.execute("SELECT COUNT(*) FROM tasks WHERE status='taken' AND assigned_to=?", (uid,)).fetchone()[0]
    if active_count >= MAX_ACTIVE_TASKS:
        conn.close()
        await callback.answer(f"У вас уже максимум активных задач ({MAX_ACTIVE_TASKS}).", show_alert=True)
        return

    try:
        cur.execute("BEGIN IMMEDIATE")
        task = cur.execute("SELECT * FROM tasks WHERE id=? AND status='new'", (task_id,)).fetchone()
        
        if not task:
            conn.rollback()
            await callback.answer("Задача уже недоступна или была взята другим исполнителем.", show_alert=True)
            await callback.message.delete()
            return

        cur.execute("UPDATE tasks SET status='taken', assigned_to=?, updated_at=? WHERE id=?", (uid, now_ts(), task_id))
        conn.commit()
        
        log_event(uid, "take", task_id)
        
        updated_task = cur.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        schedule_reminders_for_task(callback.bot, updated_task)
        
        await callback.message.edit_text(f"✅ Вы взяли задачу: «{task['title']}»")
        await callback.answer("Задача принята!", show_alert=True)
    except Exception as e:
        conn.rollback()
        await callback.answer("Произошла ошибка при взятии задачи.", show_alert=True)
        print(f"Error in exec_take: {e}")
    finally:
        conn.close()


@router.callback_query(F.data.startswith("exec_drop_"))
async def exec_drop(callback: types.CallbackQuery):
    """Обрабатывает отказ от задачи."""
    task_id = int(callback.data.split("_")[2])
    uid = callback.from_user.id
    
    conn = get_conn()
    task = conn.execute("SELECT id, title FROM tasks WHERE id=? AND assigned_to=?", (task_id, uid)).fetchone()

    if not task:
        conn.close()
        await callback.answer("Не удалось найти эту задачу.", show_alert=True)
        return

    conn.execute("UPDATE tasks SET status='dropped', updated_at=? WHERE id=? AND assigned_to=? AND status='taken'", (now_ts(), task_id, uid))
    conn.commit()
    conn.close()

    log_event(uid, "drop", task_id)

    username = callback.from_user.username or 'пользователь'
    text = f"🚫 Исполнитель @{username} отказался от задачи #{task['id']}.\nЗаголовок: {task['title']}"
    for pm_id in PM_IDS:
        try:
            await callback.bot.send_message(pm_id, text)
        except Exception as e:
            print(f"Не удалось отправить уведомление PM {pm_id}: {e}")

    await callback.message.edit_text(f"Вы отказались от задачи #{task['id']}.")
    await callback.answer("Вы отказались от задачи.", show_alert=True)


@router.callback_query(F.data.startswith("exec_submit_"))
async def exec_submit(callback: types.CallbackQuery):
    """Отправляет задачу на проверку PM."""
    task_id = int(callback.data.split("_")[2])
    uid = callback.from_user.id

    conn = get_conn()
    task = conn.execute("SELECT id, title FROM tasks WHERE id=? AND assigned_to=? AND status='taken'", (task_id, uid)).fetchone()
    conn.close()

    if not task:
        await callback.answer("Невозможно сдать эту задачу.", show_alert=True)
        return
        
    log_event(uid, "submit", task_id)

    username = callback.from_user.username or 'пользователь'
    text_for_pm = f"📥 Сдача задачи #{task['id']} от @{username}\nЗаголовок: {task['title']}\n\nПринять или вернуть?"
    
    for pm_id in PM_IDS:
        try:
            await callback.bot.send_message(pm_id, text_for_pm, reply_markup=pm_review_kb(task['id']))
        except Exception as e:
            print(f"Не удалось отправить уведомление PM {pm_id}: {e}")

    await callback.message.edit_text(f"✅ Задача «{task['title']}» отправлена на проверку.")
    await callback.answer("Задача отправлена на проверку PM.", show_alert=True)
