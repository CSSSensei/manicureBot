from aiogram.utils.keyboard import ReplyKeyboardMarkup as KMarkup
from aiogram.utils.keyboard import KeyboardButton as KButton
from phrases import PHRASES_RU


def __make_placeholder_appeal() -> str:
    return PHRASES_RU.placeholder_appeal


book_button: KButton = KButton(text=PHRASES_RU.button.booking)
active_booking: KButton = KButton(text=PHRASES_RU.button.active_booking)

keyboard: KMarkup = KMarkup(
    keyboard=[[book_button, active_booking]],
    resize_keyboard=True,
    one_time_keyboard=False,
    input_field_placeholder=__make_placeholder_appeal())
