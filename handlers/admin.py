# handlers/admin.py
from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_TELEGRAM_ID
from database import (
    add_member,
    get_connection,
    get_current_week,
    get_member_by_telegram_id,
    get_member_by_username,
    get_members_by_group,
    remove_participant_from_week,
    set_member_active,
    set_member_group,
    swap_member_groups,
)
from pinned_message import refresh_week_pinned_message


def is_admin(telegram_id):
    member = get_member_by_telegram_id(telegram_id)
    if member and member["role"] == "admin":
        return True
    if telegram_id == ADMIN_TELEGRAM_ID:
        return True
    return False


async def addmember_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /addmember <telegram_id> <display_name>
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
    await update.message.reply_text(f"✅ {display_name} a fost adăugat.")


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
    await update.message.reply_text(
        f"✅ {member['display_name']} a fost marcat ca inactiv."
    )


async def members_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /members — toți membrii cu grupă și status
    """
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Nu ai permisiuni.")
        return

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT * FROM members
        ORDER BY is_active DESC, group_id IS NULL, group_id, display_name
        """
    )
    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("⚠️ Nu există membri înregistrați.")
        return

    lines = []
    for m in rows:
        st = "activ" if m["is_active"] else "inactiv"
        g = m["group_id"]
        gtxt = f"grupa {g}" if g else "fără grupă"
        lines.append(
            f"• {m['display_name']} — {gtxt}, {st} (ID: {m['telegram_id']})"
        )

    await update.message.reply_text("👥 Membri:\n" + "\n".join(lines))


async def groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Nu ai permisiuni.")
        return

    lines = ["👥 Grupele de rotație:\n"]
    for gid in range(1, 8):
        ms = get_members_by_group(gid)
        if ms:
            names = ", ".join(m["display_name"] for m in ms)
        else:
            names = "(nealocat)"
        lines.append(f"Grupa {gid}: {names}")

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT display_name FROM members
        WHERE is_active = 1 AND group_id IS NULL
        ORDER BY display_name
        """
    )
    unassigned = [r[0] for r in c.fetchall()]
    conn.close()

    if unassigned:
        lines.append("\n⚠️ Fără grupă: " + ", ".join(unassigned))
    else:
        lines.append("\n⚠️ Fără grupă: —")

    await update.message.reply_text("\n".join(lines))


async def setgroup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Nu ai permisiuni.")
        return

    args = context.args
    reply = update.message.reply_to_message

    if reply and args and len(args) == 1:
        try:
            group_id = int(args[0])
        except ValueError:
            await update.message.reply_text("⚠️ Grupa trebuie să fie un număr 1–7.")
            return
        target_tid = reply.from_user.id
    elif args and len(args) >= 2:
        try:
            group_id = int(args[-1])
        except ValueError:
            await update.message.reply_text("⚠️ Ultimul argument trebuie să fie grupa 1–7.")
            return
        ref = " ".join(args[:-1]).strip()
        if ref.startswith("@"):
            ref = ref[1:]
        if ref.isdigit():
            target_tid = int(ref)
        else:
            m = get_member_by_username(ref)
            if not m:
                await update.message.reply_text(
                    "⚠️ Nu găsesc un membru cu acest username. "
                    "Folosește ID-ul Telegram sau răspunde la mesajul persoanei."
                )
                return
            target_tid = m["telegram_id"]
    else:
        await update.message.reply_text(
            "Folosire: /setgroup @username 3 sau /setgroup 123456789 3 "
            "sau răspunde la mesaj cu /setgroup 3"
        )
        return

    if group_id < 1 or group_id > 7:
        await update.message.reply_text("⚠️ Grupa trebuie să fie între 1 și 7.")
        return

    mem = get_member_by_telegram_id(target_tid)
    if not mem:
        await update.message.reply_text(
            "⚠️ Membrul nu e în baza de date. Adaugă-l mai întâi cu /addmember."
        )
        return

    set_member_group(target_tid, group_id)
    display = mem["display_name"]
    await update.message.reply_text(
        f"✅ {display} a fost atribuit grupei {group_id}."
    )


async def swap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /swap <telegram_id_1> <telegram_id_2> — schimbă grupele între doi membri
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

    if not swap_member_groups(id1, id2):
        await update.message.reply_text(
            "⚠️ Nu s-a putut schimba: verifică că ambele ID-uri există în baza de date."
        )
        return

    await update.message.reply_text(
        f"✅ Grupele au fost schimbate între {m1['display_name']} și {m2['display_name']}."
    )


async def skip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /skip <telegram_id> — scoate membrul din participanții săptămânii curente
    """
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Nu ai permisiuni.")
        return

    args = context.args
    if not args:
        await update.message.reply_text("Folosire: /skip <telegram_id>")
        return

    try:
        telegram_id = int(args[0])
    except ValueError:
        await update.message.reply_text("⚠️ telegram_id trebuie să fie un număr.")
        return

    week = get_current_week()
    if not week:
        await update.message.reply_text("⚠️ Nu există o săptămână activă.")
        return

    ok = remove_participant_from_week(week["id"], telegram_id)
    if not ok:
        await update.message.reply_text(
            "⚠️ Membrul nu era în lista săptămânii curente."
        )
        return

    await refresh_week_pinned_message(context.bot, week)

    mem = get_member_by_telegram_id(telegram_id)
    name = mem["display_name"] if mem else str(telegram_id)
    await update.message.reply_text(
        f"⏭ {name} a fost scos din lista săptămânii curente."
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
