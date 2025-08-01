from datetime import datetime
from typing import Optional

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from DB.tables.appointments import AppointmentsTable
from bot.bot_utils.filters import MasterFilter
from bot.bot_utils.msg_sender import get_media_from_photos, send_or_edit_message
from bot.keyboards import get_keyboard
from bot.states import MasterStates
from phrases import PHRASES_RU
from bot.keyboards.master import inline as inline_mkb
from utils import format_string
from config import bot


async def send_master_menu(user_id: int, message_id: Optional[int] = None):
    await send_or_edit_message(bot, user_id, 'menu', inline_mkb.menu_master_keyboard(), message_id)

router = Router()
router.message.filter(MasterFilter())


@router.message(StateFilter(MasterStates.WAITING_FOR_SLOT))
async def _(message: Message, state: FSMContext):
    if message.text:
        try:
            slots = format_string.parse_slots_text(message.text)
            confirmation_text = "🔍 *Проверьте распарсенные слоты:*\n\n"
            for i, (start, end) in enumerate(slots, 1):
                confirmation_text += (
                    f"{i}. *{start.strftime('%d.%m.%Y')}* "
                    f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}\n"
                )

            await state.update_data(parsed_slots=slots)

            await message.answer(
                confirmation_text,
                parse_mode="Markdown",
                reply_markup=inline_mkb.master_confirm_slot()
            )

        except Exception as e:
            error_msg = (
                "❌ *Ошибка при обработке запроса:*\n"
                f"`{str(e)}`\n\n"
                "*Правильный формат:*\n"
                "```\nсентябрь\n"
                "1 - 14:30-16:30 17:30-19:30\n"
                "2 - 10:00 15:00\n```\n"
                "• Первая строка - месяц\n"
                "• Число - времена через пробел\n"
                "• Одно время = слот на 3 часа"
            )
            await message.answer(error_msg, parse_mode="Markdown")
    else:
        await message.answer(PHRASES_RU.error.state.not_text_type)


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
    await send_master_menu(message.from_user.id)

