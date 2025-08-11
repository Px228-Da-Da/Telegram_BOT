# # pm.py
# from aiogram import Router, types, F
# from aiogram.fsm.state import StatesGroup, State
# from aiogram.fsm.context import FSMContext
# from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
# import json
# import os
# from datetime import datetime, timedelta
# import pytz

# from config import PM_IDS, TIMEZONE
# from db import get_conn
# from utils.hash import dedupe_hash
# from utils.time import now_ts
# from keyboards import pm_menu
# from services.export import generate_csv_for_last_week
# from scheduler import log_event

# router = Router()

# class AddTask(StatesGroup):
#     notion_url = State()
#     title = State()
#     level = State()
#     est_hours = State()
#     deadline = State()
#     publish_mode = State()
#     allowed_usernames = State()

# def save_task(data, creator_id):
#     """Сохраняет задачу в БД и логирует событие."""
#     conn = get_conn()
#     cur = conn.cursor()
#     cur.execute("""
#     INSERT INTO tasks(title, notion_url, level, est_hours, publish_mode, deadline_ts,
#                       status, created_by, allowed_usernames,
#                       dedupe_hash, created_at, updated_at)
#     VALUES (?, ?, ?, ?, ?, ?, 'new', ?, ?, ?, ?, ?)
#     """, (
#         data["title"], data["notion_url"], data.get("level"), data.get("est_hours"),
#         data["publish_mode"], data["deadline_ts"], creator_id,
#         data.get("allowed_usernames"), data["dedupe_hash"], now_ts(), now_ts()
#     ))
#     task_id = cur.lastrowid
#     conn.commit()
#     conn.close()
#     log_event(creator_id, "create", task_id)

# @router.callback_query(F.data == "pm_add")
# async def pm_add_start(callback: types.CallbackQuery, state: FSMContext):
#     if callback.from_user.id not in PM_IDS:
#         return await callback.answer("Нет доступа", show_alert=True)
#     await state.set_state(AddTask.notion_url)
#     await callback.message.answer("Введите Notion URL задачи:")
#     await callback.answer()

# @router.message(AddTask.notion_url)
# async def addtask_url(message: types.Message, state: FSMContext):
#     url = message.text.strip()
#     h = dedupe_hash(url)
#     conn = get_conn()
#     row = conn.execute("SELECT id, title FROM tasks WHERE dedupe_hash=? AND status IN ('new','taken')", (h,)).fetchone()
#     conn.close()
#     if row:
#         await message.answer(f"❗ Такая задача уже есть: #{row['id']} — {row['title']}")
#         return await state.clear()
    
#     await state.update_data(notion_url=url, dedupe_hash=h)
#     await state.set_state(AddTask.title)
#     await message.answer("Введите заголовок задачи:")

# @router.message(AddTask.title)
# async def addtask_title(message: types.Message, state: FSMContext):
#     await state.update_data(title=message.text.strip())
#     await state.set_state(AddTask.level)
#     kb = InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="L1", callback_data="level_L1"), InlineKeyboardButton(text="L2", callback_data="level_L2"), InlineKeyboardButton(text="L3", callback_data="level_L3")],
#         [InlineKeyboardButton(text="L4", callback_data="level_L4"), InlineKeyboardButton(text="L5", callback_data="level_L5")],
#         [InlineKeyboardButton(text="easy", callback_data="level_easy"), InlineKeyboardButton(text="med", callback_data="level_med"), InlineKeyboardButton(text="hard", callback_data="level_hard")]
#     ])
#     await message.answer("Выберите уровень задачи:", reply_markup=kb)

# @router.callback_query(F.data.startswith("level_"), AddTask.level)
# async def addtask_level_btn(callback: types.CallbackQuery, state: FSMContext):
#     level = callback.data.replace("level_", "")
#     await state.update_data(level=level)
#     await state.set_state(AddTask.est_hours)
#     await callback.message.edit_text("Введите оценку часов (или напишите 0, если пропустить):")
#     await callback.answer()

# @router.message(AddTask.level)
# async def addtask_level_text(message: types.Message, state: FSMContext):
#     await state.update_data(level=message.text.strip())
#     await state.set_state(AddTask.est_hours)
#     await message.answer("Введите оценку часов (или напишите 0, если пропустить):")

