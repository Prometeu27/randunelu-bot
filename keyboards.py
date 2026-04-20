# keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def join_reply_markup():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🙋 Mă alătur", callback_data="join")]]
    )
