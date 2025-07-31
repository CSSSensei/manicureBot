from aiogram.utils.keyboard import ReplyKeyboardMarkup as KMarkup
from aiogram.utils.keyboard import KeyboardButton as KButton
from phrases import PHRASES_RU


def __make_placeholder_appeal() -> str:
    return PHRASES_RU.placeholder_appeal


clients_today: KButton = KButton(text=PHRASES_RU.button.master.clients_today)
menu: KButton = KButton(text=PHRASES_RU.button.master.menu)

keyboard: KMarkup = KMarkup(
    keyboard=[[clients_today, menu]],
    resize_keyboard=True,
    one_time_keyboard=False,
    input_field_placeholder=__make_placeholder_appeal())
