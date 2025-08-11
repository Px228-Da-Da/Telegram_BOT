# scheduler.py
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from datetime import datetime, timedelta
import pytz

from db import get_conn
from utils.time import now_ts, humanize_ts
from config import REMINDERS_MIN, EXPIRE_SCAN_INTERVAL, PM_IDS, TIMEZONE

# Инициализация планировщика с правильной таймзоной
scheduler = AsyncIOScheduler(timezone=pytz.timezone(TIMEZONE))

def _log_event_within_connection(conn, actor_id, action, task_id=None, meta=None):
    """
    Внутренняя функция для логирования.
    ВАЖНО: Использует переданное соединение и НЕ коммитит изменения.
    """
    conn.execute(
        "INSERT INTO events (ts, actor_id, action, task_id, meta) VALUES (?, ?, ?, ?, ?)",
        (now_ts(), actor_id, action, task_id, meta)
    )

def log_event(actor_id, action, task_id=None, meta=None):
    """
    Универсальная функция для логирования событий в БД.
    Открывает собственное соединение для одного события.
    """
    conn = get_conn()
    try:
        _log_event_within_connection(conn, actor_id, action, task_id, meta)
        conn.commit()
    finally:
        conn.close()


async def send_reminder(bot: Bot, task_id: int, user_id: int, minutes_left: int):
    """Отправляет напоминание исполнителю."""
    conn = get_conn()
    try:
        task = conn.execute("SELECT title FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if task:
            await bot.send_message(
                user_id,
                f"❗️ **Напоминание**: до дедлайна задачи «{task['title']}» осталось {minutes_left} минут."
            )
            _log_event_within_connection(conn, bot.id, "remind", task_id, f"{minutes_left} min left")
            conn.commit()
    finally:
        conn.close()


def schedule_reminders_for_task(bot: Bot, task: dict):
    """
    Планирует все напоминания для взятой задачи.
    Использует timezone-aware datetime объекты для корректной работы.
    """
    # 1. Создаем "осведомленный" объект времени из UTC timestamp
    deadline = datetime.fromtimestamp(task['deadline_ts'], tz=pytz.utc)
    
    # 2. Получаем текущее время, также в UTC
    now_utc = datetime.now(pytz.utc)

    for minutes in REMINDERS_MIN:
        # 3. Вычисляем время напоминания (остается "осведомленным")
        remind_time = deadline - timedelta(minutes=minutes)
        
        # 4. Сравниваем два "осведомленных" объекта времени
        if remind_time > now_utc:
            scheduler.add_job(
                send_reminder,
                "date",
                run_date=remind_time,  # Передаем "осведомленный" объект
                args=[bot, task['id'], task['assigned_to'], minutes],
                id=f"reminder_{task['id']}_{minutes}",
                replace_existing=True
            )

async def check_expired_tasks(bot: Bot):
    """
    Проверяет просроченные задачи, обновляет статус и уведомляет.
    ИСПОЛЬЗУЕТ ОДНО СОЕДИНЕНИЕ НА ВСЮ ОПЕРАЦИЮ.
    """
    conn = get_conn()
    try:
        expired_tasks = conn.execute(
            "SELECT id, title, assigned_to FROM tasks WHERE status IN ('new', 'taken') AND deadline_ts < ?",
            (now_ts(),)
        ).fetchall()

        if not expired_tasks:
            return

        for task in expired_tasks:
            conn.execute("UPDATE tasks SET status = 'expired', updated_at = ? WHERE id = ?", (now_ts(), task['id']))
            _log_event_within_connection(conn, bot.id, "expire", task['id'])

            if task['assigned_to']:
                await bot.send_message(task['assigned_to'], f"⌛️ <b>Время вышло!</b> Задача «{task['title']}» просрочена.")
            
            for pm_id in PM_IDS:
                await bot.send_message(pm_id, f"⌛️ Задача #{task['id']} «{task['title']}» просрочена.")
        
        conn.commit()
    except Exception as e:
        print(f"Ошибка в check_expired_tasks: {e}")
        conn.rollback()
    finally:
        conn.close()


def schedule_existing_tasks(bot: Bot):
    """При старте бота восстанавливает напоминания для активных задач."""
    conn = get_conn()
    try:
        active_tasks = conn.execute("SELECT * FROM tasks WHERE status = 'taken' AND deadline_ts > ?", (now_ts(),)).fetchall()
        if active_tasks:
            print(f"Восстановление {len(active_tasks)} активных задач в планировщике...")
            for task in active_tasks:
                schedule_reminders_for_task(bot, task)
    finally:
        conn.close()
