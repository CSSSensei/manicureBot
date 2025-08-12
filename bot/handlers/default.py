from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram import Router, F, types

from DB.models import PhotoModel
from DB.tables.users import UsersTable
from bot import pages
from bot.keyboards import get_keyboard
from bot.keyboards.default import inline as ikb, base as ukb
from bot.navigation import AppointmentNavigation
from bot.states import AppointmentStates, UserStates

from config import config, bot
from phrases import PHRASES_RU
from utils import format_string
from bot.handlers.admin import command_getcmds

router = Router()


@router.message(F.text == config.tg_bot.password)
async def _(message: Message):
    with UsersTable() as users_db:
        if users_db.set_admin(message.from_user.id, message.from_user.id):
            await message.delete()
            await message.answer(PHRASES_RU.success.promoted, reply_markup=get_keyboard(message.from_user.id))
            await command_getcmds(message)
        else:
            await message.answer(PHRASES_RU.error.db, reply_markup=get_keyboard(message.from_user.id))


@router.message(F.text == PHRASES_RU.button.booking)
async def booking_message(message: Message, state: FSMContext):
    text, reply_markup = ikb.first_page_calendar()
    if text and reply_markup:
        await message.answer(text=text, reply_markup=reply_markup)
        await state.set_state(AppointmentStates.WAITING_FOR_DATE)
    else:
        await message.answer(PHRASES_RU.error.no_slots)


@router.message(F.text == PHRASES_RU.button.active_booking)
async def active_booking_message(message: Message):
    await pages.get_active_bookings(message.from_user.id, page=1)


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
            await message.reply(PHRASES_RU.error.photo_limit, reply=False)
            return
        updated_photos = (data.photos or []) + [new_photo]
        data.photos = updated_photos
        await AppointmentNavigation.update_appointment_data(
            state,
            photos=updated_photos
        )
        await message.reply(PHRASES_RU.answer.photo_attached, reply=False)
        await bot.edit_message_text(chat_id=message.from_user.id,
                                    message_id=data.message_id,
                                    text=format_string.user_booking_text(data) + PHRASES_RU.answer.send_photo,
                                    reply_markup=ikb.photo_keyboard())


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
                text=PHRASES_RU.answer.comment_attached,
                reply_to_message_id=data.message_id
            )
        data.comment = message.text
        await bot.edit_message_text(chat_id=message.from_user.id,
                                    message_id=data.message_id,
                                    text=format_string.user_booking_text(data) + PHRASES_RU.answer.send_comment,
                                    reply_markup=ikb.comment_keyboard())


@router.message(F.content_type == types.ContentType.CONTACT)
async def _(message: Message, state: FSMContext):
    with UsersTable() as db:
        db.update_contact(message.from_user.id, message.contact.phone_number)

    await state.clear()
    await message.answer(PHRASES_RU.answer.contact_saved, reply_markup=get_keyboard(message.from_user.id))


@router.message(StateFilter(UserStates.WAITING_FOR_CONTACT))
async def _(message: Message):
    await message.answer(PHRASES_RU.replace('answer.send_contact', button=PHRASES_RU.button.send_contact),
                         reply_markup=ukb.contact_keyboard)


@router.message()
async def _(message: Message):
    await message.answer(text=PHRASES_RU.answer.unknown, reply_markup=get_keyboard(message.from_user.id))
