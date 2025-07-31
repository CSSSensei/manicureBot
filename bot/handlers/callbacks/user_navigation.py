from datetime import datetime
import logging
from typing import Optional

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

import bot.keyboards.default.inline as ikb
from DB.models import PhotoModel, UserModel, AppointmentModel, SlotModel, ServiceModel
from DB.tables.appointment_photos import AppointmentPhotosTable
from DB.tables.appointments import AppointmentsTable
from DB.tables.photos import PhotosTable
from DB.tables.services import ServicesTable
from DB.tables.slots import SlotsTable
from bot.utils.filters import IsCancelActionFilter
from bot.utils.models import MonthCallBack, ServiceCallBack, ActionButtonCallBack, SlotCallBack

from bot.navigation import AppointmentNavigation
from bot.states import AppointmentStates
from phrases import PHRASES_RU
from bot import pages

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(MonthCallBack.filter(), StateFilter(AppointmentStates.WAITING_FOR_DATE))
async def handle_month_selection(callback: CallbackQuery, callback_data: MonthCallBack, state: FSMContext):
    if callback_data.action != 0:
        # Обработка переключения месяцев
        month = callback_data.month + callback_data.action
        year = callback_data.year
        year += month // 12 if month > 12 else -1 if month < 1 else 0
        month = 1 if month > 12 else 12 if month < 1 else month

        prev_enabled = not (month == datetime.now().month and year == datetime.now().year)
        await callback.message.edit_reply_markup(
            reply_markup=ikb.month_keyboard(month, year, prev_enabled)
        )
        return
    if callback_data.day <= 0:
        await callback.answer(PHRASES_RU.error.date)
        return
    selected_date = datetime(callback_data.year, callback_data.month, callback_data.day)
    await AppointmentNavigation.update_appointment_data(state, slot_date=selected_date, message_id=callback.message.message_id)
    await AppointmentNavigation.handle_navigation(
        callback=callback,
        state=state,
        current_state="WAITING_FOR_DATE",
        action=1
    )


@router.callback_query(SlotCallBack.filter(), StateFilter(AppointmentStates.WAITING_FOR_SLOT))
async def handle_slot_selection(callback: CallbackQuery, callback_data: SlotCallBack, state: FSMContext):
    with SlotsTable() as slots_db:
        slot = slots_db.get_slot(callback_data.slot_id)
        await AppointmentNavigation.update_appointment_data(
            state,
            slot=SlotModel(id=callback_data.slot_id,
                           start_time=slot.start_time,
                           end_time=slot.end_time,
                           is_available=False)
        )

    await AppointmentNavigation.handle_navigation(
        callback=callback,
        state=state,
        current_state="WAITING_FOR_SLOT",
        action=1
    )


@router.callback_query(ServiceCallBack.filter(), StateFilter(AppointmentStates.WAITING_FOR_SERVICE))
async def handle_service_selection(callback: CallbackQuery, callback_data: ServiceCallBack, state: FSMContext):
    with ServicesTable() as service_db:
        await AppointmentNavigation.update_appointment_data(
            state,
            service=ServiceModel(
                id=callback_data.service_id,
                name=service_db.get_service(callback_data.service_id).name
            )
        )

    await AppointmentNavigation.handle_navigation(
        callback=callback,
        state=state,
        current_state="WAITING_FOR_SERVICE",
        action=1
    )


@router.callback_query(
    ActionButtonCallBack.filter(),
    StateFilter(AppointmentStates.CONFIRMATION),
    ~IsCancelActionFilter())
async def handle_appointment_confirmation(callback: CallbackQuery, callback_data: ActionButtonCallBack, state: FSMContext, user_row: UserModel):
    if callback_data.action == -1:
        await AppointmentNavigation.handle_navigation(
            callback=callback,
            state=state,
            current_state="CONFIRMATION",
            action=-1
        )
        return

    data = await AppointmentNavigation.get_appointment_data(state)

    try:
        app_id = await process_appointment_creation(callback.from_user.id, data)
        message = (PHRASES_RU.answer.confirmation_wait if app_id
                   else PHRASES_RU.error.booking.occupied_slot)

        if app_id:
            data.client = UserModel(
                user_id=callback.from_user.id,
                username=callback.from_user.username,
                contact=user_row.contact)
            data.appointment_id = app_id
            await pages.notify_master(data)

        await clear_and_respond(callback, state, message)
    except Exception as e:
        logger.error(
            f'Appointment creation error for user {callback.from_user.id}: {e}',
            exc_info=True
        )
        await clear_and_respond(callback, state, PHRASES_RU.error.booking.try_again)


@router.callback_query(ActionButtonCallBack.filter(), StateFilter(*AppointmentNavigation.STATES.values()))
async def handle_navigation_actions(
        callback: CallbackQuery,
        callback_data: ActionButtonCallBack,
        state: FSMContext):
    current_state = await state.get_state()
    state_name = next(k for k, v in AppointmentNavigation.STATES.items() if v == current_state)

    await AppointmentNavigation.handle_navigation(
        callback=callback,
        state=state,
        current_state=state_name,
        action=callback_data.action,
    )


async def clear_and_respond(callback: CallbackQuery, state: FSMContext, message: str):
    """Очищает состояние и отправляет ответ"""
    await state.clear()
    await callback.message.edit_text(text=message, reply_markup=None)


async def process_appointment_creation(user_id: int, data: AppointmentModel) -> Optional[int]:
    """Создает запись и возвращает статус успешности"""
    if not data.is_ready_for_confirmation():
        return None

    with SlotsTable() as slots_db, AppointmentsTable() as app_db:
        if not slots_db.set_slot_availability(data.slot.id, False):
            return None

        app_id = app_db.create_appointment(
            client_id=user_id,
            slot_id=data.slot.id,
            service_id=data.service.id,
            comment=data.comment
        )

        await _process_appointment_photos(app_id, data.photos)
        return app_id


async def _process_appointment_photos(app_id: int, photos: list[PhotoModel]):
    """Обрабатывает прикрепленные фото"""
    if not photos:
        return

    with PhotosTable() as photo_db, AppointmentPhotosTable() as app_photo_db:
        for photo in photos:
            photo_id = photo_db.add_photo(
                telegram_file_id=photo.telegram_file_id,
                file_unique_id=photo.file_unique_id,
                caption=photo.caption
            )
            app_photo_db.add_photo_to_appointment(app_id, photo_id)


@router.callback_query(MonthCallBack.filter())
@router.callback_query(ServiceCallBack.filter())
@router.callback_query(ActionButtonCallBack.filter())
@router.callback_query(SlotCallBack.filter())
async def _(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(PHRASES_RU.error.booking.try_again, reply_markup=None)


@router.callback_query()
async def _(callback: CallbackQuery, state: FSMContext):
    print('Пустой колбек', callback.__dict__, await state.get_state())
    await callback.answer()
