# main.py
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler

from config import BOT_TOKEN, validate_config
from database import init_db
from handlers.admin import (
    addmember_command,
    groups_command,
    members_command,
    removemember_command,
    setadmin_command,
    setgroup_command,
    skip_command,
    swap_command,
)
from handlers.callbacks import join_callback
from handlers.commands import (
    done_command,
    lista_command,
    mystats_command,
    next_command,
    status_command,
)
from scheduler import setup_scheduler


def main():
    init_db()
    validate_config()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("done", done_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("lista", lista_command))
    app.add_handler(CommandHandler("next", next_command))
    app.add_handler(CommandHandler("mystats", mystats_command))

    app.add_handler(CommandHandler("addmember", addmember_command))
    app.add_handler(CommandHandler("removemember", removemember_command))
    app.add_handler(CommandHandler("members", members_command))
    app.add_handler(CommandHandler("setgroup", setgroup_command))
    app.add_handler(CommandHandler("groups", groups_command))
    app.add_handler(CommandHandler("swap", swap_command))
    app.add_handler(CommandHandler("skip", skip_command))
    app.add_handler(CommandHandler("setadmin", setadmin_command))

    app.add_handler(CallbackQueryHandler(join_callback, pattern="^join$"))

    setup_scheduler(app.job_queue, app.bot)

    print("Botul rulează...")
    app.run_polling()


if __name__ == "__main__":
    main()
