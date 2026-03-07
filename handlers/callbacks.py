# handlers/callbacks.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import (
    get_current_week, add_joiner,
    get_joiners_for_week, get_connection
)
from utils import format_week_message


async def join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler pentru butonul 'Mă alătur'"""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    week = get_current_week()

    if not week:
        await query.answer("⚠️ Nu există o săptămână activă.", show_alert=True)
        return

    if week['is_completed']:
        await query.answer("✅ Sarcina săptămânii e deja îndeplinită.", show_alert=True)
        return

    # Adaugă joiner
    inserted = add_joiner(
        week_id=week['id'],
        telegram_id=user.id,
        display_name=user.full_name,
        username=user.username
    )

    if not inserted:
        await query.answer("Ești deja în listă! 😊", show_alert=True)
        return

    await query.answer("✅ Te-ai alăturat săptămâna asta!")

    # Găsește membrul assigned
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM members WHERE id = ?", (week['assigned_member_id'],))
    member = c.fetchone()
    conn.close()

    # Editează mesajul pinned cu lista actualizată
    joiners = get_joiners_for_week(week['id'])
    updated_text = format_week_message(
        member['display_name'],
        joiners,
        is_completed=week['is_completed']
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🙋 Mă alătur", callback_data="join")]
    ])

    try:
        await query.edit_message_text(text=updated_text, reply_markup=keyboard)
    except Exception:
        pass