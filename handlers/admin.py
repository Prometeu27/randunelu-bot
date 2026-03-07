# handlers/admin.py
from telegram import Update
from telegram.ext import ContextTypes
from database import (
    add_member, get_all_active_members,
    get_member_by_telegram_id, set_member_active,
    swap_rotation_order, get_current_week,
    get_connection
)
from config import ADMIN_TELEGRAM_ID


def is_admin(telegram_id):
    member = get_member_by_telegram_id(telegram_id)
    if member and member['role'] == 'admin':
        return True
    if telegram_id == ADMIN_TELEGRAM_ID:
        return True
    return False


async def addmember_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /addmember <telegram_id> <display_name>
    Ex: /addmember 123456789 Ion Popescu
    """
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Nu ai permisiuni.")
        return

    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text("Folosire: /addmember <telegram_id> <nume>")
        return

    try:
        telegram_id = int(args[0])
    except ValueError:
        await update.message.reply_text("⚠️ telegram_id trebuie să fie un număr.")
        return

    display_name = " ".join(args[1:])
    add_member(telegram_id=telegram_id, display_name=display_name)
    await update.message.reply_text(f"✅ {display_name} a fost adăugat în rotație.")


async def removemember_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /removemember <telegram_id>
    """
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Nu ai permisiuni.")
        return

    args = context.args
    if not args:
        await update.message.reply_text("Folosire: /removemember <telegram_id>")
        return

    try:
        telegram_id = int(args[0])
    except ValueError:
        await update.message.reply_text("⚠️ telegram_id trebuie să fie un număr.")
        return

    member = get_member_by_telegram_id(telegram_id)
    if not member:
        await update.message.reply_text("⚠️ Membrul nu există.")
        return

    set_member_active(telegram_id, False)
    await update.message.reply_text(f"✅ {member['display_name']} a fost scos din rotație.")


async def members_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /members — listează membrii activi cu ordinea rotației
    """
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Nu ai permisiuni.")
        return

    members = get_all_active_members()
    if not members:
        await update.message.reply_text("⚠️ Nu există membri activi.")
        return

    lines = [f"{m['rotation_order']}. {m['display_name']} (ID: {m['telegram_id']})" for m in members]
    await update.message.reply_text("👥 Membri în rotație:\n" + "\n".join(lines))


async def swap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /swap <telegram_id_1> <telegram_id_2>
    """
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Nu ai permisiuni.")
        return

    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text("Folosire: /swap <telegram_id_1> <telegram_id_2>")
        return

    try:
        id1 = int(args[0])
        id2 = int(args[1])
    except ValueError:
        await update.message.reply_text("⚠️ ID-urile trebuie să fie numere.")
        return

    m1 = get_member_by_telegram_id(id1)
    m2 = get_member_by_telegram_id(id2)

    if not m1 or not m2:
        await update.message.reply_text("⚠️ Unul dintre membri nu există.")
        return

    swap_rotation_order(id1, id2)
    await update.message.reply_text(
        f"✅ Ordinea schimbată între {m1['display_name']} și {m2['display_name']}."
    )


async def skip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /skip — sare peste membrul curent, asignează următorul
    """
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Nu ai permisiuni.")
        return

    week = get_current_week()
    if not week:
        await update.message.reply_text("⚠️ Nu există o săptămână activă.")
        return

    members = get_all_active_members()
    if not members:
        await update.message.reply_text("⚠️ Nu există membri activi.")
        return

    # Găsește indexul celui curent și ia următorul
    current_id = week['assigned_member_id']
    ids = [m['id'] for m in members]

    if current_id not in ids:
        await update.message.reply_text("⚠️ Membrul curent nu mai e activ.")
        return

    current_index = ids.index(current_id)
    next_index = (current_index + 1) % len(ids)
    next_member = members[next_index]

    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE weeks SET assigned_member_id = ? WHERE id = ?",
              (next_member['id'], week['id']))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"⏭ Sărit. Acum e rândul lui {next_member['display_name']}."
    )


async def setadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /setadmin <telegram_id>
    """
    user = update.effective_user
    if user.id != ADMIN_TELEGRAM_ID:
        await update.message.reply_text("⛔ Doar adminul principal poate face asta.")
        return

    args = context.args
    if not args:
        await update.message.reply_text("Folosire: /setadmin <telegram_id>")
        return

    try:
        telegram_id = int(args[0])
    except ValueError:
        await update.message.reply_text("⚠️ telegram_id trebuie să fie un număr.")
        return

    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE members SET role = 'admin' WHERE telegram_id = ?", (telegram_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ Userul {telegram_id} e acum admin.")