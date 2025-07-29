from typing import List, Optional
from aiogram.types import InlineKeyboardButton as IButton
from aiogram.types import InlineKeyboardMarkup as IMarkup

from bot.models import MasterButtonCallBack
from phrases import PHRASES_RU


def base_master_keyboard(appointment_id: int, buttons: Optional[List[List[IButton]]] = None) -> IMarkup:
    keyboard = [[
        IButton(
            text=PHRASES_RU.button.admin.reject,
            callback_data=MasterButtonCallBack(action=-1, appointment_id=appointment_id).pack()),
        IButton(
            text=PHRASES_RU.button.admin.confirm,
            callback_data=MasterButtonCallBack(action=1, appointment_id=appointment_id).pack()
        )]
    ]

    if buttons:
        keyboard.append([buttons])
    return IMarkup(inline_keyboard=keyboard)
