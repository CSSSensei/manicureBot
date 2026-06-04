
from aiogram.filters import BaseFilter, Filter
from aiogram.types import CallbackQuery, Message

from config import const
from DB.models import Master, UserModel
from DB.tables.masters import MastersTable
from DB.tables.users import UsersTable


class AdminFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        with UsersTable() as users_db:
            user: UserModel | None = users_db.get_user(message.from_user.id)
            if user:
                return user.is_admin
            return False


class MasterFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        with MastersTable() as master_db, UsersTable() as db:
            user_master: Master | None = master_db.get_master(message.from_user.id)
            user: UserModel | None = db.get_user(message.from_user.id)
            return user.is_admin or user_master and user_master.is_master   # АДМИН ИМЕЕТ ДОСТУП К ИНТЕРФЕЙСУ МАСТЕРА


class IsCancelActionFilter(Filter):
    async def __call__(self, callback: CallbackQuery, **data) -> bool:  # Проверка, относится ли коллбэк к кнопке «Отмена»
        callback_data = data.get("callback_data")
        return callback_data.action == 0 if callback_data else False


class NotBookingCalendar(Filter):
    async def __call__(self, callback: CallbackQuery, **data) -> bool:  # Проверка, относится ли коллбэк к кнопке календаря для удаления слота
        callback_data = data.get("callback_data")
        return callback_data.mode in {const.CalendarMode.DELETE, const.CalendarMode.APPOINTMENT_MAP} or callback_data.action != 0 if callback_data else False
