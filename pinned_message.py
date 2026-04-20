# pinned_message.py
import logging

from telegram.error import BadRequest

from config import GROUP_CHAT_ID
from database import get_members_by_group, get_participants_for_week, is_week_complete
from keyboards import join_reply_markup
from utils import format_pinned_message

logger = logging.getLogger(__name__)


async def refresh_week_pinned_message(bot, week_row):
    """Actualizează mesajul pinat al săptămânii (echipă + alăturați + stări)."""
    mid = week_row["pinned_message_id"]
    gid = week_row["assigned_group_id"]
    if not mid:
        return
    team = get_members_by_group(gid) if gid else []
    participants = get_participants_for_week(week_row["id"])
    text = format_pinned_message(week_row["week_label"], team, participants)
    markup = None if is_week_complete(week_row["id"]) else join_reply_markup()
    try:
        await bot.edit_message_text(
            chat_id=GROUP_CHAT_ID,
            message_id=mid,
            text=text,
            reply_markup=markup,
        )
    except BadRequest as e:
        if "not modified" in str(e).lower():
            return
        logger.warning("Nu am putut actualiza mesajul pinat: %s", e)
    except Exception as e:
        logger.warning("Nu am putut actualiza mesajul pinat: %s", e)
