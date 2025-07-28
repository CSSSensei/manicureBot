from dataclasses import dataclass
from datetime import datetime
from typing import Tuple, Optional, Any, List
from aiogram.filters.callback_data import CallbackData
from pydantic import BaseModel

from DB.models import PhotoModel


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


class CutMessageCallBack(CallbackData, prefix='cut'):
    action: int
    user_id: int = 0
    page: int = 1


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


class Appointment(BaseModel):
    slot_date: Optional[datetime] = None
    slot_id: Optional[int] = None
    slot_str: Optional[str] = None
    service_id: Optional[int] = None
    service_str: Optional[str] = None
    photos: Optional[List[PhotoModel]] = None
    text: Optional[str] = None
    message_id: Optional[int] = None

    def is_ready_for_confirmation(self) -> bool:
        """Проверяет, все ли обязательные поля заполнены"""
        return all([
            self.slot_id,
            self.service_id
        ])
