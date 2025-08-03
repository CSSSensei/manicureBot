from pathlib import Path
from enum import Enum

BASE_DIR = Path(__file__).parent.parent
USERS_PER_PAGE = 15
ACTIONS_PER_PAGE = 5
QUERIES_PER_PAGE = 6

MONTHS = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}

PENDING = 'pending'
CONFIRMED = 'confirmed'
COMPLETED = 'completed'
CANCELLED = 'cancelled'
REJECTED = 'rejected'
BACK = 'back'


class Action:
    set_active: str = 'set_active'
    set_inactive: str = 'set_inactive'
    service_update: str = 'service_update'
    slot_calendar: str = 'slot_calendar'
    check_slot_to_delete: str = 'check_slot_to_delete'
    delete_slot: str = 'delete_slot'


class CalendarMode(Enum):
    BOOKING = "booking"  # Режим записи (для клиентов)
    DELETE = "delete"  # Режим удаления (для мастера)
