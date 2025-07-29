from typing import Optional

from aiogram.filters import BaseFilter, Filter
from aiogram.types import Message, CallbackQuery

from DB.tables.users import UsersTable
from DB.models import UserModel


class AdminFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        with UsersTable() as users_db:
            user: Optional[UserModel] = users_db.get_user(message.from_user.id)
            if user:
                return user.is_admin
            return False


class IsCancelActionFilter(Filter):
    async def __call__(self, callback: CallbackQuery, **data) -> bool:  # Проверка, относится ли коллбэк к кнопке «Отмена»
        callback_data = data.get("callback_data")
        return callback_data.action == 0 if callback_data else False
