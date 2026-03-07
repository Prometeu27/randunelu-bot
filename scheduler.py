# scheduler.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import (
    get_all_active_members, get_or_create_current_week,
    get_current_week, get_joiners_for_week,
    has_reminder_been_sent, log_reminder,
    set_pinned_message_id, get_connection
)
from utils import format_week_message
from config import GROUP_CHAT_ID
from datetime import date


def get_assigned_member_for_week():
    """Determină cine e de serviciu săptămâna asta bazat pe rotație"""
    members = get_all_active_members()
    if not members:
        return None

    # ISO week number ca index în rotație
    week_number = int(date.today().strftime("%V"))
    index = (week_number - 1) % len(members)
    return members[index]


async def send_weekly_announcement(bot):
    """Luni dimineață — anunță cine e de serviciu și postează mesajul pinned"""
    member = get_assigned_member_for_week()
    if not member:
        return

    week = get_or_create_current_week(assigned_member_id=member['id'])

    if has_reminder_been_sent(week['id'], 'monday_announce'):
        return

    joiners = get_joiners_for_week(week['id'])
    text = format_week_message(member['display_name'], joiners, is_completed=False)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🙋 Mă alătur", callback_data="join")]
    ])

    message = await bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text=text,
        reply_markup=keyboard
    )

    # Pinnează mesajul
    try:
        await bot.pin_chat_message(
            chat_id=GROUP_CHAT_ID,
            message_id=message.message_id,
            disable_notification=True
        )
    except Exception as e:
        print(f"Nu am putut pinna mesajul: {e}")

    set_pinned_message_id(week['id'], message.message_id)
    log_reminder(week['id'], 'monday_announce')


async def send_wednesday_reminder(bot):
    """Miercuri — reminder blând dacă sarcina nu e bifată"""
    week = get_current_week()
    if not week or week['is_completed']:
        return

    if has_reminder_been_sent(week['id'], 'wednesday'):
        return

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM members WHERE id = ?", (week['assigned_member_id'],))
    member = c.fetchone()
    conn.close()

    if not member:
        return

    await bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text=f"👋 Reminder pentru {member['display_name']} — sarcina săptămânii nu e bifată încă. Mai ai timp! 😊"
    )

    log_reminder(week['id'], 'wednesday')


async def send_friday_reminder(bot):
    """Vineri — reminder mai insistent"""
    week = get_current_week()
    if not week or week['is_completed']:
        return

    if has_reminder_been_sent(week['id'], 'friday'):
        return

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM members WHERE id = ?", (week['assigned_member_id'],))
    member = c.fetchone()
    conn.close()

    if not member:
        return

    await bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text=f"⚠️ {member['display_name']}, vine weekendul și sarcina e încă nebifată! Nu uita! 🙏"
    )

    log_reminder(week['id'], 'friday')


def setup_scheduler(job_queue, bot):
    """Înregistrează toate job-urile în APScheduler"""
    from datetime import time
    import pytz

    tz = pytz.timezone("Europe/Bucharest")

    # Luni la 9:00
    job_queue.run_daily(
        callback=lambda context: send_weekly_announcement(context.bot),
        time=time(9, 0, tzinfo=tz),
        days=(0,),  # 0 = luni
        name="monday_announce"
    )

    # Miercuri la 10:00
    job_queue.run_daily(
        callback=lambda context: send_wednesday_reminder(context.bot),
        time=time(10, 0, tzinfo=tz),
        days=(2,),  # 2 = miercuri
        name="wednesday_reminder"
    )

    # Vineri la 10:00
    job_queue.run_daily(
        callback=lambda context: send_friday_reminder(context.bot),
        time=time(10, 0, tzinfo=tz),
        days=(4,),  # 4 = vineri
        name="friday_reminder"
    )