# utils.py
from datetime import date, timedelta

from config import ROTATION_ANCHOR_DATE


def _today() -> date:
    """Punct unic pentru „astăzi” (ușor de patch-uit în teste)."""
    return date.today()


def get_current_sunday() -> date:
    """Cea mai recentă duminică (inclusiv astăzi dacă e duminică)."""
    today = _today()
    delta = (today.weekday() + 1) % 7
    return today - timedelta(days=delta)


def get_next_sunday() -> date:
    """Duminica care urmează după începutul săptămânii curente (duminică–sâmbătă)."""
    return get_current_sunday() + timedelta(days=7)


def _first_sunday_of_year(year: int) -> date:
    jan1 = date(year, 1, 1)
    return jan1 + timedelta(days=(6 - jan1.weekday()) % 7)


def sunday_week_sequence(sunday: date) -> int:
    """Index secvențial al săptămânii duminică–sâmbătă în anul calendaristic al acelei duminici."""
    y = sunday.year
    first = _first_sunday_of_year(y)
    if sunday < first:
        prev_dec = date(y - 1, 12, 31)
        # ultima duminică din anul anterior pentru același „flux”
        prev_sun = prev_dec - timedelta(days=(prev_dec.weekday() + 1) % 7)
        return sunday_week_sequence(prev_sun)
    return 1 + (sunday - first).days // 7


def week_label_for_sunday(sunday: date) -> str:
    return f"{sunday.year}-S{sunday_week_sequence(sunday)}"


def get_week_label() -> str:
    return week_label_for_sunday(get_current_sunday())


def group_id_for_sunday(sunday: date) -> int:
    anchor = date.fromisoformat(ROTATION_ANCHOR_DATE)
    weeks_elapsed = (sunday - anchor).days // 7
    return (weeks_elapsed % 7) + 1


def format_pinned_message(week_label, assigned_members, participants):
    """
    assigned_members: listă de rânduri membru (display_name, telegram_id) în ordinea dorită.
    participants: rânduri week_participants (telegram_id, display_name, is_assigned, completed).
    """
    by_tid = {int(p["telegram_id"]): p for p in participants}

    def status_emoji(tid: int) -> str:
        p = by_tid.get(tid)
        if not p:
            return "⏳"
        return "✅" if p["completed"] else "⏳"

    team_parts = []
    for m in assigned_members:
        tid = int(m["telegram_id"])
        name = m["display_name"]
        team_parts.append(f"{name} {status_emoji(tid)}")

    joiners = [p for p in participants if not p["is_assigned"]]
    if joiners:
        joiner_parts = [f"{p['display_name']} {'✅' if p['completed'] else '⏳'}" for p in joiners]
        joiners_section = "🙋 Alăturați:\n" + "\n".join(f"  • {jp}" for jp in joiner_parts)
    else:
        joiners_section = "🙋 Alăturați:\n  (încă nimeni)"

    team_line = ", ".join(team_parts) if team_parts else "(nimeni)"

    is_complete = bool(participants) and all(p["completed"] for p in participants)

    if is_complete:
        footer = "🎉 Toți participanții au citit rugăciunea săptămâna aceasta! Slavă Domnului! 🙏"
    else:
        footer = "Cineva vrea să li se alăture? Apasă butonul de mai jos! 👇"

    return (
        f"📖 Săptămâna {week_label}\n"
        f"🙏 De rugăciune: {team_line}\n\n"
        f"{footer}\n\n"
        f"{joiners_section}"
    )
