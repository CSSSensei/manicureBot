from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.keyboards import base
from bot.routers import UserRouter, BaseRouter
from bot.states import AppointmentStates
from config import Config, load_config
from phrases import PHRASES_RU

router = UserRouter()
config: Config = load_config()


@router.command('start', 'запустить бота')  # /start
async def _(message: Message):
    await message.answer(PHRASES_RU.commands.start, reply_markup=base.keyboard)


@router.command('help', 'как пользоваться ботом')  # /help
async def _(message: Message):
    await message.answer(PHRASES_RU.commands.help, reply_markup=base.keyboard)


@router.command('about', 'о разработчиках')  # /about
async def _(message: Message):
    await message.answer(PHRASES_RU.commands.about, disable_web_page_preview=True, reply_markup=base.keyboard)


@router.command(('commands', 'cmd'), 'список всех команд (это сообщение)')  # /commands
async def _(message: Message):
    commands_text = '\n'.join(str(command) for command in BaseRouter.available_commands if not command.is_admin)
    await message.answer(PHRASES_RU.title.commands + commands_text, reply_markup=base.keyboard)


@router.command('add_contact', 'добавление контактной информации')          # /add_contact
async def add_contact(message: Message, state: FSMContext):
    await message.answer("Введите номер телефона или любую контактную информацию")
    await state.set_state(AppointmentStates.WAITING_FOR_CONTACT)
