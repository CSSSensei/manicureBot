import datetime
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InputMediaPhoto

from bot import keyboards
from bot.bot_utils.msg_sender import send_or_edit_message
from bot.keyboards.admin import inline as admin_ikb
from bot.keyboards.master import inline as master_ikb
from config.const import (
    ACTIONS_PER_PAGE,
    CONFIRMED,
    PENDING,
    QUERIES_PER_PAGE,
    USERS_PER_PAGE,
    AppListMode,
    PageListSection,
)
from DB.models import AppointmentModel, Pagination
from DB.tables.appointments import AppointmentsTable
from DB.tables.masters import MastersTable
from DB.tables.queries import QueriesTable
from DB.tables.users import UsersTable
from phrases import PHRASES_RU
from utils import format_list, format_string

logger = logging.getLogger(__name__)


async def get_users(bot: Bot, user_id: int, message_id: int | None = None, page: int = 1):
    with UsersTable() as users_db:
        users, pagination = users_db.get_all_users(page, USERS_PER_PAGE)

        txt = format_list.format_user_list(users, pagination)
        reply_markup = admin_ikb.page_keyboard(type_of_event=PageListSection.USERS, pagination=pagination)

        if message_id:
            await bot.edit_message_text(chat_id=user_id, message_id=message_id, text=txt, reply_markup=reply_markup)
        else:
            await bot.send_message(chat_id=user_id, text=txt, reply_markup=reply_markup)


async def user_query(bot: Bot, user_id: int, user_id_to_find: int | None, message_id: int | None = None, page: int = 1):
    with QueriesTable() as queries_db, UsersTable() as users_db:
        queries, pagination = queries_db.get_user_queries(user_id_to_find, page, QUERIES_PER_PAGE)
        if not user_id_to_find or not queries:
            await bot.send_message(chat_id=user_id, text=PHRASES_RU.error.no_query)
            return

        user = users_db.get_user(user_id_to_find)

        username_display = f'@{user.username}' if user and user.username else user.first_name if user else None

        txt = format_list.format_queries_text(
            queries=queries,
            name=username_display,
            user_id=user_id_to_find,
            footnote_template=PHRASES_RU.footnote.user_query,
            line_template=PHRASES_RU.template.user_query,
        )

        reply_markup = admin_ikb.page_keyboard(
            type_of_event=PageListSection.QUERY, pagination=pagination, user_id=user_id_to_find
        )

        if message_id:
            await bot.edit_message_text(chat_id=user_id, message_id=message_id, text=txt, reply_markup=reply_markup)
        else:
            await bot.send_message(chat_id=user_id, text=txt, reply_markup=reply_markup)


async def get_active_bookings(bot: Bot, user_id: int, page: int = 1, message_id: int | None = None):
    with AppointmentsTable() as app_db:
        app, pagination = app_db.get_client_appointments(user_id, page)
        if pagination.total_items > 0:
            if not app:
                await send_or_edit_message(
                    bot, chat_id=user_id, message_id=message_id, text=PHRASES_RU.error.booking.try_again
                )
                return
            await _send_appointment_message(bot, user_id, app, pagination, message_id)
        else:
            await send_or_edit_message(
                bot,
                message_id=message_id,
                chat_id=user_id,
                text=PHRASES_RU.replace('answer.no_active_bookings', booking=PHRASES_RU.button.booking),
            )


def get_day_range(date: datetime.date) -> tuple[datetime.datetime, datetime.datetime]:
    start_of_day = datetime.datetime.combine(date, datetime.time.min)
    end_of_day = datetime.datetime.combine(date, datetime.time.max)
    return start_of_day, end_of_day


async def get_master_apps(bot: Bot, callback: CallbackQuery, date: datetime.date, page: int = 1):
    start_of_day, end_of_day = get_day_range(date)

    with AppointmentsTable() as app_db:
        app, pagination = app_db.get_appointments_by_status_and_time_range(CONFIRMED, start_of_day, end_of_day, page)
        if not app:
            await callback.message.edit_text(text=PHRASES_RU.error.booking.try_again)
            return
        await _send_appointment_message(
            bot, callback.from_user.id, app[0], pagination, callback.message.message_id, AppListMode.MASTER
        )


