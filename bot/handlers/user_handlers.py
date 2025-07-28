from typing import Dict, List

from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram import Router, F
import datetime

from DB.models import PhotoModel
from DB.tables.users import UsersTable
from bot.keyboards import user_keyboards
from bot.keyboards import inline_keyboards as ikb
from bot.navigation import AppointmentNavigation
from bot.states import AppointmentStates

from config import config, bot
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
    await message.answer(PHRASES_RU.answer.choose_date, reply_markup=ikb.month_keyboard(current_month, current_year, False))


@router.message(StateFilter(AppointmentStates.WAITING_FOR_PHOTOS))
async def _(message: Message, state: FSMContext):
    if message.photo:
        photo = message.photo[-1]
        new_photo = PhotoModel(
            telegram_file_id=photo.file_id,
            file_unique_id=photo.file_unique_id,
            caption=message.caption
        )

        data = await AppointmentNavigation.get_appointment_data(state)
        updated_photos = (data.photos or []) + [new_photo]

        await AppointmentNavigation.update_appointment_data(
            state,
            photos=updated_photos
        )


@router.message(StateFilter(AppointmentStates.WAITING_FOR_COMMENT))
async def _(message: Message, state: FSMContext):
    if message.text:
        data = await AppointmentNavigation.update_appointment_data(
            state,
            text=message.text
        )

        if data.message_id:
            await bot.send_message(
                chat_id=message.from_user.id,
                text=f'<i>{message.text}</i>\n\nбудет учтено',
                reply_to_message_id=data.message_id
            )


@router.message(StateFilter(AppointmentStates.WAITING_FOR_CONTACT))
async def process_contact(message: Message, state: FSMContext):
    with UsersTable() as db:
        db.update_contact(message.from_user.id, message.text)

    await state.clear()
    await message.answer(PHRASES_RU.answer.contact_saved)


@router.message()
async def _(message: Message):
    await message.answer(text=PHRASES_RU.answer.unknown, reply_markup=user_keyboards.keyboard)
