# database.py
import logging
import sqlite3
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from config import DATABASE_PATH
from utils import get_current_sunday, week_label_for_sunday

logger = logging.getLogger(__name__)


def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_columns(conn, table: str):
    c = conn.cursor()
    c.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in c.fetchall()]


def _migrate_legacy_if_needed(conn):
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='members'")
    if not c.fetchone():
        return
    cols = _table_columns(conn, "members")
    if "rotation_order" not in cols:
        return

    c.execute("SELECT * FROM members")
    legacy_members = []
    for row in c.fetchall():
        d = dict(row)
        legacy_members.append(
            {
                "telegram_id": d["telegram_id"],
                "username": d.get("username"),
                "display_name": d["display_name"],
                "is_active": d.get("is_active", 1),
                "role": d.get("role", "member"),
                "joined_at": d.get("joined_at"),
            }
        )

    c.executescript(
        """
        DROP TABLE IF EXISTS week_joiners;
        DROP TABLE IF EXISTS reminders_log;
        DROP TABLE IF EXISTS weeks;
        DROP TABLE IF EXISTS members;
        """
    )
    conn.commit()

    _create_tables(conn)
    conn.commit()

    for m in legacy_members:
        c.execute(
            """
            INSERT INTO members (telegram_id, username, display_name, group_id, is_active, role, joined_at)
            VALUES (?, ?, ?, NULL, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
            """,
            (
                m["telegram_id"],
                m.get("username"),
                m["display_name"],
                m.get("is_active", 1),
                m.get("role", "member"),
                m.get("joined_at"),
            ),
        )
    conn.commit()


def _create_tables(conn):
    c = conn.cursor()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            display_name TEXT NOT NULL,
            group_id INTEGER,
            is_active INTEGER DEFAULT 1,
            role TEXT DEFAULT 'member',
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS weeks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_label TEXT UNIQUE NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            assigned_group_id INTEGER,
            pinned_message_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS week_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_id INTEGER NOT NULL,
            telegram_id INTEGER NOT NULL,
            username TEXT,
            display_name TEXT NOT NULL,
            is_assigned INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0,
            completed_at TEXT,
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(week_id, telegram_id),
            FOREIGN KEY (week_id) REFERENCES weeks(id)
        );

        CREATE TABLE IF NOT EXISTS reminders_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_id INTEGER NOT NULL,
            reminder_type TEXT NOT NULL,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(week_id, reminder_type),
            FOREIGN KEY (week_id) REFERENCES weeks(id)
        );
        """
    )


def init_db():
    conn = get_connection()
    _migrate_legacy_if_needed(conn)
    _create_tables(conn)
    conn.commit()
    conn.close()


# --- MEMBERS ---


def add_member(telegram_id, display_name, username=None, role="member"):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO members (telegram_id, username, display_name, role)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            display_name = excluded.display_name,
            username = COALESCE(excluded.username, members.username)
        """,
        (telegram_id, username, display_name, role),
    )
    conn.commit()
    conn.close()


def set_member_group(telegram_id, group_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE members SET group_id = ? WHERE telegram_id = ?",
        (group_id, telegram_id),
    )
    conn.commit()
    conn.close()


