import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel

from config.const import PENDING
from phrases import PHRASES_RU

logger = logging.getLogger(__name__)


@dataclass
class UserModel:
    """Класс для представления пользователя"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_admin: bool = False
    is_banned: bool = False
    registration_date: Optional[datetime] = None
    contact: Optional[str] = None
    query_count: int = 0

    def full_name(self) -> str:
        """Возвращает полное имя пользователя"""
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return ' '.join(parts) if parts else str(self.user_id)


@dataclass
class QueryModel:
    """Класс для представления запроса"""
    user_id: int
    query_text: str
    query_id: Optional[int] = None
    query_date: Optional[datetime] = None
    user: Optional[UserModel] = None


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
    """Класс для представления сервиса"""
    name: str
    price: Optional[float] = None
    description: Optional[str] = None
    id: Optional[int] = None
    duration: Optional[int] = None
    is_active: bool = True


@dataclass
class SlotModel:
    """Класс для представления слота для записи"""
    start_time: datetime
    end_time: datetime
    is_available: bool
    is_deleted: bool = False
    id: Optional[int] = None

    def __str__(self):
        start = self.start_time.strftime('%H:%M') if self.start_time else '00:00'
        end = self.end_time.strftime('%H:%M') if self.end_time else '00:00'
        return f'{start}{PHRASES_RU.icon.time_separator}{end}'


@dataclass
class PhotoModel:
    """Класс для представления фото референсов"""
    id: Optional[int] = None
    telegram_file_id: Optional[str] = None
    file_unique_id: Optional[str] = None
    caption: Optional[str] = None


class AppointmentModel(BaseModel):
    """Модель записи на прием с валидацией обязательных полей"""
    appointment_id: Optional[int] = None
    status: str = PENDING
    slot: Optional[SlotModel] = None
    service: Optional[ServiceModel] = None
    photos: Optional[List[PhotoModel]] = None
    comment: Optional[str] = None
    client: Optional[UserModel] = None
    message_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    slot_date: Optional[datetime] = None

    def is_ready_for_confirmation(self) -> bool:
        """Проверяет, все ли обязательные поля заполнены"""
        return all([
            self.slot and self.slot.id is not None,
            self.service and self.service.id is not None
        ])

    @property
    def formatted_date(self) -> str:
        """Возвращает дату слота в формате '{день недели} %d.%m' или ошибку, если слот не задан"""
        if not self.slot or not self.slot.start_time:
            return 'Ошибка: дата не указана'

        weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        weekday = weekdays[self.slot.start_time.weekday()]
        return f'{weekday} {self.slot.start_time.strftime("%d.%m")}'

    @property
    def slot_str(self) -> str:
        """Возвращает временной интервал слота в формате 'HH:MM – HH:MM'"""
        if not self.slot:
            return '00:00 – 00:00'
        return str(self.slot)
    
    @classmethod
    def from_fsm_data(cls, data: dict[str, Any]) -> 'AppointmentModel':
        """Преобразует данные из FSM в модель AppointmentModel."""
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

        return cls(
            slot=slot,
            service=service,
            client=client,
            photos=photos,
            **base_data
        )

    def __str__(self):
        """Строковое представление записи"""
        return (
            f'Запись #{self.appointment_id or "новая"}\n'
            f'Услуга: {self.service.name if self.service else "не выбрана"}\n'
            f'Дата: {self.formatted_date}\n'
            f'Время: {self.slot_str}\n'
            f'Статус: {self.status}'
        )


@dataclass
class Master:
    """Класс для представления общей инфо о записи"""
    id: Optional[int] = None
    name: Optional[str] = None
    specialization: Optional[str] = None
    is_master: Optional[bool] = None
    message_id: Optional[int] = None
    current_app_id: Optional[int] = None
    msg_to_delete: Optional[str] = None