# @router.message(AddTask.est_hours)
# async def addtask_hours(message: types.Message, state: FSMContext):
#     try:
#         hours = float(message.text.strip())
#         if hours == 0: hours = None
#     except:
#         hours = None
#     await state.update_data(est_hours=hours)
#     await state.set_state(AddTask.deadline)
#     await message.answer("Дедлайн: +6h, +30m или YYYY-MM-DD HH:MM:")

# @router.message(AddTask.deadline)
# async def addtask_deadline(message: types.Message, state: FSMContext):
#     txt = message.text.strip()
#     deadline_ts = None
#     tz = pytz.timezone(TIMEZONE)

#     if txt.startswith("+") and txt.endswith("h"):
#         try:
#             hours = int(txt[1:-1])
#             deadline_ts = now_ts() + hours * 3600
#         except: pass
#     elif txt.startswith("+") and txt.endswith("m"):
#         try:
#             mins = int(txt[1:-1])
#             deadline_ts = now_ts() + mins * 60
#         except: pass
#     else:
#         try:
#             dt = datetime.strptime(txt, "%Y-%m-%d %H:%M")
#             deadline_ts = int(tz.localize(dt).timestamp())
#         except: pass

#     if not deadline_ts:
#         return await message.answer("Неверный формат. Пример: `+6h` или `2025-08-12 15:00`")

#     await state.update_data(deadline_ts=deadline_ts)
#     await state.set_state(AddTask.publish_mode)
#     kb = InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="Открытая", callback_data="pm_pub_open")],
#         [InlineKeyboardButton(text="Точечная", callback_data="pm_pub_direct")]
#     ])
#     await message.answer("Выберите тип публикации:", reply_markup=kb)

# @router.callback_query(F.data.startswith("pm_pub_"))
# async def addtask_pubmode(callback: types.CallbackQuery, state: FSMContext):
#     mode = callback.data.replace("pm_pub_", "")
#     await state.update_data(publish_mode=mode)
#     if mode == "direct":
#         await state.set_state(AddTask.allowed_usernames)
#         await callback.message.edit_text("Список @username через пробел:")
#     else:
#         data = await state.get_data()
#         save_task(data, callback.from_user.id)
#         await state.clear()
#         await callback.message.edit_text("✅ Задача создана", reply_markup=pm_menu())
#     await callback.answer()

# @router.message(AddTask.allowed_usernames)
# async def addtask_direct_usernames(message: types.Message, state: FSMContext):
#     usernames = [u.strip().lstrip("@") for u in message.text.split() if u.strip()]
#     await state.update_data(allowed_usernames=json.dumps(usernames))
#     data = await state.get_data()
#     save_task(data, message.from_user.id)
#     await state.clear()
#     await message.answer("✅ Задача создана (точечная)", reply_markup=pm_menu())

# @router.callback_query(F.data == "pm_export")
# async def pm_export_csv(callback: types.CallbackQuery):
#     await callback.answer("Начинаю формировать отчет за неделю...")
#     try:
#         file_path = generate_csv_for_last_week()
#         doc = FSInputFile(file_path)
#         await callback.message.answer_document(doc, caption="📊 Ваш отчет по задачам за последнюю неделю.")
#         os.remove(file_path)
#     except Exception as e:
#         await callback.message.answer("❌ Произошла ошибка при формировании отчета.")
#         print(f"Error generating CSV: {e}")

# @router.callback_query(F.data.startswith("pm_accept_"))
# async def pm_accept(callback: types.CallbackQuery):
#     task_id = int(callback.data.split("_")[2])
#     conn = get_conn()
#     conn.execute("UPDATE tasks SET status='done', updated_at=? WHERE id=? AND status='taken'", (now_ts(), task_id))
#     conn.commit()
#     conn.close()
#     log_event(callback.from_user.id, "done", task_id)
#     await callback.answer("Задача принята!", show_alert=True)
#     await callback.message.edit_text(f"✅ Задача #{task_id} — принята.")

# @router.callback_query(F.data.startswith("pm_return_"))
# async def pm_return(callback: types.CallbackQuery):
#     task_id = int(callback.data.split("_")[2])
#     conn = get_conn()

#     # Получаем данные о задаче, чтобы знать, кого уведомлять
#     task = conn.execute("SELECT title, assigned_to FROM tasks WHERE id=?", (task_id,)).fetchone()

#     if not task or not task['assigned_to']:
#         conn.close()
#         await callback.answer("Не удалось найти задачу или исполнителя.", show_alert=True)
#         return

