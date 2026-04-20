# scheduler.py
import logging
import random
from datetime import timedelta, time

import pytz

from config import GROUP_CHAT_ID
from database import (
    add_participant,
    get_current_week,
    get_members_by_group,
    get_or_create_current_week,
    get_participants_for_week,
    get_pending_participants,
    get_week_by_start_date,
    has_reminder_been_sent,
    is_week_complete,
    log_reminder,
    set_pinned_message_id,
)
from keyboards import join_reply_markup
from utils import format_pinned_message, get_current_sunday, group_id_for_sunday

logger = logging.getLogger(__name__)


def _names_join(lst):
    if not lst:
        return "nimeni"
    return ", ".join(x["display_name"] for x in lst)


async def send_sunday_message(bot):
    current_sunday = get_current_sunday()
    last_sunday = current_sunday - timedelta(days=7)
    last_week = get_week_by_start_date(last_sunday.isoformat())

    if last_week and not has_reminder_been_sent(last_week["id"], "sunday_close"):
        mid = last_week["pinned_message_id"]
        if mid:
            try:
                await bot.unpin_chat_message(chat_id=GROUP_CHAT_ID, message_id=mid)
            except Exception as e:
                logger.warning("Nu am putut despina mesajul săptămânii trecute: %s", e)

        participants = get_participants_for_week(last_week["id"])

        if not participants:
            text = (
                "Săptămâna trecută nu a avut pe nimeni înscris în listă de rugăciune. "
                "Doamne ajută tuturor pentru săptămâna ce vine! 🙏"
            )
        elif is_week_complete(last_week["id"]):
            done = [p for p in participants if p["completed"]]
            done_assigned = [p for p in done if p["is_assigned"]]
            done_join = [p for p in done if not p["is_assigned"]]
            parts = []
            if done_assigned:
                parts.append("✅ Din echipă: " + _names_join(done_assigned) + ".")
            if done_join:
                parts.append("🙋 Voluntari: " + _names_join(done_join) + ".")
            body = " ".join(parts) if parts else "Toți au fost minunați!"
            text = (
                "🎉 Săptămâna trecută s-a încheiat cu bine! Slavă Domnului! 🙏\n"
                f"{body}\n"
                "Mulțumim tuturor pentru osteneală!"
            )
        else:
            done = [p for p in participants if p["completed"]]
            pending = [p for p in participants if not p["completed"]]
            done_assigned = [p for p in done if p["is_assigned"]]
            done_join = [p for p in done if not p["is_assigned"]]
            pend_assigned = [p for p in pending if p["is_assigned"]]
            pend_join = [p for p in pending if not p["is_assigned"]]

            did = _names_join(done) if done else "nimeni"
            didnt_parts = []
            if pend_assigned:
                didnt_parts.append("din echipă: " + _names_join(pend_assigned))
            if pend_join:
                didnt_parts.append("alăturați: " + _names_join(pend_join))
            didnt = ", ".join(didnt_parts) if didnt_parts else "nimeni"

            text = (
                "Săptămâna s-a încheiat. ✅ Au citit rugăciunea: "
                f"{did}.\n❌ Nu au bifat: {didnt}. "
                "Dumnezeu vede tot. 👁️ Să ne fie învățătură pentru săptămâna ce vine."
            )

        try:
            await bot.send_message(chat_id=GROUP_CHAT_ID, text=text)
        except Exception as e:
            logger.error("Eroare la wrap-up săptămână trecută: %s", e)
        else:
            log_reminder(last_week["id"], "sunday_close")

    assigned_group_id = group_id_for_sunday(current_sunday)
    week = get_or_create_current_week(assigned_group_id)

    if has_reminder_been_sent(week["id"], "sunday_announce"):
        return

    team = get_members_by_group(assigned_group_id)
    for m in team:
        add_participant(
            week["id"],
            m["telegram_id"],
            m["display_name"],
            m.get("username"),
            is_assigned=1,
        )

    participants = get_participants_for_week(week["id"])
    wlabel = week["week_label"]
    body = format_pinned_message(wlabel, team, participants)

    try:
        message = await bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=body,
            reply_markup=join_reply_markup(),
        )
    except Exception as e:
        logger.error("Eroare la anunțul de duminică: %s", e)
        return

    try:
        await bot.pin_chat_message(
            chat_id=GROUP_CHAT_ID,
            message_id=message.message_id,
            disable_notification=True,
        )
    except Exception as e:
        logger.warning("Nu am putut pinna mesajul: %s", e)

    set_pinned_message_id(week["id"], message.message_id)

    for m in team:
        try:
            await bot.send_message(
                chat_id=m["telegram_id"],
                text=(
                    f"Salut, {m['display_name']}! 🙏 Săptămâna aceasta ești în echipa de rugăciune. "
                    "Când ai citit Acatistul, te rog bifează cu /done. Doamne ajută! ✝️"
                ),
            )
        except Exception as e:
            logger.warning("Nu am putut trimite DM lui %s: %s", m["telegram_id"], e)

    log_reminder(week["id"], "sunday_announce")


