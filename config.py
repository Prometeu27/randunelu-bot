# config.py
import os
from datetime import date

from dotenv import load_dotenv

load_dotenv()

DATABASE_PATH = "bot.db"

BOT_TOKEN = None
GROUP_CHAT_ID = None
ADMIN_TELEGRAM_ID = None
ROTATION_ANCHOR_DATE = os.getenv("ROTATION_ANCHOR_DATE", "2025-01-05")


def validate_config():
    """
    Validează variabilele de mediu. Apelată la import și din main după init_db.
    """
    global BOT_TOKEN, GROUP_CHAT_ID, ADMIN_TELEGRAM_ID, ROTATION_ANCHOR_DATE

    token = os.getenv("BOT_TOKEN")
    if not token or not str(token).strip():
        raise ValueError(
            "BOT_TOKEN lipsește sau e gol. Adaugă-l în fișierul .env."
        )

    raw_group = os.getenv("GROUP_CHAT_ID")
    if raw_group is None or not str(raw_group).strip():
        raise ValueError(
            "GROUP_CHAT_ID lipsește din .env (ID-ul numeric al grupului Telegram)."
        )
    try:
        gid = int(str(raw_group).strip())
    except ValueError as e:
        raise ValueError(
            "GROUP_CHAT_ID trebuie să fie un număr întreg (ID chat)."
        ) from e

    raw_admin = os.getenv("ADMIN_TELEGRAM_ID")
    if raw_admin is None or not str(raw_admin).strip():
        raise ValueError(
            "ADMIN_TELEGRAM_ID lipsește din .env (ID-ul numeric al adminului principal)."
        )
    try:
        aid = int(str(raw_admin).strip())
    except ValueError as e:
        raise ValueError(
            "ADMIN_TELEGRAM_ID trebuie să fie un număr întreg."
        ) from e

    anchor_raw = os.getenv("ROTATION_ANCHOR_DATE", "2025-01-05")
    anchor_raw = str(anchor_raw).strip()
    try:
        anchor = date.fromisoformat(anchor_raw)
    except ValueError as e:
        raise ValueError(
            f"ROTATION_ANCHOR_DATE ({anchor_raw!r}) nu e o dată ISO validă (AAAA-LL-ZZ)."
        ) from e
    if anchor.weekday() != 6:
        raise ValueError(
            f"ROTATION_ANCHOR_DATE trebuie să fie o duminică; {anchor_raw} "
            f"({anchor.isoformat()}) are weekday {anchor.weekday()} (6 = duminică)."
        )

    BOT_TOKEN = str(token).strip()
    GROUP_CHAT_ID = gid
    ADMIN_TELEGRAM_ID = aid
    ROTATION_ANCHOR_DATE = anchor_raw


validate_config()
