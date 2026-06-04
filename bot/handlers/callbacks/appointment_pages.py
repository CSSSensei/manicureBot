import datetime

from aiogram import Router
from aiogram.types import CallbackQuery

from bot import scheduler
from bot.bot_utils import msg_sender
from bot.bot_utils.models import BookingPageCallBack, BookingStatusCallBack, PhotoAppCallBack
from bot.bot_utils.msg_sender import get_media_from_photos
from bot.keyboards.default import inline as ikb
from bot.pages import get_active_bookings, get_day_range, get_master_apps
from bot.scheduler import SlotNotifierBot
from config import bot, const
from config.const import AppListMode, AppointmentPageAction
from DB.tables.appointments import AppointmentsTable
from DB.tables.masters import MastersTable
from phrases import PHRASES_RU

router = Router()


@router.callback_query(BookingPageCallBack.filter())
async def booking_page_distributor(callback: CallbackQuery, callback_data: BookingPageCallBack):
    page = callback_data.page
    action = callback_data.action
    mode = callback_data.mode
    if action is not None and callback_data.mode == AppListMode.MASTER and action != AppointmentPageAction.BACK_TO_MAP:
        with MastersTable() as master_db:
            master = master_db.get_master(callback.from_user.id)
            if not master or not master.is_master:
                await callback.answer(PHRASES_RU.error.no_rights)
                await callback.message.delete()
                return
    await callback.answer()
    if page is None:  # пустой коллбэк
        return
    if action in {const.AppointmentPageAction.SET_CANCELLED, const.AppointmentPageAction.BACK, const.AppointmentPageAction.BACK_TO_MAP}:
        match action, mode:
            case (const.AppointmentPageAction.SET_CANCELLED, _):
                await callback.message.edit_reply_markup(
                    reply_markup=ikb.user_cancel_keyboard(
                        callback_data.app_id,
                        page,
                        mode,
                        callback_data.app_date))
                return
            case (const.AppointmentPageAction.BACK, AppListMode.USER):
                with AppointmentsTable() as app_db:
                    app, pagination = app_db.get_client_appointments(callback.from_user.id, page)
                    await callback.message.edit_reply_markup(
                        reply_markup=ikb.booking_page_keyboard(
                            app,
                            pagination,
                            mode))
                return
            case (const.AppointmentPageAction.BACK, AppListMode.MASTER):
                with AppointmentsTable() as app_db:
                    start_of_day, end_of_day = get_day_range(callback_data.app_date)
                    apps, pagination = app_db.get_appointments_by_status_and_time_range(const.CONFIRMED,
                                                                                        start_of_day,
                                                                                        end_of_day,
                                                                                        page)
                    await callback.message.edit_reply_markup(
                        reply_markup=ikb.booking_page_keyboard(
                            apps[0],
                            pagination,
                            mode))
                return
            case (const.AppointmentPageAction.BACK_TO_MAP, AppListMode.MASTER):
                app_date = callback_data.app_date
                text, reply_markup = ikb.create_calendar_keyboard(app_date.month,
                                                                  app_date.year,
                                                                  True,
                                                                  const.CalendarMode.APPOINTMENT_MAP)
                await callback.message.edit_text(text=text, reply_markup=reply_markup)
                return
    match mode:
        case AppListMode.USER:
            await get_active_bookings(callback.from_user.id, page, callback.message.message_id)
        case AppListMode.MASTER:
            await get_master_apps(callback, callback_data.app_date, page)


@router.callback_query(BookingStatusCallBack.filter())
async def booking_status_distributor(callback: CallbackQuery, callback_data: BookingStatusCallBack):
    appointment_id = callback_data.app_id
    status = callback_data.status
    if status is None or appointment_id is None:  # пустой коллбэк
        await callback.answer()
        return
    with AppointmentsTable() as app_db:
        app = app_db.get_appointment_by_id(appointment_id)

        if status == const.CANCELLED:
            if app.status == const.REJECTED:
                await callback.message.edit_text(PHRASES_RU.answer.status.already_rejected)

            elif app.status in {const.PENDING, const.CONFIRMED}:
                if app.status == const.CONFIRMED and datetime.datetime.now() + datetime.timedelta(hours=3) > app.slot.start_time:
                    await callback.message.edit_text(PHRASES_RU.answer.too_late_to_cancel)
                    return

                success = AppointmentsTable.cancel_appointment(app, status)

                if success:
                    if app.status == const.CONFIRMED:
                        app.status = status
                        scheduler.cancel_scheduled_reminders(app)
                        await msg_sender.notify_master(app)
                    await SlotNotifierBot().update_channel_slots()
                    await callback.message.edit_text(PHRASES_RU.answer.notify.client.app_cancelled_by_user)
                else:
                    await callback.message.edit_text(PHRASES_RU.error.booking.try_again)
        elif status == const.REJECTED:
            with MastersTable() as master_db:
                master = master_db.get_master(callback.from_user.id)
                if not master or not master.is_master:
                    await callback.answer(PHRASES_RU.error.no_rights)
                    await callback.message.delete()
                    return
            if app.status == const.CANCELLED:
                await callback.message.edit_text(PHRASES_RU.answer.status.already_cancelled)

            elif app.status in {const.CONFIRMED}:
                success = AppointmentsTable.cancel_appointment(app, status)
                if success:
                    app.status = const.CANCELLED
                    scheduler.cancel_scheduled_reminders(app)
                    await msg_sender.notify_client(app)
                    await SlotNotifierBot().update_channel_slots()
                    await callback.message.edit_text(PHRASES_RU.answer.status.cancelled_by_master)
                else:
                    await callback.message.edit_text(PHRASES_RU.error.booking.try_again)
    await callback.answer()


@router.callback_query(PhotoAppCallBack.filter())
async def booking_photos_distributor(callback: CallbackQuery, callback_data: PhotoAppCallBack):
    await callback.answer()
    appointment_id = callback_data.app_id
    if appointment_id is None:  # пустой коллбэк
        return
    with AppointmentsTable() as app_db:
        appointment = app_db.get_appointment_by_id(appointment_id)
        if appointment and appointment.photos and len(appointment.photos) > 0:
            await bot.send_media_group(chat_id=callback.from_user.id,
                                       media=get_media_from_photos(appointment.photos),
                                       reply_to_message_id=callback.message.message_id)
        else:
            await callback.message.reply(text=PHRASES_RU.error.no_photos)
