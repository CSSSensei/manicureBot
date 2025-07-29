import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel

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
    id: Optional[int] = None

    def __str__(self):
        start = self.start_time.strftime("%H:%M") if self.start_time else "00:00"
        end = self.end_time.strftime("%H:%M") if self.end_time else "00:00"
        return f"{start}{PHRASES_RU.icon.time_separator}{end}"


@dataclass
class PhotoModel:
    """Класс для представления фото референсов"""
    id: Optional[int] = None
    telegram_file_id: Optional[str] = None
    file_unique_id: Optional[str] = None
    caption: Optional[str] = None


class AppointmentModel(BaseModel):
    appointment_id: Optional[int] = None
    status: str = 'pending'
    slot_date: Optional[datetime] = None
    slot_id: Optional[int] = None
    service_id: Optional[int] = None
    service_name: Optional[str] = None
    photos: Optional[List[PhotoModel]] = None
    comment: Optional[str] = None
    client_id: Optional[int] = None
    client_username: Optional[str] = None
    client_contact: Optional[str] = None
    message_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def is_ready_for_confirmation(self) -> bool:
        """Проверяет, все ли обязательные поля заполнены"""
        return all([
            self.slot_id,
            self.service_id
        ])

    @property
    def formatted_date(self) -> Optional[str]:
        """Возвращает дату слота в формате '{день недели} %d.%m' или символ ошибки"""
        if self.slot_date is None:
            logger.error(f'Message creation error: no slot date in state data')
            return PHRASES_RU.error.unknown

        weekdays = [
            "Понедельник",
            "Вторник",
            "Среда",
            "Четверг",
            "Пятница",
            "Суббота",
            "Воскресенье"
        ]

        return f"{weekdays[self.slot_date.weekday()]} {self.slot_date.strftime('%d.%m')}"

    @property
    def slot_str(self):
        start = self.start_time.strftime("%H:%M") if self.start_time else "00:00"
        end = self.end_time.strftime("%H:%M") if self.end_time else "00:00"
        return f"{start}{PHRASES_RU.icon.time_separator}{end}"


@dataclass
class Master:
    """Класс для представления общей инфо о записи"""
    id: Optional[int] = None
    name: Optional[str] = None
    is_master: Optional[bool] = None
    message_id: Optional[int] = None
