"""Stockage SQLite : rappels (uniques et quotidiens) et fuseaux horaires."""
import os
import sqlite3
import time
from contextlib import closing

DB_PATH = os.getenv("DB_PATH", "bot.db")


def _connect():
    return sqlite3.connect(DB_PATH)


def init_db():
    with closing(_connect()) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id    INTEGER NOT NULL,
                text       TEXT    NOT NULL,
                due_ts     REAL    NOT NULL,
                daily_time TEXT
            )
            """
        )
        # Migration : anciennes bases créées avant l'ajout des rappels quotidiens
        columns = {row[1] for row in conn.execute("PRAGMA table_info(reminders)")}
        if "daily_time" not in columns:
            conn.execute("ALTER TABLE reminders ADD COLUMN daily_time TEXT")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                chat_id  INTEGER PRIMARY KEY,
                timezone TEXT NOT NULL
            )
            """
        )


# ---------- Rappels ----------

def add_reminder(chat_id: int, text: str, minutes: float) -> tuple[int, float]:
    """Rappel unique. Renvoie (id, timestamp d'échéance)."""
    due_ts = time.time() + minutes * 60
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO reminders (chat_id, text, due_ts) VALUES (?, ?, ?)",
            (chat_id, text, due_ts),
        )
        return cur.lastrowid, due_ts


def add_daily(chat_id: int, text: str, hhmm: str) -> int:
    """Rappel quotidien à l'heure 'HH:MM' (dans le fuseau de l'utilisateur)."""
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO reminders (chat_id, text, due_ts, daily_time) VALUES (?, ?, 0, ?)",
            (chat_id, text, hhmm),
        )
        return cur.lastrowid


def delete_reminder(reminder_id: int, chat_id: int | None = None) -> bool:
    """Supprime un rappel. Si chat_id est donné, vérifie qu'il appartient à ce chat."""
    query = "DELETE FROM reminders WHERE id = ?"
    params: tuple = (reminder_id,)
    if chat_id is not None:
        query += " AND chat_id = ?"
        params += (chat_id,)
    with closing(_connect()) as conn, conn:
        return conn.execute(query, params).rowcount > 0


def get_all_reminders() -> list[tuple[int, int, str, float, str | None]]:
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT id, chat_id, text, due_ts, daily_time FROM reminders ORDER BY due_ts, id"
        ).fetchall()


def get_chat_reminders(chat_id: int) -> list[tuple[int, str, float, str | None]]:
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT id, text, due_ts, daily_time FROM reminders "
            "WHERE chat_id = ? ORDER BY due_ts, id",
            (chat_id,),
        ).fetchall()


# ---------- Fuseaux horaires ----------

def set_timezone(chat_id: int, tz_name: str):
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO users (chat_id, timezone) VALUES (?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET timezone = excluded.timezone",
            (chat_id, tz_name),
        )


def get_timezone(chat_id: int) -> str | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT timezone FROM users WHERE chat_id = ?", (chat_id,)
        ).fetchone()
    return row[0] if row else None
