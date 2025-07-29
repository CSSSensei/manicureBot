from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram import Router, F

from DB.models import PhotoModel
from DB.tables.slots import SlotsTable
from DB.tables.users import UsersTable
from bot.keyboards import base as ukb
from bot.keyboards import inline as ikb
from bot.navigation import AppointmentNavigation
from bot.states import AppointmentStates

from config import config, bot
from phrases import PHRASES_RU
from utils import format_string
from bot.handlers.admin_handlers import command_getcmds

router = Router()


@router.message(F.text == config.tg_bot.password)
async def _(message: Message):
    with UsersTable() as users_db:
        if users_db.set_admin(message.from_user.id, message.from_user.id):
            await message.delete()
            await message.answer(PHRASES_RU.success.promoted, reply_markup=ukb.keyboard)
            await command_getcmds(message)
        else:
            await message.answer(PHRASES_RU.error.db, reply_markup=ukb.keyboard)


@router.message(F.text == PHRASES_RU.button.booking)
async def booking_message(message: Message, state: FSMContext):
    await state.set_state(AppointmentStates.WAITING_FOR_DATE)
    with SlotsTable() as slots_db:
        first_slot = slots_db.get_first_available_slot()
        if first_slot:
            await message.answer(PHRASES_RU.answer.choose_date, reply_markup=ikb.month_keyboard(first_slot.month, first_slot.year, False))
        else:
            await message.answer(PHRASES_RU.error.no_slots)


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
        if data.photos and len(data.photos) >= 9:
            await message.reply("🚨 Нельзя прикрепить больше 9 фото!", reply=False)  # TODO убрать во phrases
            return
        updated_photos = (data.photos or []) + [new_photo]
        data.photos = updated_photos
        await AppointmentNavigation.update_appointment_data(
            state,
            photos=updated_photos
        )
        await message.reply("✅ Фото прикреплено!", reply=False)  # TODO убрать во phrases
        await bot.edit_message_text(chat_id=message.from_user.id, message_id=data.message_id, text=format_string.user_booking_text(data) + PHRASES_RU.answer.send_photo, reply_markup=ikb.photo_keyboard())


@router.message(StateFilter(AppointmentStates.WAITING_FOR_COMMENT))
async def _(message: Message, state: FSMContext):
    if message.text:
        data = await AppointmentNavigation.update_appointment_data(
            state,
            comment=message.text
        )

        if data.message_id:
            await bot.send_message(
                chat_id=message.from_user.id,
                text=f'<i>{message.text}</i>\n\nбудет учтено',  # TODO убрать во phrases
                reply_to_message_id=data.message_id
            )
        data.comment = message.text
        await bot.edit_message_text(chat_id=message.from_user.id, message_id=data.message_id, text=format_string.user_booking_text(data) + PHRASES_RU.answer.send_comment, reply_markup=ikb.comment_keyboard())


@router.message(StateFilter(AppointmentStates.WAITING_FOR_CONTACT))
async def process_contact(message: Message, state: FSMContext):
    with UsersTable() as db:
        db.update_contact(message.from_user.id, message.text)

    await state.clear()
    await message.answer(PHRASES_RU.answer.contact_saved)


@router.message()
async def _(message: Message):
    await message.answer(text=PHRASES_RU.answer.unknown, reply_markup=ukb.keyboard)
