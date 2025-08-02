from datetime import datetime
from typing import Optional
from aiogram.types import InlineKeyboardButton as IButton
from aiogram.types import InlineKeyboardMarkup as IMarkup

from DB.models import Pagination
from bot.bot_utils.models import MasterButtonCallBack, AddSlotsMonthCallBack
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


def back_to_adding() -> IMarkup:
    keyboard = [[IButton(text=PHRASES_RU.button.back, callback_data=PHRASES_RU.callback_data.master.back_to_adding_slots)]]
    return IMarkup(inline_keyboard=keyboard)


def add_slots_menu() -> IMarkup:
    now = datetime.now()
    current_month = now.month
    current_year = now.year

    next_month = current_month + 1 if current_month < 12 else 1
    next_year = current_year + 1 if current_month == 12 else current_year

    keyboard = [
        [
            IButton(
                text=f'на {const.MONTHS[current_month].lower()}',
                callback_data=AddSlotsMonthCallBack(month=current_month, year=current_year).pack()),
            IButton(
                text=f'на {const.MONTHS[next_month].lower()}',
                callback_data=AddSlotsMonthCallBack(month=next_month, year=next_year).pack())
        ],
        [
            IButton(text="Добавить вручную", callback_data=PHRASES_RU.callback_data.master.add_manual_slots)
        ],
        [
            IButton(text=PHRASES_RU.button.back, callback_data=PHRASES_RU.callback_data.master.cancel)
        ]
    ]
    return IMarkup(inline_keyboard=keyboard)


def master_confirm_adding(month: Optional[int] = None, year: Optional[int] = None) -> IMarkup:
    keyboard = [
        [IButton(text=PHRASES_RU.button.cancel,
                 callback_data=PHRASES_RU.callback_data.master.back_to_adding_slots)],
        [IButton(text=PHRASES_RU.button.confirm,
                 callback_data=AddSlotsMonthCallBack(action='add', month=month, year=year).pack() if month and year else
                 PHRASES_RU.callback_data.master.confirm_add_slot)]
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
