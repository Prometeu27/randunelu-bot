# utils.py
from datetime import date


def get_week_label():
    return date.today().strftime("%G-W%V")


def format_week_message(member_display_name, joiners, is_completed=False):
    week_label = get_week_label()

    if is_completed:
        status = f"✅ {member_display_name} a îndeplinit sarcina!"
    else:
        status = f"🎯 De serviciu: {member_display_name}"

    if joiners:
        joiners_list = "\n".join([f"  • {j['display_name']}" for j in joiners])
        joiners_section = f"🙋 S-au alăturat:\n{joiners_list}"
    else:
        joiners_section = "🙋 S-au alăturat:\n  (încă nimeni)"

    return (
        f"📋 Săptămâna {week_label}\n"
        f"{status}\n\n"
        f"{joiners_section}"
    )


def format_status_message(week, member, joiners):
    if not week:
        return "⚠️ Nu există o săptămână activă momentan."

    status = "✅ Îndeplinită" if week['is_completed'] else "⏳ În așteptare"
    joiners_names = ", ".join([j['display_name'] for j in joiners]) if joiners else "nimeni"

    return (
        f"📋 Status săptămâna curentă:\n"
        f"👤 De serviciu: {member['display_name']}\n"
        f"📌 Status: {status}\n"
        f"🙋 Alăturați: {joiners_names}"
    )