from aiogram import Router
from aiogram.types import CallbackQuery, InputMediaPhoto

from DB.tables.appointments import AppointmentsTable
from DB.tables.slots import SlotsTable
from bot.pages import get_active_bookings
from bot.utils.models import BookingPageCallBack, BookingStatusCallBack, PhotoAppCallBack
from bot.keyboards.default import inline as ikb
from config import bot
from config import const
from phrases import PHRASES_RU

router = Router()


@router.callback_query(BookingPageCallBack.filter())
async def booking_page_distributor(callback: CallbackQuery, callback_data: BookingPageCallBack):
    await callback.answer()
    page = callback_data.page
    action = callback_data.action
    if page is None:  # пустой коллбэк
        return
    if action in {const.CANCELLED, const.BACK}:
        with AppointmentsTable() as app_db:
            app, pagination = app_db.get_client_appointments(callback.from_user.id, page)
        match action:
            case const.CANCELLED:
                await callback.message.edit_reply_markup(
                    reply_markup=ikb.user_cancel_keyboard(
                        app.appointment_id,
                        page))
                return
            case const.BACK:
                await callback.message.edit_reply_markup(
                    reply_markup=ikb.booking_page_keyboard(
                        app,
                        pagination))
                return
    await get_active_bookings(callback.from_user.id, page, callback.message.message_id)


@router.callback_query(BookingStatusCallBack.filter())
async def booking_status_distributor(callback: CallbackQuery, callback_data: BookingStatusCallBack):
    await callback.answer()
    appointment_id = callback_data.app_id
    status = callback_data.status
    if status is None or appointment_id is None:  # пустой коллбэк
        return
    with AppointmentsTable() as app_db, SlotsTable() as slots_db:
        if status == const.CANCELLED:
            app_db.update_appointment_status(appointment_id, status)
            appointment = app_db.get_appointment_by_id(appointment_id)
            slots_db.set_slot_availability(appointment.slot.id, True)
            await callback.message.edit_text(PHRASES_RU.answer.status.cancelled)


@router.callback_query(PhotoAppCallBack.filter())
async def booking_photos_distributor(callback: CallbackQuery, callback_data: PhotoAppCallBack):
    await callback.answer()
    appointment_id = callback_data.app_id
    if appointment_id is None:  # пустой коллбэк
        return
    with AppointmentsTable() as app_db:
        appointment = app_db.get_appointment_by_id(appointment_id)
        if appointment and appointment.photos and len(appointment.photos) > 0:
            media: list[InputMediaPhoto] = []
            for photo in appointment.photos:
                media.append(InputMediaPhoto(media=photo.telegram_file_id))
            await bot.send_media_group(chat_id=callback.from_user.id,
                                       media=media[:9],
                                       reply_to_message_id=callback.message.message_id)
        else:
            await callback.message.reply(text=PHRASES_RU.error.no_photos)
