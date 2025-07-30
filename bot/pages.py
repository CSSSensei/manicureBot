from typing import Union
from aiogram.types import InputMediaPhoto

from DB.models import AppointmentModel, Pagination
from DB.tables.appointments import AppointmentsTable
from phrases import PHRASES_RU
from DB.tables.queries import QueriesTable
from DB.tables.users import UsersTable
from config import bot
from config.const import USERS_PER_PAGE, QUERIES_PER_PAGE
from utils import format_list
from bot import keyboards
from utils.format_string import user_sent_booking


async def get_users(user_id: int, page: int = 1, message_id: Union[int, None] = None):
    with UsersTable() as users_db:
        users, pagination = users_db.get_all_users(page, USERS_PER_PAGE)

        txt = format_list.format_user_list(users, pagination)
        reply_markup = keyboards.admin.inline.page_keyboard(type_of_event=1, pagination=pagination)

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

        txt = format_list.format_queries_text(
            queries=queries,
            username=user.username if user else None,
            user_id=user_id_to_find,
            footnote_template=PHRASES_RU.footnote.user_query,
            line_template=PHRASES_RU.template.user_query
        )

        reply_markup = keyboards.admin.inline.page_keyboard(
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


async def get_active_bookings(user_id: int, page=1):
    with AppointmentsTable() as app_db:
        app, pagination = app_db.get_client_appointments(user_id, page)
        if pagination.total_items > 0:
            await send_user_app(app, pagination)
        else:
            await bot.send_message(chat_id=user_id, text=PHRASES_RU.replace('answer.no_active_bookings', booking=PHRASES_RU.button.booking),
                                   reply_markup=keyboards.default.base.keyboard)


async def send_user_app(app: AppointmentModel, pagination: Pagination):
    caption = user_sent_booking(app)
    reply_to = None
    msg_to_delete = None
    if app.photos and len(app.photos) > 0:
        media: list[InputMediaPhoto] = []
        for photo in app.photos:
            media.append(InputMediaPhoto(media=photo.telegram_file_id))

        msgs = await bot.send_media_group(chat_id=app.client.user_id, media=media[:9])
        msg_to_delete = f'{msgs[0].message_id},{msgs[-1].message_id}'
        reply_to = msgs[0].message_id
    await bot.send_message(chat_id=app.client.user_id, text=caption, reply_to_message_id=reply_to,
                           reply_markup=keyboards.default.inline.booking_page_keyboard(pagination, msg_to_delete))