def get_members_by_group(group_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM members WHERE is_active = 1 AND group_id = ? ORDER BY display_name",
        (group_id,),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def get_all_active_members():
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT * FROM members
        WHERE is_active = 1
        ORDER BY group_id IS NULL, group_id, display_name
        """
    )
    rows = c.fetchall()
    conn.close()
    return rows


def get_member_by_telegram_id(telegram_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM members WHERE telegram_id = ?", (telegram_id,))
    row = c.fetchone()
    conn.close()
    return row


def get_member_by_username(username: str):
    if not username:
        return None
    u = username.lstrip("@").strip()
    if not u:
        return None
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM members WHERE username IS NOT NULL AND lower(username) = lower(?)",
        (u,),
    )
    row = c.fetchone()
    conn.close()
    return row


def set_member_active(telegram_id, is_active: bool):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE members SET is_active = ? WHERE telegram_id = ?",
        (1 if is_active else 0, telegram_id),
    )
    conn.commit()
    conn.close()


def swap_member_groups(telegram_id_1, telegram_id_2):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT telegram_id, group_id FROM members WHERE telegram_id IN (?, ?)",
        (telegram_id_1, telegram_id_2),
    )
    rows = {r["telegram_id"]: r["group_id"] for r in c.fetchall()}
    if telegram_id_1 not in rows or telegram_id_2 not in rows:
        conn.close()
        return False
    g1, g2 = rows[telegram_id_1], rows[telegram_id_2]
    c.execute(
        "UPDATE members SET group_id = ? WHERE telegram_id = ?",
        (g2, telegram_id_1),
    )
    c.execute(
        "UPDATE members SET group_id = ? WHERE telegram_id = ?",
        (g1, telegram_id_2),
    )
    conn.commit()
    conn.close()
    return True


# --- WEEKS ---


def get_or_create_current_week(assigned_group_id):
    """
    Creează sau returnează rândul pentru săptămâna curentă (duminică–sâmbătă).

    Dacă rândul există deja cu assigned_group_id setat, nu îl suprascriem
    (schimbările de anchor/rotație nu migrează retroactiv săptămânile vechi).
    """
    conn = get_connection()
    c = conn.cursor()
    sunday = get_current_sunday()
    week_label = week_label_for_sunday(sunday)
    start_date = sunday.isoformat()
    end_date = (sunday + timedelta(days=6)).isoformat()

    c.execute("SELECT * FROM weeks WHERE week_label = ?", (week_label,))
    week = c.fetchone()

    if not week:
        c.execute(
            """
            INSERT INTO weeks (week_label, start_date, end_date, assigned_group_id)
            VALUES (?, ?, ?, ?)
            """,
            (week_label, start_date, end_date, assigned_group_id),
        )
        conn.commit()
        c.execute("SELECT * FROM weeks WHERE week_label = ?", (week_label,))
        week = c.fetchone()
    elif week["assigned_group_id"] is None and assigned_group_id is not None:
        c.execute(
            "UPDATE weeks SET assigned_group_id = ? WHERE id = ?",
            (assigned_group_id, week["id"]),
        )
        conn.commit()
        c.execute("SELECT * FROM weeks WHERE id = ?", (week["id"],))
        week = c.fetchone()
    elif (
        week["assigned_group_id"] is not None
        and assigned_group_id is not None
        and week["assigned_group_id"] != assigned_group_id
    ):
        logger.info(
            "Săptămâna %s are assigned_group_id=%s; rotația curentă cere %s (nu se actualizează automat).",
            week_label,
            week["assigned_group_id"],
            assigned_group_id,
        )

    conn.close()
    return week


def get_current_week():
    conn = get_connection()
    c = conn.cursor()
    label = week_label_for_sunday(get_current_sunday())
    c.execute("SELECT * FROM weeks WHERE week_label = ?", (label,))
    row = c.fetchone()
    conn.close()
    return row


def get_week_by_label(week_label):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM weeks WHERE week_label = ?", (week_label,))
    row = c.fetchone()
    conn.close()
    return row


def get_week_by_start_date(start_date_iso: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM weeks WHERE start_date = ?", (start_date_iso,))
    row = c.fetchone()
    conn.close()
    return row


def get_assigned_group_for_week(week):
    if not week:
        return None
    return week["assigned_group_id"]


def set_pinned_message_id(week_id, message_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE weeks SET pinned_message_id = ? WHERE id = ?",
        (message_id, week_id),
    )
    conn.commit()
    conn.close()


# --- PARTICIPANTS ---


def add_participant(week_id, telegram_id, display_name, username=None, is_assigned=0):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT OR IGNORE INTO week_participants
        (week_id, telegram_id, username, display_name, is_assigned)
        VALUES (?, ?, ?, ?, ?)
        """,
        (week_id, telegram_id, username, display_name, 1 if is_assigned else 0),
    )
    inserted = c.rowcount > 0
    conn.commit()
    conn.close()
    return inserted


