from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message

from DB.tables.appointments import AppointmentsTable
from bot.bot_utils.filters import MasterFilter
from bot.bot_utils.msg_sender import get_media_from_photos
from bot.keyboards import get_keyboard
from phrases import PHRASES_RU
from bot.keyboards.master import inline as inline_mkb
from utils import format_string

router = Router()
router.message.filter(MasterFilter())


@router.message(F.text == PHRASES_RU.button.master.clients_today)
async def _(message: Message):
    with AppointmentsTable() as app_db:
        apps = app_db.get_appointments_by_status_and_date(datetime.now())
        if apps:
            for app in apps:
                caption = format_string.master_sent_booking(app, PHRASES_RU.replace('title.booking', date=app.formatted_date))
                if app.photos:
                    await message.answer_media_group(media=get_media_from_photos(app.photos, caption=caption))
                else:
                    await message.answer(text=caption)
        else:
            await message.answer(text=PHRASES_RU.answer.no_apps_today, reply_markup=get_keyboard(message.from_user.id))


@router.message(F.text == PHRASES_RU.button.master.menu)
async def _(message: Message):
    await message.answer(text='menu', reply_markup=inline_mkb.menu_master_keyboard())