THURSDAY_MESSAGES = [
    "Bună! 🙏 Ai apucat să citești rugăciunea săptămâna asta? Dacă da, bifează cu /done. Dacă nu, mai e timp! Doamne ajută! ✝️",
    "Salut! Suntem la jumătatea săptămânii. 📖 Rugăciunea te așteaptă. Când ești gata, /done și ești bifat! 😊",
    "Hey! 👋 Joi deja... Ai citit Acatistul? Dacă da — /done. Dacă nu — weekend-ul e aproape, mai ai timp! 🙏",
]


async def send_thursday_dm_reminder(bot):
    week = get_current_week()
    if not week or is_week_complete(week["id"]):
        return
    if has_reminder_been_sent(week["id"], "thursday_dm"):
        return

    pending = get_pending_participants(week["id"])
    if not pending:
        return

    msg = random.choice(THURSDAY_MESSAGES)
    sent_ok = 0
    for p in pending:
        try:
            await bot.send_message(chat_id=p["telegram_id"], text=msg)
            sent_ok += 1
        except Exception as e:
            logger.warning("Reminder joi eșuat pentru %s: %s", p["telegram_id"], e)

    if sent_ok > 0:
        log_reminder(week["id"], "thursday_dm")
    else:
        logger.warning(
            "Reminder joi: 0 DM-uri reușite pentru week_id=%s (%s persoane în așteptare).",
            week["id"],
            len(pending),
        )


SATURDAY_MESSAGES = [
    "🌙 Sâmbătă seara bate la ușă... Rugăciunea săptămânii plutește încă nerostită. {names} — mai e timp! 🙏",
    "⏳ A mai rămas o zi. {names}, vă mai așteptăm! Dumnezeu răbdare are, dar săptămâna — mai puțin. 😅🙏",
]


async def send_saturday_group_reminder(bot):
    week = get_current_week()
    if not week or is_week_complete(week["id"]):
        return
    if has_reminder_been_sent(week["id"], "saturday_group"):
        return

    pending = get_pending_participants(week["id"])
    if not pending:
        return

    names = _names_join(pending)
    template = random.choice(SATURDAY_MESSAGES)
    text = template.format(names=names)

    try:
        await bot.send_message(chat_id=GROUP_CHAT_ID, text=text)
    except Exception as e:
        logger.error("Reminder sâmbătă eșuat: %s", e)
    else:
        log_reminder(week["id"], "saturday_group")


def setup_scheduler(job_queue, bot):
    tz = pytz.timezone("Europe/Bucharest")

    job_queue.run_daily(
        callback=lambda context: send_sunday_message(context.bot),
        time=time(15, 0, tzinfo=tz),
        days=(6,),
        name="sunday_announce",
    )

    job_queue.run_daily(
        callback=lambda context: send_thursday_dm_reminder(context.bot),
        time=time(10, 0, tzinfo=tz),
        days=(3,),
        name="thursday_dm_reminder",
    )

    job_queue.run_daily(
        callback=lambda context: send_saturday_group_reminder(context.bot),
        time=time(10, 0, tzinfo=tz),
        days=(5,),
        name="saturday_group_reminder",
    )
