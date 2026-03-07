# database.py
import sqlite3
from config import DATABASE_PATH
from datetime import datetime, date


def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # returnează dict-like rows
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            display_name TEXT NOT NULL,
            rotation_order INTEGER UNIQUE,
            is_active INTEGER DEFAULT 1,
            role TEXT DEFAULT 'member',
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS weeks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_label TEXT UNIQUE NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            assigned_member_id INTEGER,
            is_completed INTEGER DEFAULT 0,
            completed_at TEXT,
            pinned_message_id INTEGER,
            FOREIGN KEY (assigned_member_id) REFERENCES members(id)
        );

        CREATE TABLE IF NOT EXISTS week_joiners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_id INTEGER NOT NULL,
            telegram_id INTEGER NOT NULL,
            username TEXT,
            display_name TEXT NOT NULL,
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
    """)

    conn.commit()
    conn.close()


# --- MEMBERS ---

def add_member(telegram_id, display_name, username=None, role='member'):
    conn = get_connection()
    c = conn.cursor()
    # rotation_order = următorul număr disponibil
    c.execute("SELECT COALESCE(MAX(rotation_order), 0) + 1 FROM members")
    next_order = c.fetchone()[0]
    c.execute("""
        INSERT OR IGNORE INTO members (telegram_id, username, display_name, rotation_order, role)
        VALUES (?, ?, ?, ?, ?)
    """, (telegram_id, username, display_name, next_order, role))
    conn.commit()
    conn.close()


def get_all_active_members():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM members WHERE is_active = 1 ORDER BY rotation_order")
    members = c.fetchall()
    conn.close()
    return members


def get_member_by_telegram_id(telegram_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM members WHERE telegram_id = ?", (telegram_id,))
    member = c.fetchone()
    conn.close()
    return member


def set_member_active(telegram_id, is_active: bool):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE members SET is_active = ? WHERE telegram_id = ?",
              (1 if is_active else 0, telegram_id))
    conn.commit()
    conn.close()


def swap_rotation_order(telegram_id_1, telegram_id_2):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, rotation_order FROM members WHERE telegram_id = ?", (telegram_id_1,))
    m1 = c.fetchone()
    c.execute("SELECT id, rotation_order FROM members WHERE telegram_id = ?", (telegram_id_2,))
    m2 = c.fetchone()
    if m1 and m2:
        c.execute("UPDATE members SET rotation_order = ? WHERE id = ?", (m2['rotation_order'], m1['id']))
        c.execute("UPDATE members SET rotation_order = ? WHERE id = ?", (m1['rotation_order'], m2['id']))
        conn.commit()
    conn.close()


# --- WEEKS ---

def get_or_create_current_week(assigned_member_id):
    conn = get_connection()
    c = conn.cursor()
    today = date.today()
    # ISO week: ex "2025-W03"
    week_label = today.strftime("%G-W%V")
    # Start = luni, end = duminică
    monday = today - __import__('datetime').timedelta(days=today.weekday())
    sunday = monday + __import__('datetime').timedelta(days=6)

    c.execute("SELECT * FROM weeks WHERE week_label = ?", (week_label,))
    week = c.fetchone()

    if not week:
        c.execute("""
            INSERT INTO weeks (week_label, start_date, end_date, assigned_member_id)
            VALUES (?, ?, ?, ?)
        """, (week_label, monday.isoformat(), sunday.isoformat(), assigned_member_id))
        conn.commit()
        c.execute("SELECT * FROM weeks WHERE week_label = ?", (week_label,))
        week = c.fetchone()

    conn.close()
    return week


def get_current_week():
    conn = get_connection()
    c = conn.cursor()
    week_label = date.today().strftime("%G-W%V")
    c.execute("SELECT * FROM weeks WHERE week_label = ?", (week_label,))
    week = c.fetchone()
    conn.close()
    return week


def mark_week_completed(week_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE weeks SET is_completed = 1, completed_at = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), week_id))
    conn.commit()
    conn.close()


def set_pinned_message_id(week_id, message_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE weeks SET pinned_message_id = ? WHERE id = ?", (message_id, week_id))
    conn.commit()
    conn.close()


# --- JOINERS ---

def add_joiner(week_id, telegram_id, display_name, username=None):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO week_joiners (week_id, telegram_id, username, display_name)
            VALUES (?, ?, ?, ?)
        """, (week_id, telegram_id, username, display_name))
        conn.commit()
        inserted = True
    except sqlite3.IntegrityError:
        inserted = False  # already joined
    conn.close()
    return inserted


def get_joiners_for_week(week_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM week_joiners WHERE week_id = ?", (week_id,))
    joiners = c.fetchall()
    conn.close()
    return joiners


# --- REMINDERS ---

def has_reminder_been_sent(week_id, reminder_type):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM reminders_log WHERE week_id = ? AND reminder_type = ?",
              (week_id, reminder_type))
    result = c.fetchone()
    conn.close()
    return result is not None


def log_reminder(week_id, reminder_type):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO reminders_log (week_id, reminder_type)
        VALUES (?, ?)
    """, (week_id, reminder_type))
    conn.commit()
    conn.close()