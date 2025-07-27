from typing import Dict, List

from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram import Router, F
import datetime

from DB.models import PhotoModel
from DB.tables.users import UsersTable
from bot.keyboards import user_keyboards
from bot.keyboards.inline_keyboards import month_keyboard, photo_keyboard
from bot.states import AppointmentStates

from config import config
from phrases import PHRASES_RU

router = Router()


@router.message(F.text == config.tg_bot.password)
async def _(message: Message):
    with UsersTable() as users_db:
        if users_db.set_admin(message.from_user.id, message.from_user.id):
            await message.answer(PHRASES_RU.success.promoted, reply_markup=user_keyboards.keyboard)
        else:
            await message.answer(PHRASES_RU.error.db, reply_markup=user_keyboards.keyboard)


@router.message(F.text == PHRASES_RU.button.booking)
async def booking_message(message: Message, state: FSMContext):
    current_date = datetime.datetime.now()
    current_month = current_date.month
    current_year = current_date.year
    await state.set_state(AppointmentStates.WAITING_FOR_DATE)
    await message.answer(PHRASES_RU.answer.choose_date, reply_markup=month_keyboard(current_month, current_year, False))


@router.message(StateFilter(AppointmentStates.WAITING_FOR_PHOTOS))
async def _(message: Message, state: FSMContext):
    if message.photo:
        data: Dict = await state.get_data()
        photos: List = data.get('photos')
        photos = photos if photos else []
        photo = message.photo[-1]
        photos.append(PhotoModel(telegram_file_id=photo.file_id, file_unique_id=photo.file_unique_id, caption=message.caption))
        await state.update_data({'photos': photos})


@router.message(StateFilter(AppointmentStates.WAITING_FOR_COMMENT))
async def _(message: Message, state: FSMContext):
    if message.text:
        reply_to_message_id = (await state.get_data()).get('message_id')
        from config import bot
        await bot.send_message(chat_id=message.from_user.id, text=f'<i>{message.text}</i>\n\nбудет учтено', reply_to_message_id=reply_to_message_id)
        await state.update_data({'text': message.text})


@router.message()
async def _(message: Message):
    await message.answer(text=PHRASES_RU.answer.unknown, reply_markup=user_keyboards.keyboard)
