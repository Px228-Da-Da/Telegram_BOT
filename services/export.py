# services/export.py
import csv
import os
from datetime import datetime, timedelta

from db import get_conn
from config import EXPORT_DIR
from utils.time import now_ts, humanize_ts

def generate_csv_for_last_week() -> str:
    """Генерирует CSV-отчет за последние 7 дней и возвращает путь к файлу."""
    end_ts = now_ts()
    start_ts = int((datetime.now() - timedelta(days=7)).timestamp())

    conn = get_conn()
    # Запрос для получения задач с именем исполнителя
    tasks = conn.execute("""
        SELECT
            t.id, t.title, t.notion_url, u.username as assignee_username, t.status,
            t.level, t.est_hours, t.deadline_ts, t.created_at, t.updated_at
        FROM tasks t
        LEFT JOIN users u ON t.assigned_to = u.tg_id
        WHERE t.created_at >= ?
        ORDER BY t.created_at DESC
    """, (start_ts,)).fetchall()
    conn.close()

    os.makedirs(EXPORT_DIR, exist_ok=True)
    file_path = os.path.join(EXPORT_DIR, f"report_{now_ts()}.csv")

    headers = ["id", "title", "notion_url", "assignee_username", "status", "level", "est_hours", "deadline", "created_at", "updated_at"]

    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for task in tasks:
            writer.writerow([
                task['id'], task['title'], task['notion_url'],
                task['assignee_username'] or '', task['status'], task['level'],
                task['est_hours'],
                humanize_ts(task['deadline_ts']) if task['deadline_ts'] else '',
                humanize_ts(task['created_at']) if task['created_at'] else '',
                humanize_ts(task['updated_at']) if task['updated_at'] else ''
            ])
            
    return file_path