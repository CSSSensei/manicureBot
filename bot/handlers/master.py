from aiogram import Router, F
from aiogram.types import Message

from bot.utils.filters import MasterFilter
from bot.keyboards import get_keyboard
from phrases import PHRASES_RU
from bot.keyboards.master import inline as inline_mkb

router = Router()
router.message.filter(MasterFilter())


@router.message(F.text == PHRASES_RU.button.master.clients_today)
async def _(message: Message):
    await message.answer(text='клиенты на сегодня', reply_markup=get_keyboard(message.from_user.id))


@router.message(F.text == PHRASES_RU.button.master.menu)
async def _(message: Message):
    await message.answer(text='menu', reply_markup=inline_mkb.menu_master_keyboard())