def mark_participant_done(week_id, telegram_id):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute(
        """
        UPDATE week_participants
        SET completed = 1, completed_at = ?
        WHERE week_id = ? AND telegram_id = ?
        """,
        (now, week_id, telegram_id),
    )
    conn.commit()
    conn.close()


def get_participants_for_week(week_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT * FROM week_participants
        WHERE week_id = ?
        ORDER BY is_assigned DESC, joined_at
        """,
        (week_id,),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def is_week_complete(week_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT COUNT(*) AS n,
               SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS done_n
        FROM week_participants
        WHERE week_id = ?
        """,
        (week_id,),
    )
    r = c.fetchone()
    conn.close()
    n, done_n = r["n"], r["done_n"] or 0
    return n > 0 and n == done_n


def get_pending_participants(week_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT * FROM week_participants
        WHERE week_id = ? AND completed = 0
        ORDER BY is_assigned DESC, display_name
        """,
        (week_id,),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def remove_participant_from_week(week_id, telegram_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "DELETE FROM week_participants WHERE week_id = ? AND telegram_id = ?",
        (week_id, telegram_id),
    )
    conn.commit()
    deleted = c.rowcount > 0
    conn.close()
    return deleted


# --- REMINDERS ---


def has_reminder_been_sent(week_id, reminder_type):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM reminders_log WHERE week_id = ? AND reminder_type = ?",
        (week_id, reminder_type),
    )
    ok = c.fetchone() is not None
    conn.close()
    return ok


def log_reminder(week_id, reminder_type):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT OR IGNORE INTO reminders_log (week_id, reminder_type)
        VALUES (?, ?)
        """,
        (week_id, reminder_type),
    )
    conn.commit()
    conn.close()


# --- STATS ---


def get_member_stats(telegram_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT
            SUM(CASE WHEN is_assigned = 1 THEN 1 ELSE 0 END) AS assigned_count,
            SUM(CASE WHEN is_assigned = 1 AND completed = 1 THEN 1 ELSE 0 END) AS completed_assigned,
            SUM(CASE WHEN is_assigned = 0 THEN 1 ELSE 0 END) AS joined_count,
            SUM(CASE WHEN is_assigned = 0 AND completed = 1 THEN 1 ELSE 0 END) AS completed_joined
        FROM week_participants
        WHERE telegram_id = ?
        """,
        (telegram_id,),
    )
    r = c.fetchone()
    conn.close()
    ac = int(r["assigned_count"] or 0)
    ca = int(r["completed_assigned"] or 0)
    jc = int(r["joined_count"] or 0)
    cj = int(r["completed_joined"] or 0)
    return {
        "assigned_count": ac,
        "completed_assigned": ca,
        "joined_count": jc,
        "completed_joined": cj,
    }


def get_top_contributors(limit=10):
    tz = ZoneInfo("Europe/Bucharest")
    now = datetime.now(tz)
    first = now.date().replace(day=1)
    if first.month == 12:
        next_first = date(first.year + 1, 1, 1)
    else:
        next_first = date(first.year, first.month + 1, 1)

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT telegram_id,
               MAX(display_name) AS display_name,
               COUNT(*) AS total
        FROM week_participants
        WHERE completed = 1
          AND completed_at IS NOT NULL
          AND date(completed_at) >= date(?)
          AND date(completed_at) < date(?)
        GROUP BY telegram_id
        ORDER BY total DESC
        LIMIT ?
        """,
        (first.isoformat(), next_first.isoformat(), limit),
    )
    rows = c.fetchall()
    conn.close()
    return rows