#     # Обновляем статус и время
#     conn.execute("UPDATE tasks SET status='taken', updated_at=? WHERE id=?", (now_ts(), task_id))
#     conn.commit()
#     conn.close()

#     # Логируем событие
#     log_event(callback.from_user.id, "return", task_id)

#     # Уведомляем исполнителя
#     executor_id = task['assigned_to']
#     try:
#         await callback.bot.send_message(
#             executor_id,
#             f"❌ **Задача возвращена на доработку**\n\n"
#             f"Ваша задача «{task['title']}» была возвращена PM. "
#             f"Проверьте комментарии в Notion или свяжитесь с PM для уточнений."
#         )
#     except Exception as e:
#         print(f"Не удалось уведомить исполнителя {executor_id} о возврате задачи {task_id}: {e}")
#         await callback.message.answer(f"⚠️ Не удалось уведомить исполнителя о возврате задачи #{task_id}.")

#     # Отвечаем PM
#     await callback.answer("Задача возвращена исполнителю.", show_alert=True)
#     await callback.message.edit_text(f"❌ Задача #{task_id} — возвращена исполнителю.")
# pm.py
from aiogram import Router, types, F
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
import json
import os
from datetime import datetime, timedelta
import pytz

from config import PM_IDS, TIMEZONE
from db import get_conn
from utils.hash import dedupe_hash
from utils.time import now_ts, humanize_ts
from keyboards import pm_menu
from services.export import generate_csv_for_last_week
from scheduler import log_event

router = Router()

# --- Машины состояний (FSM) ---

class AddTask(StatesGroup):
    notion_url = State()
    title = State()
    level = State()
    est_hours = State()
    deadline = State()
    publish_mode = State()
    allowed_usernames = State()

class SearchTask(StatesGroup):
    query = State()


# --- Вспомогательные функции ---

def save_task(data, creator_id):
    """Сохраняет задачу в БД и логирует событие."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO tasks(title, notion_url, level, est_hours, publish_mode, deadline_ts,
                      status, created_by, allowed_usernames,
                      dedupe_hash, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, 'new', ?, ?, ?, ?, ?)
    """, (
        data["title"], data["notion_url"], data.get("level"), data.get("est_hours"),
        data["publish_mode"], data["deadline_ts"], creator_id,
        data.get("allowed_usernames"), data["dedupe_hash"], now_ts(), now_ts()
    ))
    task_id = cur.lastrowid
    conn.commit()
    conn.close()
    log_event(creator_id, "create", task_id)

async def display_task_list(message: types.Message, tasks: list, title: str):
    """Универсальная функция для отображения списка задач."""
    if not tasks:
        await message.answer(f"Нет задач в категории «{title}».")
        return

    await message.answer(f"<b>{title}:</b>")
    for t in tasks:
        # ИСПРАВЛЕННАЯ СТРОКА:
        assignee_info = f"Исполнитель: @{t['assignee_username']}\n" if 'assignee_username' in t.keys() and t['assignee_username'] else ""
        
        text = (
            f"<b>#{t['id']} — {t['title']}</b>\n"
            f"Статус: <code>{t['status']}</code>\n"
            f"{assignee_info}"
            f"Уровень: {t['level']}\n"
            f"Дедлайн: {humanize_ts(t['deadline_ts']) if t['deadline_ts'] else 'Не указан'}"
        )
        await message.answer(text)


# --- Обработчики меню PM ---

@router.callback_query(F.data == "pm_queue")
async def pm_queue(callback: types.CallbackQuery):
    """Показывает задачи в очереди (статус 'new')."""
    conn = get_conn()
    tasks = conn.execute("SELECT * FROM tasks WHERE status = 'new' ORDER BY created_at ASC").fetchall()
    conn.close()
    await display_task_list(callback.message, tasks, "📋 Задачи в очереди")
    await callback.answer()


@router.callback_query(F.data == "pm_inprogress")
async def pm_inprogress(callback: types.CallbackQuery):
    """Показывает задачи в работе (статус 'taken')."""
    conn = get_conn()
    tasks = conn.execute("""
        SELECT t.*, u.username as assignee_username
        FROM tasks t
        JOIN users u ON t.assigned_to = u.tg_id
        WHERE t.status = 'taken'
        ORDER BY t.deadline_ts ASC
    """).fetchall()
    conn.close()
    await display_task_list(callback.message, tasks, "⏳ Задачи в работе")
    await callback.answer()


