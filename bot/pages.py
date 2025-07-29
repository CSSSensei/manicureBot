from typing import Union
from phrases import PHRASES_RU

from DB.tables.queries import QueriesTable
from DB.tables.users import UsersTable
from config import bot
from config.const import USERS_PER_PAGE, QUERIES_PER_PAGE
from utils import format_list
from bot import keyboards


async def get_users(user_id: int, page: int = 1, message_id: Union[int, None] = None):
    with UsersTable() as users_db:
        users, pagination = users_db.get_all_users(page, USERS_PER_PAGE)

        txt = format_list.format_user_list(users, pagination)
        reply_markup = keyboards.inline.page_keyboard(action=1, pagination=pagination)

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

        reply_markup = keyboards.inline.page_keyboard(
            action=2,
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