async def _send_appointment_message(
    bot: Bot,
    user_id: int,
    app: AppointmentModel,
    pagination: Pagination,
    message_id: int | None = None,
    mode: AppListMode = AppListMode.USER,
):
    caption = PHRASES_RU.error.unknown
    match mode:
        case AppListMode.USER:
            caption = format_string.user_sent_booking(app, PHRASES_RU.replace('title.booking', date=app.formatted_date))
        case AppListMode.MASTER:
            caption = format_string.master_sent_booking(
                app, PHRASES_RU.replace('title.booking', date=app.formatted_date)
            )
    await send_or_edit_message(
        bot,
        chat_id=user_id,
        text=caption,
        reply_markup=keyboards.default.inline.booking_page_keyboard(app, pagination, mode),
        message_id=message_id,
    )


async def update_master_booking_ui(bot: Bot, data: AppointmentModel):
    with MastersTable() as masters_db, AppointmentsTable() as app_db:
        total_items = app_db.count_appointments(PENDING)
        masters = masters_db.get_all_masters()

        if masters and len(masters) > 0:
            master = masters[0]
            if not master.message_id:
                msg_to_delete = None
                caption = format_string.master_booking_text(data, total_items)
                reply_to = None
                if data.photos and len(data.photos) > 0:
                    media: list[InputMediaPhoto] = []
                    for photo in data.photos:
                        media.append(InputMediaPhoto(media=photo.telegram_file_id))
                    msgs = await bot.send_media_group(chat_id=master.user.user_id, media=media[:9])
                    reply_to = msgs[0].message_id
                    msg_to_delete = f'{msgs[0].message_id},{msgs[-1].message_id}'

                msg = await bot.send_message(
                    chat_id=master.user.user_id,
                    text=caption,
                    reply_markup=master_ikb.action_master_keyboard(
                        appointment_id=data.appointment_id, msg_to_delete=msg_to_delete
                    ),
                    reply_to_message_id=reply_to,
                )
                masters_db.update_current_state(master.user.user_id, msg.message_id, data.appointment_id, msg_to_delete)
            else:
                current_app = app_db.get_appointment_by_id(master.current_app_id)
                if current_app.status != PENDING:
                    total_items += 1
                caption = format_string.master_booking_text(current_app, total_items)
                try:
                    await bot.edit_message_text(
                        chat_id=master.user.user_id,
                        message_id=master.message_id,
                        text=caption,
                        reply_markup=master_ikb.action_master_keyboard(
                            appointment_id=master.current_app_id, msg_to_delete=master.msg_to_delete
                        ),
                    )
                except TelegramBadRequest as e:
                    if 'message is not modified' in str(e):
                        pass
                    else:
                        logger.error('TelegramBadRequest while editing message: %s', e, exc_info=True)


async def get_history(bot: Bot, user_id: int, message_id: int | None = None, page: int = 1):
    with AppointmentsTable() as app_db:
        appointments, pagination = app_db.get_master_actions(page, ACTIONS_PER_PAGE)

        txt = format_list.format_app_actions(appointments, pagination)
        reply_markup = master_ikb.master_page_keyboard(
            type_of_event=PageListSection.ACTION_HISTORY, pagination=pagination
        )
        if message_id:
            await bot.edit_message_text(chat_id=user_id, message_id=message_id, text=txt, reply_markup=reply_markup)
        else:
            await bot.send_message(chat_id=user_id, text=txt, reply_markup=reply_markup)


async def get_clients(bot: Bot, user_id: int, message_id: int, page: int = 1):
    with AppointmentsTable() as db:
        clients, pagination = db.get_clients_with_stats(page, USERS_PER_PAGE)

        txt = format_list.format_client_list(clients, pagination)
        reply_markup = master_ikb.master_page_keyboard(type_of_event=PageListSection.CLIENTS, pagination=pagination)

        if message_id:
            await bot.edit_message_text(chat_id=user_id, message_id=message_id, text=txt, reply_markup=reply_markup)
        else:
            await bot.send_message(chat_id=user_id, text=txt, reply_markup=reply_markup)
