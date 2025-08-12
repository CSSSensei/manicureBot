from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.keyboards import get_keyboard
from bot.bot_utils.routers import UserRouter, BaseRouter
from phrases import PHRASES_RU

router = UserRouter()


@router.command('start', 'запустить бота')  # /start
async def _(message: Message):
    await message.answer(PHRASES_RU.replace('commands.start', booking=PHRASES_RU.button.booking),
                         reply_markup=get_keyboard(message.from_user.id))


@router.command('help', 'как пользоваться ботом')  # /help
async def _(message: Message):
    await message.answer(PHRASES_RU.replace('commands.help', booking=PHRASES_RU.button.booking), reply_markup=get_keyboard(message.from_user.id))


@router.command('about', 'о разработчиках')  # /about
async def _(message: Message):
    await message.answer(PHRASES_RU.commands.about, disable_web_page_preview=True, reply_markup=get_keyboard(message.from_user.id))


@router.command(('commands', 'cmd'), 'список всех команд (это сообщение)')  # /commands
async def _(message: Message):
    commands_text = '\n'.join(str(command) for command in BaseRouter.available_commands if not command.is_admin)
    await message.answer(PHRASES_RU.title.commands + commands_text, reply_markup=get_keyboard(message.from_user.id))


@router.command('cancel', 'выход из текущего состояния')   # /cancel
async def _(message: Message, state: FSMContext):
    await message.answer("Вы вышли из текущего состояния")
    await state.clear()
