# handlers/commands.py
from telegram import Update
from telegram.ext import ContextTypes

from config import GROUP_CHAT_ID
from database import (
    get_current_week,
    get_member_by_telegram_id,
    get_member_stats,
    get_members_by_group,
    get_participants_for_week,
    get_pending_participants,
    is_week_complete,
    mark_participant_done,
)
from pinned_message import refresh_week_pinned_message
from utils import get_next_sunday, group_id_for_sunday


def _participant_for_user(week_id, telegram_id):
    for p in get_participants_for_week(week_id):
        if int(p["telegram_id"]) == int(telegram_id):
            return p
    return None


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if chat.type != "private":
        await update.message.reply_text("✋ Folosește /done în privat cu mine.")
        return

    week = get_current_week()
    if not week:
        await update.message.reply_text("⚠️ Nu există o săptămână activă.")
        return

    p = _participant_for_user(week["id"], user.id)
    if not p:
        await update.message.reply_text(
            "Nu ești înregistrat pentru săptămâna asta. "
            "Apasă 'Mă alătur' în grup mai întâi."
        )
        return

    if p["completed"]:
        await update.message.reply_text("Ai bifat deja! ✅ Mulțumim! 🙏")
        return

    mark_participant_done(week["id"], user.id)
    await update.message.reply_text(
        "✅ Mulțumim! Dumnezeu să-ți răsplătească osteneala! 🙏"
    )

    await refresh_week_pinned_message(context.bot, week)

    display = p["display_name"]
    if is_week_complete(week["id"]):
        allp = get_participants_for_week(week["id"])
        names = ", ".join(x["display_name"] for x in allp)
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=(
                "🎉 Toți cei înscriși au citit rugăciunea săptămâna aceasta! "
                f"Slavă Domnului! 🙏 {names}"
            ),
        )
    else:
        pend = get_pending_participants(week["id"])
        pend_names = ", ".join(x["display_name"] for x in pend)
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=(
                f"✅ {display} a bifat rugăciunea! "
                f"Mai avem: {pend_names} 🙏"
            ),
        )


def _status_lines(week):
    participants = get_participants_for_week(week["id"])
    assigned = [p for p in participants if p["is_assigned"]]
    joiners = [p for p in participants if not p["is_assigned"]]

    def fmt_person(p):
        st = "✅" if p["completed"] else "⏳"
        return f"{p['display_name']} {st}"

    team = ", ".join(fmt_person(p) for p in assigned) or "—"
    alaturati = ", ".join(fmt_person(p) for p in joiners) or "—"
    total = len(participants)
    done = sum(1 for p in participants if p["completed"])
    return (
        f"📖 Săptămâna {week['week_label']}\n"
        f"👥 Echipa: {team}\n"
        f"🙋 Alăturați: {alaturati}\n"
        f"📊 Progres: {done} din {total} au finalizat"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    week = get_current_week()
    if not week:
        await update.message.reply_text("⚠️ Nu există o săptămână activă momentan.")
        return
    await update.message.reply_text(_status_lines(week))


async def lista_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    week = get_current_week()
    if not week:
        await update.message.reply_text("⚠️ Nu există o săptămână activă.")
        return

    participants = get_participants_for_week(week["id"])
    if not participants:
        await update.message.reply_text("Nu e nimeni înscris încă pentru săptămâna asta.")
        return

    lines = []
    for p in participants:
        rol = "echipă" if p["is_assigned"] else "voluntar"
        st = "✅ bifat" if p["completed"] else "⏳ în așteptare"
        lines.append(f"• {p['display_name']} ({rol}) — {st}")

    await update.message.reply_text(
        "📋 Participanți săptămâna aceasta:\n" + "\n".join(lines)
    )


async def next_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ns = get_next_sunday()
    gid = group_id_for_sunday(ns)
    team = get_members_by_group(gid)
    names = ", ".join(m["display_name"] for m in team) or "(încă nimeni în grupă)"
    user = update.effective_user
    text = (
        "📅 Săptămâna viitoare:\n"
        f"🙏 Echipa de rugăciune: {names}"
    )
    if any(int(m["telegram_id"]) == user.id for m in team):
        text += (
            "\n\n👆 Ești și tu în echipa săptămânii viitoare! Doamne ajută! 🙏"
        )
    await update.message.reply_text(text)


async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    mem = get_member_by_telegram_id(user.id)
    display = mem["display_name"] if mem else (user.full_name or str(user.id))
    s = get_member_stats(user.id)
    total_done = s["completed_assigned"] + s["completed_joined"]
    text = (
        f"📊 Statisticile tale, {display}:\n"
        f"📌 Ai fost în echipă: {s['assigned_count']} ori\n"
        f"✅ Ai finalizat (din echipă): {s['completed_assigned']} ori\n"
        f"🙋 Te-ai alăturat voluntar: {s['joined_count']} ori\n"
        f"✅ Ai finalizat (voluntar): {s['completed_joined']} ori\n"
        f"🏆 Total finalizări: {total_done}"
    )
    await update.message.reply_text(text)
