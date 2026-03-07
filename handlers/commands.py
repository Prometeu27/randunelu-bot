# handlers/commands.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import (
    get_current_week, get_member_by_telegram_id,
    get_joiners_for_week, mark_week_completed,
    set_pinned_message_id
)
from utils import format_week_message, format_status_message
from config import GROUP_CHAT_ID, ADMIN_TELEGRAM_ID


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Doar în privat — marchează sarcina ca îndeplinită"""
    user = update.effective_user
    chat = update.effective_chat

    # Doar în privat
    if chat.type != 'private':
        await update.message.reply_text("✋ Folosește /done în privat cu mine.")
        return

    # Verifică dacă e membru de bază
    member = get_member_by_telegram_id(user.id)
    if not member:
        await update.message.reply_text("⚠️ Nu ești în lista membrilor.")
        return

    # Verifică dacă e rândul lui
    week = get_current_week()
    if not week:
        await update.message.reply_text("⚠️ Nu există o săptămână activă.")
        return

    if week['assigned_member_id'] != member['id']:
        await update.message.reply_text("⚠️ Nu e rândul tău săptămâna asta.")
        return

    if week['is_completed']:
        await update.message.reply_text("✅ Ai marcat deja sarcina ca îndeplinită săptămâna asta.")
        return

    # Marchează ca îndeplinit
    mark_week_completed(week['id'])
    await update.message.reply_text("✅ Excelent! Am anunțat grupul.")

    # Anunță grupul
    joiners = get_joiners_for_week(week['id'])
    updated_text = format_week_message(member['display_name'], joiners, is_completed=True)

    # Editează mesajul pinned dacă există
    if week['pinned_message_id']:
        try:
            await context.bot.edit_message_text(
                chat_id=GROUP_CHAT_ID,
                message_id=week['pinned_message_id'],
                text=updated_text
            )
        except Exception:
            pass

    # Trimite și un mesaj nou în grup
    await context.bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text=f"🎉 {member['display_name']} a îndeplinit sarcina săptămâna asta!"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Oriunde — arată statusul săptămânii curente"""
    week = get_current_week()
    if not week:
        await update.message.reply_text("⚠️ Nu există o săptămână activă momentan.")
        return

    member = get_member_by_telegram_id(None)
    # Găsim membrul assigned
    from database import get_connection
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM members WHERE id = ?", (week['assigned_member_id'],))
    member = c.fetchone()
    conn.close()

    joiners = get_joiners_for_week(week['id'])
    text = format_status_message(week, member, joiners)
    await update.message.reply_text(text)


async def lista_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Arată lista celor alăturați săptămâna asta"""
    week = get_current_week()
    if not week:
        await update.message.reply_text("⚠️ Nu există o săptămână activă.")
        return

    joiners = get_joiners_for_week(week['id'])
    if not joiners:
        await update.message.reply_text("🙋 Nimeni nu s-a alăturat încă săptămâna asta.")
        return

    names = "\n".join([f"• {j['display_name']}" for j in joiners])
    await update.message.reply_text(f"🙋 Alăturați săptămâna asta:\n{names}")