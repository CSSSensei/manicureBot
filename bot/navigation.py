import datetime
import logging
from typing import Optional, Awaitable, Callable

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.models import Appointment
from bot.states import AppointmentStates
from phrases import PHRASES_RU
from bot.keyboards import inline_keyboards as ikb


logger = logging.getLogger(__name__)


class AppointmentNavigation:
    STATES = {
        'WAITING_FOR_DATE': AppointmentStates.WAITING_FOR_DATE,
        'WAITING_FOR_SLOT': AppointmentStates.WAITING_FOR_SLOT,
        'WAITING_FOR_SERVICE': AppointmentStates.WAITING_FOR_SERVICE,
        'WAITING_FOR_PHOTOS': AppointmentStates.WAITING_FOR_PHOTOS,
        'WAITING_FOR_COMMENT': AppointmentStates.WAITING_FOR_COMMENT,
        'CONFIRMATION': AppointmentStates.CONFIRMATION
    }

    FLOW_ORDER = list(STATES.keys())

    @classmethod
    async def get_appointment_data(cls, state: FSMContext) -> Appointment:
        data = await state.get_data()
        return Appointment(**data)

    @classmethod
    async def update_appointment_data(cls, state: FSMContext, **updates) -> Appointment:
        current = await cls.get_appointment_data(state)
        updated = current.model_copy(update=updates)
        await state.update_data(updated.model_dump())
        return updated

    @classmethod
    def get_next_state(cls, current_state: str) -> Optional[str]:
        """Возвращает следующее состояние в процессе записи"""
        try:
            idx = cls.FLOW_ORDER.index(current_state)
            return cls.FLOW_ORDER[idx + 1] if idx + 1 < len(cls.FLOW_ORDER) else None
        except ValueError:
            return None

    @classmethod
    def get_prev_state(cls, current_state: str) -> Optional[str]:
        """Возвращает предыдущее состояние в процессе записи"""
        try:
            idx = cls.FLOW_ORDER.index(current_state)
            return cls.FLOW_ORDER[idx - 1] if idx > 0 else None
        except ValueError:
            return None

    @classmethod
    async def handle_navigation(
            cls,
            callback: CallbackQuery,
            state: FSMContext,
            current_state: str,
            action: int,
            additional_check: Optional[Callable[[Appointment], Awaitable[bool]]] = None):
        if action == 0:  # Отмена
            await state.clear()
            await callback.message.edit_text(text=PHRASES_RU.answer.booking_canceled, reply_markup=None)
            return

        if action == -1:  # Назад
            if prev_state := cls.get_prev_state(current_state):
                await cls._clear_step_data(state, prev_state)
                await state.set_state(cls.STATES[prev_state])
                await cls._call_step_handler(callback, state, prev_state)
            return

        if action == 1:  # Далее
            if next_state := cls.get_next_state(current_state):
                if additional_check and not await additional_check(await cls.get_appointment_data(state)):
                    await callback.answer(PHRASES_RU.error.booking.missing_data)
                    return

                await state.set_state(cls.STATES[next_state])
                await cls._call_step_handler(callback, state, next_state)

    @classmethod
    async def _clear_step_data(cls, state: FSMContext, step: str):
        """Очищает данные, связанные с определенным шагом"""
        clear_rules = {
            'WAITING_FOR_DATE': {'slot_date': None},
            'WAITING_FOR_SLOT': {'slot_id': None, 'slot_str': None},
            'WAITING_FOR_SERVICE': {'service_id': None, 'service_str': None},
            'WAITING_FOR_PHOTOS': {'photos': None},
            'WAITING_FOR_COMMENT': {'text': None}
        }
        if step in clear_rules:
            await cls.update_appointment_data(state, **clear_rules[step])

    @classmethod
    async def _call_step_handler(cls, callback: CallbackQuery, state: FSMContext, step: str):
        """Вызывает обработчик для конкретного шага"""
        data = await cls.get_appointment_data(state)
        handlers = {
            'WAITING_FOR_DATE': cls._show_date_selection,
            'WAITING_FOR_SLOT': cls._show_slot_selection,
            'WAITING_FOR_SERVICE': cls._show_service_selection,
            'WAITING_FOR_PHOTOS': cls._show_photo_upload,
            'WAITING_FOR_COMMENT': cls._show_comment_input,
            'CONFIRMATION': cls._show_confirmation
        }
        await handlers[step](callback, data)

    @staticmethod
    async def _show_date_selection(callback: CallbackQuery, data: Appointment):
        current_date = datetime.datetime.now()
        current_month = current_date.month
        current_year = current_date.year
        await callback.message.edit_text(PHRASES_RU.answer.choose_date, reply_markup=ikb.month_keyboard(current_month, current_year, False))

    @staticmethod
    async def _show_slot_selection(callback: CallbackQuery, data: Appointment):
        if data.slot_date:
            await callback.message.edit_text(
                text=PHRASES_RU.replace('answer.choose_slot', date=data.slot_date.strftime('%d.%m.%Y')),
                reply_markup=ikb.slots_keyboard(data.slot_date)
            )
        else:
            logger.error(f'Appointment creation error: no slot date in state data')
            await callback.message.edit_text(PHRASES_RU.error.booking.try_again, reply_markup=None)

    @staticmethod
    async def _show_service_selection(callback: CallbackQuery, data: Appointment):
        await callback.message.edit_text(
            text=AppointmentNavigation.current_booking_text(data) + PHRASES_RU.answer.choose_service,
            reply_markup=ikb.service_keyboard()
        )

    @staticmethod
    async def _show_photo_upload(callback: CallbackQuery, data: Appointment):
        await callback.message.edit_text(
            text=AppointmentNavigation.current_booking_text(data) + PHRASES_RU.answer.send_photo,
            reply_markup=ikb.photo_keyboard()
        )

    @staticmethod
    async def _show_comment_input(callback: CallbackQuery, data: Appointment):
        await callback.message.edit_text(
            text=AppointmentNavigation.current_booking_text(data) + PHRASES_RU.answer.send_comment,
            reply_markup=ikb.comment_keyboard()
        )

    @staticmethod
    async def _show_confirmation(callback: CallbackQuery, data: Appointment):
        await callback.message.edit_text(
            text=AppointmentNavigation.current_booking_text(data) + PHRASES_RU.replace('answer.confirm', data=data),
            reply_markup=ikb.confirm_keyboard()
        )

    @staticmethod
    def current_booking_text(data: Appointment) -> str:
        text = PHRASES_RU.replace('template.slot', date=data.slot_date.strftime('%d.%m.%Y'),
                                  datetime=data.slot_str) if data.slot_date and data.slot_str else ''
        if data.service_str:
            text += PHRASES_RU.replace('template.service', service=data.service_str)
        if data.photos and len(data.photos) > 0:
            text += PHRASES_RU.replace('template.photos', len_photos=len(data.photos))
        if data.text:
            text += PHRASES_RU.replace('template.text', text=data.text)
        return text
