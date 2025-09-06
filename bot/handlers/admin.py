import logging
from aiogram.types import Message

from DB.tables.masters import MastersTable
from phrases import PHRASES_RU
from DB.tables.queries import QueriesTable
from DB.tables.users import UsersTable
from utils import format_list
from bot import pages
from bot.bot_utils import command_arguments
from bot.bot_utils.routers import AdminRouter, BaseRouter
import temp

router = AdminRouter()
logger = logging.getLogger(__name__)


@router.command(('users', 'u'), 'таблица со всеми пользователями')  # /users
async def _(message: Message):
    await pages.get_users(message.from_user.id)


@router.command(('commands', 'cmds'), 'список всех доступных команд')  # /commands /cmds
async def command_getcmds(message: Message):
    commands_text = PHRASES_RU.title.commands
    admin_commands = '\n'.join(str(command) for command in BaseRouter.available_commands if command.is_admin)
    if admin_commands:
        commands_text += PHRASES_RU.subtitle.admin_commands + admin_commands + '\n\n'
    master_commands = '\n'.join(str(command) for command in BaseRouter.available_commands if command.is_master)
    if master_commands:
        commands_text += PHRASES_RU.subtitle.master_commands + master_commands
    user_commands = '\n'.join(str(command) for command in BaseRouter.available_commands if command.is_user)
    if user_commands:
        commands_text += PHRASES_RU.subtitle.user_commands + user_commands
    await message.answer(commands_text)


@router.command('promote', 'повысить уровень доступа', 'user_id')  # /promote
@command_arguments.user_id
async def _(message: Message, user_id):
    with UsersTable() as users_db:
        if users_db.set_admin(user_id, message.from_user.id, True):
            await message.answer(PHRASES_RU.replace('success.promoted_by', user_id=user_id))
        else:
            await message.answer(PHRASES_RU.error.db)


@router.command('demote', 'понизить уровень доступа', 'user_id')  # /demote
@command_arguments.user_id
async def _(message: Message, user_id):
    with UsersTable() as users_db:
        if users_db.set_admin(user_id, message.from_user.id, False):
            await message.answer(PHRASES_RU.replace('success.demoted', user_id=user_id))
        else:
            await message.answer(PHRASES_RU.error.db)


@router.command(('query', 'q'), 'последние N запросов', 'N')  # /query
@command_arguments.digit(default=5)
async def _(message: Message, amount: int):
    with QueriesTable() as queries_db:
        queries = queries_db.get_last_queries(int(amount))
        if not queries:
            await message.answer(PHRASES_RU.info.no_query)
            return

        txt = format_list.format_queries_text(
            queries=queries,
            footnote_template=PHRASES_RU.footnote.all_queries,
            line_template=PHRASES_RU.template.all_queries
        )

        if txt:
            await message.answer(txt.replace('\t', '\n'), disable_web_page_preview=True)


@router.command('clear_temp', 'очистка временных файлов')  # /clear_temp
async def _(message: Message):
    if temp.clear():
        logger.info(f'TEMP directory cleared by user {message.from_user.id} ({message.from_user.username})')
        await message.answer(text=PHRASES_RU.success.clear_temp)
    else:
        await message.answer(text=PHRASES_RU.error.clear_temp)


@router.command(('user_query', 'uq', 'qu'), 'запросы пользователя по ID', 'user_id')  # /user_query
@command_arguments.user_id
async def _(message: Message, user_id: int):
    await pages.user_query(message.from_user.id, user_id)


@router.command('master', 'назначить мастером', 'user_id')  # /master
@command_arguments.user_id
async def _(message: Message, user_id):
    with MastersTable() as masters_db:
        if masters_db.set_master_status(user_id):
            await message.answer(PHRASES_RU.replace('success.set_master', user_id=user_id))
        else:
            await message.answer(PHRASES_RU.error.db)


@router.command('del_master', 'удалить мастера', 'user_id')  # /del_master
@command_arguments.user_id
async def _(message: Message, user_id):
    with MastersTable() as masters_db:
        if masters_db.set_master_status(user_id, False):
            await message.answer(PHRASES_RU.replace('success.del_master', user_id=user_id))
        else:
            await message.answer(PHRASES_RU.error.db)


@router.command('test', 'отладка и тестирование функций')  # /test
async def _():
    pass
