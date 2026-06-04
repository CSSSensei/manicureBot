import logging
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any

from pydantic import BaseModel

from config.const import PENDING

logger = logging.getLogger(__name__)


def format_date(time: datetime):
    weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    weekday = weekdays[time.weekday()]
    return f'{weekday} {time.strftime("%d.%m")}'


@dataclass
class UserModel:
    user_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_admin: bool = False
    is_banned: bool = False
    registration_date: datetime | None = None
    contact: str | None = None
    query_count: int = 0

    def full_name(self) -> str:
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return ' '.join(parts) if parts else str(self.user_id)


@dataclass
class QueryModel:
    user_id: int
    query_text: str
    query_id: int | None = None
    query_date: datetime | None = None
    user: UserModel | None = None


@dataclass
class Pagination:
    page: int
    per_page: int
    total_items: int
    total_pages: int

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


@dataclass
class ServiceModel:
    name: str
    price: float | None = None
    description: str | None = None
    id: int | None = None
    duration: int | None = None
    is_active: bool = True


@dataclass
class SlotModel:
    start_time: datetime
    end_time: datetime
    is_available: bool
    is_deleted: bool = False
    id: int | None = None

    def __str__(self):
        start = self.start_time.strftime('%H:%M') if self.start_time else '00:00'
        return f'{start}'

    @property
    def formatted_date(self) -> str:
        """Возвращает дату слота в формате '{день недели} %d.%m' или ошибку, если время не задано"""
        if not self.start_time:
            return 'Ошибка: дата не указана'

        return format_date(self.start_time)


@dataclass
class PhotoModel:
    id: int | None = None
    telegram_file_id: str | None = None
    file_unique_id: str | None = None
    caption: str | None = None


class AppointmentModel(BaseModel):
    appointment_id: int | None = None
    status: str = PENDING
    slot: SlotModel | None = None
    service: ServiceModel | None = None
    photos: list[PhotoModel] | None = None
    comment: str | None = None
    client: UserModel | None = None
    message_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    slot_date: datetime | None = None

    def is_ready_for_confirmation(self) -> bool:
        return all([self.slot and self.slot.id is not None, self.service and self.service.id is not None])

    @property
    def formatted_date(self) -> str:
        if not self.slot:
            return 'Ошибка: дата не указана'

        return self.slot.formatted_date

    @property
    def slot_str(self) -> str:
        """Возвращает временной интервал слота в формате 'HH:MM – HH:MM'"""
        if not self.slot:
            return '00:00 – 00:00'
        return str(self.slot)

    @classmethod
    def from_fsm_data(cls, data: dict[str, Any]) -> 'AppointmentModel':
        slot_data = data.pop('slot', None)
        service_data = data.pop('service', None)
        client_data = data.pop('client', None)
        photos_data = data.pop('photos', None)
        slot = SlotModel(**slot_data) if slot_data else None
        service = ServiceModel(**service_data) if service_data else None
        client = UserModel(**client_data) if client_data else None

        photos = None
        if photos_data:
            photos = [PhotoModel(**p) if isinstance(p, dict) else p for p in photos_data]

        base_data = {k: v for k, v in data.items() if k in cls.model_fields}

        return cls(slot=slot, service=service, client=client, photos=photos, **base_data)

    def __str__(self):
        return (
            f'Запись #{self.appointment_id or "новая"}\n'
            f'Услуга: {self.service.name if self.service else "не выбрана"}\n'
            f'Дата: {self.formatted_date}\n'
            f'Время: {self.slot_str}\n'
            f'Статус: {self.status}'
        )


@dataclass
class Master:
    user: UserModel | None = None
    specialization: str | None = None
    is_master: bool | None = None
    message_id: int | None = None
    current_app_id: int | None = None
    msg_to_delete: str | None = None


@dataclass
class ClientStats:
    total: int = 0
    completed: int = 0
    upcoming: int = 0
    pending: int = 0
    cancelled: int = 0
    rejected: int = 0
    first_appointment: datetime | None = None
    last_appointment: datetime | None = None
    by_status: dict[str, int] = None

    def __post_init__(self):
        if self.by_status is None:
            self.by_status = {}


@dataclass
class ClientWithStats:
    user: UserModel
    stats: ClientStats


@dataclass
class Weekday:
    id: int
    name: str
    name_ru: str
    short_name: str


@dataclass
class ServiceSchedule:
    service_id: int
    weekday: Weekday
    is_available: bool


@dataclass
class ChannelMessage:
    id: int
    channel_id: int
    message_id: int
    message_type: str
    last_update: datetime
    is_active: bool


@dataclass
class DaySchedule:
    weekday: int
    time_slots: list[tuple[time, time]]  # Список времени начала слотов
    is_working: bool
