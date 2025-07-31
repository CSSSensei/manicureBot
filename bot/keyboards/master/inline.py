from typing import Optional
from aiogram.types import InlineKeyboardButton as IButton
from aiogram.types import InlineKeyboardMarkup as IMarkup

from bot.utils.models import MasterButtonCallBack
from config import const
from phrases import PHRASES_RU


def action_master_keyboard(appointment_id: int, msg_to_delete: Optional[str] = None) -> IMarkup:
    keyboard = [[
        IButton(
            text=PHRASES_RU.button.admin.reject,
            callback_data=MasterButtonCallBack(status=const.REJECTED,
                                               appointment_id=appointment_id,
                                               msg_to_delete=msg_to_delete).pack()),
        IButton(
            text=PHRASES_RU.button.admin.confirm,
            callback_data=MasterButtonCallBack(status=const.CONFIRMED,
                                               appointment_id=appointment_id,
                                               msg_to_delete=msg_to_delete).pack()
        )]
    ]
    return IMarkup(inline_keyboard=keyboard)


def menu_master_keyboard() -> IMarkup:
    keyboard = [
        [IButton(text="Клиенты", callback_data=PHRASES_RU.callback_data.master.clients)],
        [
            IButton(text="Удалить слоты", callback_data=PHRASES_RU.callback_data.master.delete_slots),
            IButton(text="Добавить слоты", callback_data=PHRASES_RU.callback_data.master.add_slots)
        ],
        [IButton(text="История действий", callback_data=PHRASES_RU.callback_data.master.history)]
    ]
    return IMarkup(inline_keyboard=keyboard)
