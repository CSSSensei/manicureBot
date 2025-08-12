import logging
import datetime
from typing import Union, Optional
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InputMediaPhoto, CallbackQuery

from DB.models import AppointmentModel, Pagination
from DB.tables.appointments import AppointmentsTable
from DB.tables.masters import MastersTable
from bot.bot_utils.msg_sender import send_or_edit_message
from phrases import PHRASES_RU
from DB.tables.queries import QueriesTable
from DB.tables.users import UsersTable
from config import bot
from config.const import USERS_PER_PAGE, ACTIONS_PER_PAGE, QUERIES_PER_PAGE, PENDING, AppListMode, CONFIRMED
from utils.format_list import format_user_list, format_queries_text, format_app_actions
from utils.format_string import user_sent_booking, master_booking_text, master_sent_booking
from bot import keyboards
from bot.keyboards.admin import inline as admin_ikb
from bot.keyboards.master import inline as master_ikb

logger = logging.getLogger(__name__)


async def get_users(user_id: int, page: int = 1, message_id: Union[int, None] = None):
    with UsersTable() as users_db:
        users, pagination = users_db.get_all_users(page, USERS_PER_PAGE)

        txt = format_user_list(users, pagination)
        reply_markup = admin_ikb.page_keyboard(type_of_event=1, pagination=pagination)

        if message_id:
            await bot.edit_message_text(chat_id=user_id, message_id=message_id, text=txt,
                                        reply_markup=reply_markup)
        else:
            await bot.send_message(chat_id=user_id, text=txt, reply_markup=reply_markup)


async def user_query(user_id: int, user_id_to_find: Union[int, None], page: int = 1, message_id: Union[int, None] = None):
    with QueriesTable() as queries_db, UsersTable() as users_db:
        queries, pagination = queries_db.get_user_queries(user_id_to_find, page, QUERIES_PER_PAGE)
        if not user_id_to_find or not queries:
            await bot.send_message(chat_id=user_id, text=PHRASES_RU.error.no_query)
            return

        user = users_db.get_user(user_id_to_find)

        txt = format_queries_text(
            queries=queries,
            username=user.username if user else None,
            user_id=user_id_to_find,
            footnote_template=PHRASES_RU.footnote.user_query,
            line_template=PHRASES_RU.template.user_query
        )

        reply_markup = admin_ikb.page_keyboard(
            type_of_event=2,
            pagination=pagination,
            user_id=user_id_to_find
        )

        if message_id:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=txt,
                reply_markup=reply_markup
            )
        else:
            await bot.send_message(
                chat_id=user_id,
                text=txt,
                reply_markup=reply_markup
            )


async def get_active_bookings(user_id: int, page: int = 1, message_id: Optional[int] = None):
    with AppointmentsTable() as app_db:
        app, pagination = app_db.get_client_appointments(user_id, page)
        if pagination.total_items > 0:
            if not app:
                await send_or_edit_message(chat_id=user_id,
                                           message_id=message_id,
                                           text=PHRASES_RU.error.booking.try_again)
                return
            await _send_appointment_message(user_id, app, pagination, message_id)
        else:
            await send_or_edit_message(message_id=message_id,
                                       chat_id=user_id,
                                       text=PHRASES_RU.replace('answer.no_active_bookings',
                                                               booking=PHRASES_RU.button.booking))


def get_day_range(date: datetime.date) -> tuple[datetime.datetime, datetime.datetime]:
    start_of_day = datetime.datetime.combine(date, datetime.time.min)
    end_of_day = datetime.datetime.combine(date, datetime.time.max)
    return start_of_day, end_of_day


async def get_master_apps(callback: CallbackQuery, date: datetime.date, page: int = 1):
    start_of_day, end_of_day = get_day_range(date)

    with AppointmentsTable() as app_db:
        app, pagination = app_db.get_appointments_by_status_and_time_range(CONFIRMED, start_of_day, end_of_day, page)
        if not app:
            await callback.message.edit_text(text=PHRASES_RU.error.booking.try_again)
            return
        await _send_appointment_message(callback.from_user.id, app[0], pagination, callback.message.message_id, AppListMode.MASTER)


async def _send_appointment_message(user_id: int,
                                    app: AppointmentModel,
                                    pagination: Pagination,
                                    message_id: Optional[int] = None,
                                    mode: AppListMode = AppListMode.USER):
    caption = PHRASES_RU.error.unknown
    match mode:
        case AppListMode.USER:
            caption = user_sent_booking(app, PHRASES_RU.replace('title.booking', date=app.formatted_date))
        case AppListMode.MASTER:
            caption = master_sent_booking(app, PHRASES_RU.replace('title.booking', date=app.formatted_date))
    await send_or_edit_message(chat_id=user_id,
                               text=caption,
                               reply_markup=keyboards.default.inline.booking_page_keyboard(
                                   app,
                                   pagination,
                                   mode),
                               message_id=message_id)


async def update_master_booking_ui(data: AppointmentModel):
    with (MastersTable() as masters_db, AppointmentsTable() as app_db):
        total_items = app_db.count_appointments(PENDING)
        masters = masters_db.get_all_masters()

        if masters and len(masters) > 0:
            master = masters[0]
            if not master.message_id:
                msg_to_delete = None
                caption = master_booking_text(data, total_items)
                reply_to = None
                if data.photos and len(data.photos) > 0:
                    media: list[InputMediaPhoto] = []
                    for photo in data.photos:
                        media.append(InputMediaPhoto(media=photo.telegram_file_id))
                    msgs = await bot.send_media_group(chat_id=master.id, media=media[:9])
                    reply_to = msgs[0].message_id
                    msg_to_delete = f'{msgs[0].message_id},{msgs[-1].message_id}'

                msg = await bot.send_message(
                    chat_id=master.id,
                    text=caption,
                    reply_markup=master_ikb.action_master_keyboard(
                        appointment_id=data.appointment_id,
                        client=data.client,
                        msg_to_delete=msg_to_delete),
                    reply_to_message_id=reply_to)
                masters_db.update_current_state(master.id, msg.message_id, data.appointment_id, msg_to_delete)
            else:
                current_app = app_db.get_appointment_by_id(master.current_app_id)
                if current_app.status != PENDING:
                    total_items += 1
                caption = master_booking_text(current_app, total_items)
                try:
                    await bot.edit_message_text(chat_id=master.id,
                                                message_id=master.message_id,
                                                text=caption,
                                                reply_markup=master_ikb.action_master_keyboard(
                                                    appointment_id=master.current_app_id,
                                                    client=current_app.client,
                                                    msg_to_delete=master.msg_to_delete)
                                                )
                except TelegramBadRequest as e:
                    if "message is not modified" in str(e):
                        pass
                    else:
                        logger.error(
                            "TelegramBadRequest while editing message: %s",
                            e,
                            exc_info=True
                        )


async def get_history(user_id: int, page: int = 1, message_id: Optional[int] = None):
    with AppointmentsTable() as app_db:
        appointments, pagination = app_db.get_master_actions(page, ACTIONS_PER_PAGE)

        txt = format_app_actions(appointments, pagination)
        reply_markup = master_ikb.master_history_keyboard(pagination)
        if message_id:
            await bot.edit_message_text(chat_id=user_id, message_id=message_id, text=txt,
                                        reply_markup=reply_markup)
        else:
            await bot.send_message(chat_id=user_id, text=txt, reply_markup=reply_markup)
