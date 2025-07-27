import datetime
import logging
from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

import bot.keyboards.inline_keyboards as ikb
from DB.models import UserModel, PhotoModel
from DB.tables.appointment_photos import AppointmentPhotosTable
from DB.tables.appointments import AppointmentsTable
from DB.tables.masters import MastersTable
from DB.tables.photos import PhotosTable
from DB.tables.slots import SlotsTable
from bot.filters import IsCancelActionFilter
from bot.keyboards.inline_keyboards import slots_keyboard
from bot.models import CutMessageCallBack, MonthCallBack, ServiceCallBack, ActionButtonCallBack, SlotCallBack
from bot import pages
from bot.navigation import AppointmentNavigation
from bot.states import AppointmentStates
from config import bot
from phrases import PHRASES_RU

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(CutMessageCallBack.filter())
async def cut_message_distributor(callback: CallbackQuery, callback_data: CutMessageCallBack):
    action = callback_data.action
    page = callback_data.page
    user_id = callback_data.user_id
    if action == 1:
        await pages.get_users(callback.from_user.id, page, callback.message.message_id)
    elif action == 2:
        await pages.user_query(callback.from_user.id, user_id, page, callback.message.message_id)
    elif action == -1:
        await callback.answer()


@router.callback_query(MonthCallBack.filter(), StateFilter(AppointmentStates.WAITING_FOR_DATE))
async def handle_month_selection(callback: CallbackQuery, callback_data: MonthCallBack, state: FSMContext):
    if callback_data.action != 0:
        # Обработка переключения месяцев
        month = callback_data.month + callback_data.action
        year = callback_data.year

        if month > 12:
            year += 1
            month = 1
        elif month < 1:
            year -= 1
            month = 12

        prev_enabled = not (month == datetime.datetime.now().month and year == datetime.datetime.now().year)
        await callback.message.edit_reply_markup(
            reply_markup=ikb.month_keyboard(month, year, prev_enabled)
        )
        return

    if not all([callback_data.day > 0, callback_data.month > 0, callback_data.year > 0]):
        await callback.answer(text=PHRASES_RU.error.date)
        return

    selected_date = datetime.datetime(callback_data.year, callback_data.month, callback_data.day)
    await state.set_state(AppointmentStates.WAITING_FOR_SLOT)
    await state.update_data(slot_date=selected_date)
    await callback.message.edit_text(
        PHRASES_RU.answer.choose_slot,
        reply_markup=slots_keyboard(selected_date)
    )


@router.callback_query(SlotCallBack.filter(), StateFilter(AppointmentStates.WAITING_FOR_SLOT))
async def handle_slot_selection(callback: CallbackQuery, callback_data: SlotCallBack, state: FSMContext):
    await state.update_data(slot_id=callback_data.slot_id, message_id=callback.message.message_id)

    await AppointmentNavigation.handle_navigation(
        callback=callback,
        state=state,
        current_state="WAITING_FOR_SLOT",
        action=1
    )


@router.callback_query(ServiceCallBack.filter(), StateFilter(AppointmentStates.WAITING_FOR_SERVICE))
async def handle_service_selection(callback: CallbackQuery, callback_data: ServiceCallBack, state: FSMContext):
    await state.update_data(service_id=callback_data.service_id)

    await AppointmentNavigation.handle_navigation(
        callback=callback,
        state=state,
        current_state="WAITING_FOR_SERVICE",
        action=1
    )


@router.callback_query(
    ActionButtonCallBack.filter(),
    StateFilter(AppointmentStates.CONFIRMATION),
    ~IsCancelActionFilter()
)
async def handle_appointment_confirmation(
        callback: CallbackQuery,
        callback_data: ActionButtonCallBack,
        state: FSMContext,
        user_row: UserModel
):
    if callback_data.action == -1:
        await AppointmentNavigation.handle_navigation(
            callback=callback,
            state=state,
            current_state="CONFIRMATION",
            action=-1
        )
        return

    data = await state.get_data()
    if not is_valid_appointment_data(data, user_row):
        await clear_and_respond(callback, state, PHRASES_RU.error.booking.no_contacts)
        # TODO no contacts
        return

    try:
        success = await process_appointment_creation(callback.from_user.id, data)
        message = (PHRASES_RU.answer.confirmation_wait if success
                   else PHRASES_RU.error.booking.occupied_slot)

        if success:
            await notify_master(data)

        await clear_and_respond(callback, state, message)
    except Exception as e:
        logger.error(f'Appointment creation error: {e}')
        await clear_and_respond(callback, state, PHRASES_RU.error.booking.try_again)


@router.callback_query(ActionButtonCallBack.filter(), StateFilter(*AppointmentNavigation.STATES.values()))
async def handle_navigation_actions(callback: CallbackQuery, callback_data: ActionButtonCallBack, state: FSMContext):
    current_state = await state.get_state()
    state_mapping = {v: k for k, v in AppointmentNavigation.STATES.items()}

    await AppointmentNavigation.handle_navigation(
        callback=callback,
        state=state,
        current_state=state_mapping[current_state],
        action=callback_data.action
    )


async def notify_master(data: dict):
    with MastersTable() as masters_db:
        masters = masters_db.get_all_masters()
        if masters:
            await bot.send_message(chat_id=masters[0].id, text=repr(data))


async def clear_and_respond(callback: CallbackQuery, state: FSMContext, message: str):
    """Очищает состояние и отправляет ответ"""
    await state.clear()
    await callback.message.edit_text(text=message, reply_markup=None)


def is_valid_appointment_data(data: dict, user_row: UserModel) -> bool:
    """Проверяет валидность данных для записи"""
    required_fields = ['slot_id', 'service_id']
    contact_info = any([user_row.username, user_row.phone_number])

    return all(data.get(field) for field in required_fields) and contact_info


async def process_appointment_creation(user_id: int, data: dict) -> bool:
    """Создает запись и возвращает статус успешности"""
    with SlotsTable() as slots_db, AppointmentsTable() as app_db:
        if not slots_db.reserve_slot(data['slot_id']):
            return False

        app_id = app_db.create_appointment(
            client_id=user_id,
            slot_id=data['slot_id'],
            service_id=data['service_id'],
            comment=data.get('text')
        )

        await process_appointment_photos(app_id, data.get('photos', []))
        return True


async def process_appointment_photos(app_id: int, photos: list[PhotoModel]):
    """Обрабатывает прикрепленные фото"""
    for photo in photos:
        with PhotosTable() as photo_db, AppointmentPhotosTable() as app_photo_db:
            photo_id = photo_db.add_photo(
                telegram_file_id=photo.telegram_file_id,
                file_unique_id=photo.file_unique_id,
                caption=photo.caption
            )
            app_photo_db.add_photo_to_appointment(app_id, photo_id)


@router.callback_query()
async def _(callback: CallbackQuery, state: FSMContext):
    print('Пустой колбек', callback.__dict__, await state.get_state())
    await callback.answer()
