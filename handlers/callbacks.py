# handlers/callbacks.py
import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import GROUP_CHAT_ID
from database import add_participant, get_current_week
from pinned_message import refresh_week_pinned_message

logger = logging.getLogger(__name__)


async def join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler pentru butonul 'Mă alătur'."""
    query = update.callback_query
    user = query.from_user
    week = get_current_week()

    if not week:
        await query.answer(
            "⚠️ Nu există o săptămână activă momentan.", show_alert=True
        )
        return

    inserted = add_participant(
        week_id=week["id"],
        telegram_id=user.id,
        display_name=user.full_name or (user.username or str(user.id)),
        username=user.username,
        is_assigned=0,
    )

    if not inserted:
        await query.answer(
            "Ești deja în lista acestei săptămâni! 😊", show_alert=True
        )
        return

    await query.answer(
        "Te-ai alăturat echipei de rugăciune săptămâna asta! 🙏 "
        "Când ești gata, bifează cu /done."
    )

    display = user.full_name or (user.username or str(user.id))
    try:
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=(
                f"🙋 {display} s-a alăturat echipei de rugăciune săptămâna asta! "
                "Minunat! 🙏"
            ),
        )
    except Exception as e:
        logger.warning("Nu am putut anunța alăturarea lui %s în grup: %s", display, e)

    await refresh_week_pinned_message(context.bot, week)
