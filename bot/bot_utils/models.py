from dataclasses import dataclass
from typing import Tuple, Optional, Any
from aiogram.filters.callback_data import CallbackData


@dataclass
class CommandUnit:
    """Контейнер для хранения информации о команде бота"""
    name: str  # Основное имя команды
    aliases: Tuple[str, ...] = ()  # Дополнительные варианты вызова
    description: str = ''
    is_admin: bool = False
    placeholders: Optional[Tuple[Any, ...]] = None

    def __str__(self):
        base = f'/{self.name}'
        if self.aliases:
            base += f", {', '.join(f'/{a}' for a in self.aliases)}"
        if self.placeholders:
            base += ' ' + ' '.join(f'{{{p}}}' for p in self.placeholders)
        if self.description:
            base += f' — {self.description}'
        return base


class AdminPageCallBack(CallbackData, prefix='cut'):
    type_of_event: int  # -1 - no action, 1 - get_users, 2 - user_query, 3 - action master history
    user_id: int = 0
    page: int = 1


class BookingPageCallBack(CallbackData, prefix='booking'):
    page: Optional[int] = None  # None - кнопка с текущей странице, не подразумевает действий
    action: Optional[str] = None  # 'cancel' - отменить запись, 'back' - разад


class BookingStatusCallBack(CallbackData, prefix='status'):
    status: Optional[str] = None  # 'cancel'
    app_id: Optional[int] = None


class PhotoAppCallBack(CallbackData, prefix='photo'):
    app_id: Optional[int] = None


class MonthCallBack(CallbackData, prefix="calendar"):
    day: int = 0
    month: int = 0
    year: int = 0
    action: int = 0  # 0 -ничего, 1 - след месяц, -1 - предыдущий месяц, 3 - след год, 4 - пред год


class SlotCallBack(CallbackData, prefix="slot"):
    slot_id: int


class ServiceCallBack(CallbackData, prefix="service"):
    service_id: int


class ActionButtonCallBack(CallbackData, prefix="action_button"):
    action: int  # 1 - вперед, -1 -назад, 0 - отмена
    current_page: Optional[int] = None


class MasterButtonCallBack(CallbackData, prefix="master"):
    status: str  # {'pending', 'confirmed', 'completed', 'cancelled'}
    appointment_id: Optional[int] = None
    msg_to_delete: Optional[str] = None


class AddSlotsMonthCallBack(CallbackData, prefix="add_slots_month"):
    action: str = 'check'  # 'check', 'add'
    month: int
    year: int


class MasterServiceCallBack(CallbackData, prefix="master_service"):
    service_id: int
    action: Optional[str] = None  # 'set_active', 'set_inactive', 'updated'


class EditServiceCallBack(CallbackData, prefix="edit_master_service"):
    service_id: int
