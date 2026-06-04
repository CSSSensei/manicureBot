from dataclasses import dataclass
from datetime import date
from typing import Any

from aiogram.filters.callback_data import CallbackData

from config.const import Action, AppListMode, AppointmentPageAction, CalendarMode, PageListSection


@dataclass
class CommandUnit:
    """Контейнер для хранения информации о команде бота"""

    name: str  # Основное имя команды
    aliases: tuple[str, ...] = ()  # Дополнительные варианты вызова
    description: str = ''
    is_admin: bool = False
    is_master: bool = False
    is_user: bool = True
    placeholders: tuple[Any, ...] | None = None

    def __str__(self):
        base = f'/{self.name}'
        if self.aliases:
            base += f', {", ".join(f"/{a}" for a in self.aliases)}'
        if self.placeholders:
            base += ' ' + ' '.join(f'{{{p}}}' for p in self.placeholders)
        if self.description:
            base += f' — {self.description}'
        return base


class AdminPageCallBack(CallbackData, prefix='cut'):
    type_of_event: PageListSection
    user_id: int = 0
    page: int = 1


class BookingPageCallBack(CallbackData, prefix='booking'):
    page: int | None = None  # None - кнопка с текущей странице, не подразумевает действий
    action: AppointmentPageAction | None = None  # 'set_cancelled' - отменить запись, 'back' - назад
    app_id: int | None = None
    app_date: date | None = None
    mode: AppListMode | None = None


class BookingStatusCallBack(CallbackData, prefix='status'):
    status: str | None = None  # 'cancel'
    app_id: int | None = None


class PhotoAppCallBack(CallbackData, prefix='photo'):
    app_id: int | None = None


class MonthCallBack(CallbackData, prefix='calendar'):
    day: int = 0
    month: int = 0
    year: int = 0
    action: int = 0  # 0 - ничего, 1 - след месяц, -1 - предыдущий месяц
    mode: CalendarMode = CalendarMode.BOOKING


class SlotCallBack(CallbackData, prefix='slot'):
    slot_id: int
    mode: CalendarMode = CalendarMode.BOOKING


class ServiceCallBack(CallbackData, prefix='service'):
    service_id: int


class ActionButtonCallBack(CallbackData, prefix='action_button'):
    action: int  # 1 - вперед, -1 -назад, 0 - отмена
    current_page: int | None = None


class MasterButtonCallBack(CallbackData, prefix='master'):
    status: str  # {'pending', 'confirmed', 'completed', 'cancelled'}
    appointment_id: int | None = None
    msg_to_delete: str | None = None


class AddSlotsMonthCallBack(CallbackData, prefix='add_slots_month'):
    action: str = 'check'  # 'check', 'add'
    month: int
    year: int


class MasterServiceCallBack(CallbackData, prefix='master_service'):
    service_id: int
    action: str | None = None  # 'set_active', 'set_inactive', 'updated'


class ScheduleServiceCallBack(CallbackData, prefix='schedule_service'):
    service_id: int
    weekday: int
    action: str  # 'set_active', 'set_inactive'


class EditServiceCallBack(CallbackData, prefix='edit_master_service'):
    service_id: int


class DeleteSlotCallBack(CallbackData, prefix='delete_slot'):
    slot_id: int | None = None
    slot_date: date | None = None
    action: str = Action.slot_calendar
