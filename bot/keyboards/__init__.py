from typing import Optional
from aiogram.utils.keyboard import ReplyKeyboardMarkup as KMarkup

from DB.tables.masters import MastersTable
from . import admin, default, master as master_keyboard


def get_keyboard(user_id: int) -> Optional[KMarkup]:
    with MastersTable() as master_db:
        user_master = master_db.get_master(user_id)
        if user_master and user_master.is_master:
            return master_keyboard.base.keyboard

    return default.base.keyboard