@router.callback_query(F.data == "pm_search")
async def pm_search_start(callback: types.CallbackQuery, state: FSMContext):
    """Запускает процесс поиска."""
    await state.set_state(SearchTask.query)
    await callback.message.answer("Введите текст для поиска (по заголовку, URL или @username исполнителя):")
    await callback.answer()


@router.message(SearchTask.query)
async def pm_search_process(message: types.Message, state: FSMContext):
    """Выполняет поиск и выводит результаты."""
    await state.clear()
    query_text = f"%{message.text.strip()}%"
    username_query = message.text.strip().lstrip('@')

    conn = get_conn()
    tasks = conn.execute("""
        SELECT t.*, u.username as assignee_username
        FROM tasks t
        LEFT JOIN users u ON t.assigned_to = u.tg_id
        WHERE t.title LIKE ? OR t.notion_url LIKE ? OR u.username = ?
        ORDER BY t.updated_at DESC
        LIMIT 20
    """, (query_text, query_text, username_query)).fetchall()
    conn.close()
    
    await display_task_list(message, tasks, f"🔎 Результаты поиска по «{message.text}»")


# --- Мастер добавления задачи ---

@router.callback_query(F.data == "pm_add")
async def pm_add_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in PM_IDS:
        return await callback.answer("Нет доступа", show_alert=True)
    await state.set_state(AddTask.notion_url)
    await callback.message.answer("Введите Notion URL задачи:")
    await callback.answer()

@router.message(AddTask.notion_url)
async def addtask_url(message: types.Message, state: FSMContext):
    url = message.text.strip()
    h = dedupe_hash(url)
    conn = get_conn()
    row = conn.execute("SELECT id, title FROM tasks WHERE dedupe_hash=? AND status IN ('new','taken')", (h,)).fetchone()
    conn.close()
    if row:
        await message.answer(f"❗ Такая задача уже есть: #{row['id']} — {row['title']}")
        return await state.clear()
    
    await state.update_data(notion_url=url, dedupe_hash=h)
    await state.set_state(AddTask.title)
    await message.answer("Введите заголовок задачи:")

@router.message(AddTask.title)
async def addtask_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(AddTask.level)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="L1", callback_data="level_L1"), InlineKeyboardButton(text="L2", callback_data="level_L2"), InlineKeyboardButton(text="L3", callback_data="level_L3")],
        [InlineKeyboardButton(text="L4", callback_data="level_L4"), InlineKeyboardButton(text="L5", callback_data="level_L5")],
        [InlineKeyboardButton(text="easy", callback_data="level_easy"), InlineKeyboardButton(text="med", callback_data="level_med"), InlineKeyboardButton(text="hard", callback_data="level_hard")]
    ])
    await message.answer("Выберите уровень задачи:", reply_markup=kb)

@router.callback_query(F.data.startswith("level_"), AddTask.level)
async def addtask_level_btn(callback: types.CallbackQuery, state: FSMContext):
    level = callback.data.replace("level_", "")
    await state.update_data(level=level)
    await state.set_state(AddTask.est_hours)
    await callback.message.edit_text("Введите оценку часов (или напишите 0, если пропустить):")
    await callback.answer()

@router.message(AddTask.level)
async def addtask_level_text(message: types.Message, state: FSMContext):
    await state.update_data(level=message.text.strip())
    await state.set_state(AddTask.est_hours)
    await message.answer("Введите оценку часов (или напишите 0, если пропустить):")

@router.message(AddTask.est_hours)
async def addtask_hours(message: types.Message, state: FSMContext):
    try:
        hours = float(message.text.strip())
        if hours == 0: hours = None
    except:
        hours = None
    await state.update_data(est_hours=hours)
    await state.set_state(AddTask.deadline)
    await message.answer("Дедлайн: +6h, +30m или YYYY-MM-DD HH:MM:")

