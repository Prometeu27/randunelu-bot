# main.py
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler
)
from config import BOT_TOKEN
from database import init_db
from scheduler import setup_scheduler
from handlers.commands import (
    done_command, status_command, lista_command
)
from handlers.admin import (
    addmember_command, removemember_command,
    members_command, swap_command,
    skip_command, setadmin_command
)
from handlers.callbacks import join_callback


def main():
    # Inițializează DB
    init_db()

    # Construiește aplicația
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Comenzi utilizatori
    app.add_handler(CommandHandler("done", done_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("lista", lista_command))

    # Comenzi admin
    app.add_handler(CommandHandler("addmember", addmember_command))
    app.add_handler(CommandHandler("removemember", removemember_command))
    app.add_handler(CommandHandler("members", members_command))
    app.add_handler(CommandHandler("swap", swap_command))
    app.add_handler(CommandHandler("skip", skip_command))
    app.add_handler(CommandHandler("setadmin", setadmin_command))

    # Callback buton Join
    app.add_handler(CallbackQueryHandler(join_callback, pattern="^join$"))

    # Scheduler
    setup_scheduler(app.job_queue, app.bot)

    print("Botul rulează...")
    app.run_polling()


if __name__ == "__main__":
    main()