import datetime
import logging
from typing import Optional

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.states import AppointmentStates
from phrases import PHRASES_RU
from bot.keyboards import inline_keyboards as ikb, user_keyboards as ukb


logger = logging.getLogger(__name__)


class AppointmentNavigation:
    STATES = {
        "WAITING_FOR_DATE": AppointmentStates.WAITING_FOR_DATE,
        "WAITING_FOR_SLOT": AppointmentStates.WAITING_FOR_SLOT,
        "WAITING_FOR_SERVICE": AppointmentStates.WAITING_FOR_SERVICE,
        "WAITING_FOR_PHOTOS": AppointmentStates.WAITING_FOR_PHOTOS,
        "WAITING_FOR_COMMENT": AppointmentStates.WAITING_FOR_COMMENT,
        "CONFIRMATION": AppointmentStates.CONFIRMATION
    }

    FLOW_ORDER = [
        "WAITING_FOR_DATE",
        "WAITING_FOR_SLOT",
        "WAITING_FOR_SERVICE",
        "WAITING_FOR_PHOTOS",
        "WAITING_FOR_COMMENT",
        "CONFIRMATION"
    ]

    @classmethod
    def get_next_state(cls, current_state: str) -> Optional[str]:
        """Возвращает следующее состояние в процессе записи"""
        try:
            current_index = cls.FLOW_ORDER.index(current_state)
            if current_index + 1 < len(cls.FLOW_ORDER):
                return cls.FLOW_ORDER[current_index + 1]
        except ValueError:
            pass
        return None

    @classmethod
    def get_prev_state(cls, current_state: str) -> Optional[str]:
        """Возвращает предыдущее состояние в процессе записи"""
        try:
            current_index = cls.FLOW_ORDER.index(current_state)
            if current_index > 0:
                return cls.FLOW_ORDER[current_index - 1]
        except ValueError:
            pass
        return None

    @classmethod
    async def handle_navigation(
            cls,
            callback: CallbackQuery,
            state: FSMContext,
            current_state: str,
            action: int,
            additional_checks: Optional[callable] = None
    ):
        prev_state = AppointmentNavigation.get_prev_state(current_state)
        next_state = AppointmentNavigation.get_next_state(current_state)
        if action == 0:  # Отмена
            await state.clear()
            await callback.message.edit_text(text=PHRASES_RU.answer.booking_canceled, reply_markup=None)
            return

        if action == -1 and prev_state:  # Назад
            await state.set_state(cls.STATES[prev_state])
            await cls.show_prev_step(callback, state, prev_state)
            return

        if action == 1 and next_state:  # Далее
            if additional_checks and not await additional_checks(state):
                await callback.answer(PHRASES_RU.error.booking.missing_data)
                return

            await state.set_state(cls.STATES[next_state])
            await cls.show_next_step(callback, state, next_state)
            return

    @classmethod
    async def show_prev_step(cls, callback: CallbackQuery, state: FSMContext, prev_state: str):
        clear_data = {
            "WAITING_FOR_DATE": {'slot_date': None},
            "WAITING_FOR_SLOT": {'slot_id': None},
            "WAITING_FOR_SERVICE": {'service_id': None},
            "WAITING_FOR_PHOTOS": {'photos': None},
            "WAITING_FOR_COMMENT": {'text': None}
        }

        # Получаем текущие данные
        data = await state.get_data()

        if prev_state in clear_data:
            await state.update_data(clear_data[prev_state])

        handlers = {
            "WAITING_FOR_DATE": show_date_selection,
            "WAITING_FOR_SLOT": show_slot_selection,
            "WAITING_FOR_SERVICE": show_service_selection,
            "WAITING_FOR_PHOTOS": show_photo_upload,
            "WAITING_FOR_COMMENT": show_comment_input
        }
        await handlers[prev_state](callback, data)

    @classmethod
    async def show_next_step(cls, callback: CallbackQuery, state: FSMContext, next_state: str):
        data = await state.get_data()
        handlers = {
            "WAITING_FOR_SERVICE": show_service_selection,
            "WAITING_FOR_PHOTOS": show_photo_upload,
            "WAITING_FOR_COMMENT": show_comment_input,
            "CONFIRMATION": show_confirmation
        }
        await handlers[next_state](callback, data)


async def show_date_selection(callback: CallbackQuery, data: dict):
    current_date = datetime.datetime.now()
    current_month = current_date.month
    current_year = current_date.year
    await callback.message.edit_text(PHRASES_RU.answer.choose_date, reply_markup=ikb.month_keyboard(current_month, current_year, False))


async def show_slot_selection(callback: CallbackQuery, data: dict):
    if 'slot_date' in data:
        await callback.message.edit_text(
            PHRASES_RU.answer.choose_slot,
            reply_markup=ikb.slots_keyboard(data['slot_date'])
        )
    else:
        logger.error(f'Appointment creation error: no slot date in state data')
        await callback.message.edit_text(PHRASES_RU.error.booking.try_again, reply_markup=None)


async def show_service_selection(callback: CallbackQuery, data: dict):
    await callback.message.edit_text(
        text=PHRASES_RU.answer.choose_service,
        reply_markup=ikb.service_keyboard()
    )


async def show_photo_upload(callback: CallbackQuery, data: dict):
    await callback.message.edit_text(
        text=PHRASES_RU.answer.send_photo,
        reply_markup=ikb.photo_keyboard()
    )


async def show_comment_input(callback: CallbackQuery, data: dict):
    await callback.message.edit_text(
        text=PHRASES_RU.answer.send_comment,
        reply_markup=ikb.comment_keyboard()
    )


async def show_confirmation(callback: CallbackQuery, data: dict):
    await callback.message.edit_text(
        text=PHRASES_RU.replace('answer.confirm', data=data),
        reply_markup=ikb.confirm_keyboard()
    )