@router.message(AddTask.deadline)
async def addtask_deadline(message: types.Message, state: FSMContext):
    txt = message.text.strip()
    deadline_ts = None
    tz = pytz.timezone(TIMEZONE)

    if txt.startswith("+") and txt.endswith("h"):
        try:
            hours = int(txt[1:-1])
            deadline_ts = now_ts() + hours * 3600
        except: pass
    elif txt.startswith("+") and txt.endswith("m"):
        try:
            mins = int(txt[1:-1])
            deadline_ts = now_ts() + mins * 60
        except: pass
    else:
        try:
            dt = datetime.strptime(txt, "%Y-%m-%d %H:%M")
            deadline_ts = int(tz.localize(dt).timestamp())
        except: pass

    if not deadline_ts:
        return await message.answer("Неверный формат. Пример: `+6h` или `2025-08-12 15:00`")

    await state.update_data(deadline_ts=deadline_ts)
    await state.set_state(AddTask.publish_mode)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открытая", callback_data="pm_pub_open")],
        [InlineKeyboardButton(text="Точечная", callback_data="pm_pub_direct")]
    ])
    await message.answer("Выберите тип публикации:", reply_markup=kb)

@router.callback_query(F.data.startswith("pm_pub_"))
async def addtask_pubmode(callback: types.CallbackQuery, state: FSMContext):
    mode = callback.data.replace("pm_pub_", "")
    await state.update_data(publish_mode=mode)
    if mode == "direct":
        await state.set_state(AddTask.allowed_usernames)
        await callback.message.edit_text("Список @username через пробел:")
    else:
        data = await state.get_data()
        save_task(data, callback.from_user.id)
        await state.clear()
        await callback.message.edit_text("✅ Задача создана", reply_markup=pm_menu())
    await callback.answer()

@router.message(AddTask.allowed_usernames)
async def addtask_direct_usernames(message: types.Message, state: FSMContext):
    usernames = [u.strip().lstrip("@") for u in message.text.split() if u.strip()]
    await state.update_data(allowed_usernames=json.dumps(usernames))
    data = await state.get_data()
    save_task(data, message.from_user.id)
    await state.clear()
    await message.answer("✅ Задача создана (точечная)", reply_markup=pm_menu())


# --- Обработчики других действий PM ---

@router.callback_query(F.data == "pm_export")
async def pm_export_csv(callback: types.CallbackQuery):
    await callback.answer("Начинаю формировать отчет за неделю...")
    try:
        file_path = generate_csv_for_last_week()
        doc = FSInputFile(file_path)
        await callback.message.answer_document(doc, caption="📊 Ваш отчет по задачам за последнюю неделю.")
        os.remove(file_path)
    except Exception as e:
        await callback.message.answer("❌ Произошла ошибка при формировании отчета.")
        print(f"Error generating CSV: {e}")

@router.callback_query(F.data.startswith("pm_accept_"))
async def pm_accept(callback: types.CallbackQuery):
    task_id = int(callback.data.split("_")[2])
    conn = get_conn()
    conn.execute("UPDATE tasks SET status='done', updated_at=? WHERE id=? AND status='taken'", (now_ts(), task_id))
    conn.commit()
    conn.close()
    log_event(callback.from_user.id, "done", task_id)
    await callback.answer("Задача принята!", show_alert=True)
    await callback.message.edit_text(f"✅ Задача #{task_id} — принята.")

@router.callback_query(F.data.startswith("pm_return_"))
async def pm_return(callback: types.CallbackQuery):
    task_id = int(callback.data.split("_")[2])
    conn = get_conn()
    task = conn.execute("SELECT title, assigned_to FROM tasks WHERE id=?", (task_id,)).fetchone()

    if not task or not task['assigned_to']:
        conn.close()
        await callback.answer("Не удалось найти задачу или исполнителя.", show_alert=True)
        return

    conn.execute("UPDATE tasks SET status='taken', updated_at=? WHERE id=?", (now_ts(), task_id))
    conn.commit()
    conn.close()
    log_event(callback.from_user.id, "return", task_id)

    executor_id = task['assigned_to']
    try:
        await callback.bot.send_message(
            executor_id,
            f"❌ <b>Задача возвращена на доработку</b>\n\n"
            f"Ваша задача «{task['title']}» была возвращена PM. "
            f"Проверьте комментарии в Notion или свяжитесь с PM для уточнений."
        )
    except Exception as e:
        print(f"Не удалось уведомить исполнителя {executor_id} о возврате задачи {task_id}: {e}")
        await callback.message.answer(f"⚠️ Не удалось уведомить исполнителя о возврате задачи #{task_id}.")

    await callback.answer("Задача возвращена исполнителю.", show_alert=True)
    await callback.message.edit_text(f"❌ Задача #{task_id} — возвращена исполнителю.")
