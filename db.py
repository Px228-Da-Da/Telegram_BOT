import sqlite3
import os
from config import DB_PATH

def get_conn():
    """
    Устанавливает соединение с БД.
    - timeout=15 решает проблему 'database is locked'.
    - PRAGMA journal_mode=WAL включает режим Write-Ahead Logging для лучшей
      производительности при одновременном доступе.
    """
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    # Включаем WAL-режим. Это нужно сделать один раз для файла БД.
    # Последующие вызовы просто подтвердят, что режим уже включен.
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    """Инициализирует таблицы в базе данных."""
    # Убедимся, что папка data существует
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = get_conn()
    cur = conn.cursor()

    # Таблица для хранения информации о пользователях
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY,
      tg_id INTEGER UNIQUE NOT NULL,
      username TEXT,
      full_name TEXT,
      role TEXT CHECK(role IN ('pm','exec')) NOT NULL,
      is_active INTEGER DEFAULT 1
    )
    """)

    # Таблица для хранения задач
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks(
      id INTEGER PRIMARY KEY,
      title TEXT NOT NULL,
      notion_url TEXT NOT NULL,
      level TEXT,
      est_hours REAL,
      publish_mode TEXT CHECK(publish_mode IN ('open','direct')) NOT NULL,
      deadline_ts INTEGER,
      status TEXT CHECK(status IN ('new','taken','done','dropped','expired')) DEFAULT 'new',
      assigned_to INTEGER,
      created_by INTEGER NOT NULL,
      allowed_usernames TEXT,
      dedupe_hash TEXT,
      created_at INTEGER,
      updated_at INTEGER
    )
    """)

    # Уникальный индекс для предотвращения дублей активных задач
    cur.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_notion_active
    ON tasks(dedupe_hash)
    WHERE status IN ('new','taken')
    """)

    # Таблица для логирования всех действий в системе (аудит)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS events(
      id INTEGER PRIMARY KEY,
      ts INTEGER,
      actor_id INTEGER,
      action TEXT,
      task_id INTEGER,
      meta TEXT
    )
    """)

    conn.commit()
    conn.close()
    print(f"База инициализирована в {DB_PATH}")
