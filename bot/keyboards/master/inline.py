from typing import Optional
from aiogram.types import InlineKeyboardButton as IButton
from aiogram.types import InlineKeyboardMarkup as IMarkup

from bot.utils.models import MasterButtonCallBack
from phrases import PHRASES_RU


def page_master_keyboard(appointment_id: int, msg_to_delete: Optional[str] = None) -> IMarkup:
    keyboard = [[
        IButton(
            text=PHRASES_RU.button.admin.reject,
            callback_data=MasterButtonCallBack(status='cancelled',
                                               appointment_id=appointment_id,
                                               msg_to_delete=msg_to_delete).pack()),
        IButton(
            text=PHRASES_RU.button.admin.confirm,
            callback_data=MasterButtonCallBack(status='confirmed',
                                               appointment_id=appointment_id,
                                               msg_to_delete=msg_to_delete).pack()
        )]
    ]
    return IMarkup(inline_keyboard=keyboard)
