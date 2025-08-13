from typing import Optional
from aiogram.types import InlineKeyboardButton as IButton
from aiogram.types import InlineKeyboardMarkup as IMarkup

from DB.models import Pagination
from phrases import PHRASES_RU
from bot.bot_utils.models import AdminPageCallBack


def page_keyboard(type_of_event: int, pagination: Pagination, user_id: int = 0) -> Optional[IMarkup]:
    if pagination.total_pages <= 1:
        return None

    no_action = AdminPageCallBack(type_of_event=-1).pack()

    past_button = IButton(
        text=PHRASES_RU.button.prev_page,
        callback_data=AdminPageCallBack(type_of_event=type_of_event,
                                        page=pagination.page - 1,
                                        user_id=user_id).pack()
    ) if pagination.has_prev else IButton(text=' ', callback_data=no_action)

    next_button = IButton(
        text=PHRASES_RU.button.next_page,
        callback_data=AdminPageCallBack(type_of_event=type_of_event,
                                        page=pagination.page + 1,
                                        user_id=user_id).pack()
    ) if pagination.has_next else IButton(text=' ', callback_data=no_action)

    return IMarkup(inline_keyboard=[[
        past_button,
        IButton(text=PHRASES_RU.replace('template.page_counter', current=pagination.page, total=pagination.total_pages),
                callback_data=no_action),
        next_button
    ]])
