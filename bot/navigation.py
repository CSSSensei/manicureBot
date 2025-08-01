import logging
from typing import Optional, Awaitable, Callable

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from DB.tables.slots import SlotsTable
from DB.models import AppointmentModel
from bot.states import AppointmentStates
from phrases import PHRASES_RU
from bot.keyboards.default import inline as ikb
from utils import format_string


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
    async def get_appointment_data(cls, state: FSMContext) -> AppointmentModel:
        data = await state.get_data()
        return AppointmentModel.from_fsm_data(data)

    @classmethod
    async def update_appointment_data(cls, state: FSMContext, **updates) -> AppointmentModel:
        current_data = await state.get_data()
        current_model = AppointmentModel.from_fsm_data(current_data)
        updated_model = current_model.model_copy(update=updates)
        await state.update_data(**updated_model.model_dump())

        return updated_model

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
            additional_check: Optional[Callable[[AppointmentModel], Awaitable[bool]]] = None):
        if action == 0:  # Отмена
            await state.clear()
            await callback.message.edit_text(text=PHRASES_RU.answer.booking_canceled, reply_markup=None)
            return

        if action == -1:  # Назад
            if prev_state := cls.get_prev_state(current_state):
                if await cls._clear_step_data(state, prev_state):
                    await cls._notify_user(callback, prev_state)
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
    async def _clear_step_data(cls, state: FSMContext, step: str) -> bool:
        """Очищает данные, связанные с определенным шагом"""
        clear_rules = {
            'WAITING_FOR_SLOT': {'slot': None},
            'WAITING_FOR_SERVICE': {'service': None},
            'WAITING_FOR_PHOTOS': {'photos': None},
            'WAITING_FOR_COMMENT': {'comment': None}
        }
        if step in clear_rules:
            data = await state.get_data()
            required_keys = clear_rules[step].keys()
            await cls.update_appointment_data(state, **clear_rules[step])
            return all(key in data and data[key] is not None for key in required_keys)
        return False

    @classmethod
    async def _notify_user(cls, callback: CallbackQuery, step: str):
        notify_rules = {
            'WAITING_FOR_DATE': None,
            'WAITING_FOR_SLOT': None,
            'WAITING_FOR_SERVICE': None,
            'WAITING_FOR_PHOTOS': PHRASES_RU.callback.answer.photo_delete,
            'WAITING_FOR_COMMENT': PHRASES_RU.callback.answer.comment_delete
        }
        await callback.answer(text=notify_rules[step])

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
    async def _show_date_selection(callback: CallbackQuery, data: AppointmentModel):
        with SlotsTable() as slots_db:
            prev = False
            first_slot = slots_db.get_first_available_slot()
            if data.slot_date:
                if data.slot_date.month != first_slot.month:
                    prev = True
                first_slot = data.slot_date
            if first_slot:
                await callback.message.edit_text(
                    PHRASES_RU.answer.choose_date,
                    reply_markup=ikb.month_keyboard(first_slot.month, first_slot.year, prev))
            else:
                await callback.message.edit_text(PHRASES_RU.error.no_slots)

    @staticmethod
    async def _show_slot_selection(callback: CallbackQuery, data: AppointmentModel):
        if data.slot_date:
            await callback.message.edit_text(
                text=PHRASES_RU.replace('answer.choose_slot', date=data.slot_date.strftime('%d.%m.%Y')),
                reply_markup=ikb.slots_keyboard(data.slot_date)
            )
        else:
            logger.error(f'Appointment creation error: no slot date in state data')
            await callback.message.edit_text(PHRASES_RU.error.booking.try_again, reply_markup=None)

    @staticmethod
    async def _show_service_selection(callback: CallbackQuery, data: AppointmentModel):
        await callback.message.edit_text(
            text=format_string.user_booking_text(data) + PHRASES_RU.answer.choose_service,
            reply_markup=ikb.service_keyboard()
        )

    @staticmethod
    async def _show_photo_upload(callback: CallbackQuery, data: AppointmentModel):
        await callback.message.edit_text(
            text=format_string.user_booking_text(data) + PHRASES_RU.answer.send_photo,
            reply_markup=ikb.photo_keyboard()
        )

    @staticmethod
    async def _show_comment_input(callback: CallbackQuery, data: AppointmentModel):
        await callback.message.edit_text(
            text=format_string.user_booking_text(data) + PHRASES_RU.answer.send_comment,
            reply_markup=ikb.comment_keyboard()
        )

    @staticmethod
    async def _show_confirmation(callback: CallbackQuery, data: AppointmentModel):
        await callback.message.edit_text(
            text=format_string.user_booking_text(data) + PHRASES_RU.answer.confirm,
            reply_markup=ikb.confirm_keyboard()
        )
