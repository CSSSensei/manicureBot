from typing import Optional
from aiogram.types import InlineKeyboardButton as IButton
from aiogram.types import InlineKeyboardMarkup as IMarkup

from DB.models import Pagination
from bot.bot_utils.models import MasterButtonCallBack
from bot.keyboards.admin import inline as admin_ikb
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
        [IButton(text="Клиенты", callback_data=PHRASES_RU.callback_data.master.clients)],  # TODO заменить кнопки на phrases
        [
            IButton(text="Удалить слоты", callback_data=PHRASES_RU.callback_data.master.delete_slots),
            IButton(text="Добавить слоты", callback_data=PHRASES_RU.callback_data.master.add_slots)
        ],
        [
            IButton(text="История действий", callback_data=PHRASES_RU.callback_data.master.history),
            IButton(text="Редактор услуг", callback_data=PHRASES_RU.callback_data.master.service_editor)
        ]
    ]
    return IMarkup(inline_keyboard=keyboard)


def cancel_button() -> IMarkup:
    keyboard = [[IButton(text=PHRASES_RU.button.back, callback_data=PHRASES_RU.callback_data.master.cancel)]]
    return IMarkup(inline_keyboard=keyboard)


def master_confirm_adding() -> IMarkup:
    keyboard = [
        [IButton(text=PHRASES_RU.button.cancel, callback_data=PHRASES_RU.callback_data.master.cancel)],
        [IButton(text=PHRASES_RU.button.confirm, callback_data=PHRASES_RU.callback_data.master.confirm_add_slot)]
    ]
    return IMarkup(inline_keyboard=keyboard)


def master_service_editor() -> IMarkup:
    keyboard = [
        [IButton(text='Редактировать услуги', callback_data=PHRASES_RU.callback_data.master.edit_service),
         IButton(text='Добавить услугу', callback_data=PHRASES_RU.callback_data.master.add_service)],
        [IButton(text=PHRASES_RU.button.back, callback_data=PHRASES_RU.callback_data.master.cancel)]
    ]
    return IMarkup(inline_keyboard=keyboard)


def master_history_keyboard(pagination: Pagination) -> IMarkup:
    reply_markup = admin_ikb.page_keyboard(type_of_event=3, pagination=pagination)
    back_button = IButton(
        text=PHRASES_RU.button.back,
        callback_data=PHRASES_RU.callback_data.master.cancel)
    if reply_markup:
        reply_markup.inline_keyboard.append([back_button])
    else:
        reply_markup = IMarkup(inline_keyboard=[[
            IButton(
                text=PHRASES_RU.button.back,
                callback_data=PHRASES_RU.callback_data.master.cancel)
        ]])
    return reply_markup
