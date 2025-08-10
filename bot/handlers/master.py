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


async def send_master_menu(user_id: int, message_id: Optional[int] = None):
    await send_or_edit_message(user_id, PHRASES_RU.answer.master.menu, inline_mkb.menu_master_keyboard(), message_id)

router = Router()
router.message.filter(MasterFilter())


@router.message(StateFilter(MasterStates.WAITING_FOR_SLOT))
async def _(message: Message, state: FSMContext):
    if message.text:
        try:
            slots = format_string.parse_slots_text(message.text)
            if not slots:
                await message.answer('❌ <b>Ошибка при обработке запроса: время слотов не было найдено</b>')
                return
            confirmation_text = "🔍 *Проверьте распознанные слоты:*\n\n"
            for i, (start, end) in enumerate(slots, 1):
                confirmation_text += (
                    f"{i}. *{start.strftime('%d.%m.%Y')}* "
                    f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}\n"
                )

            await state.update_data(parsed_slots=slots)

            await message.answer(
                confirmation_text,
                parse_mode="Markdown",
                reply_markup=inline_mkb.master_confirm_adding_slot()
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
        await message.answer(PHRASES_RU.error.state.slot_not_text_type)


@router.message(StateFilter(MasterStates.WAITING_FOR_NEW_SERVICE))
async def _(message: Message, state: FSMContext):
    if message.text:
        try:

            service = format_string.parse_service_text(message.text)

            response = f"Подтвердите добавление услуги\n\n"          # TODO
            response += f"▪ Название: <i>{service.name}</i>\n"
            if service.description:
                response += f"▪ Описание: <i>{service.description}</i>\n"
            if service.price:
                response += f"▪ Стоимость: <i>{service.price} руб.</i>\n"
            if service.duration:
                response += f"▪ Длительность: <i>{service.duration} мин.</i>"

            await state.update_data(parsed_service=service)
            await message.answer(response, reply_markup=inline_mkb.master_confirm_adding_service())

        except Exception as e:
            error_msg = (                                            # TODO
                "❌ Ошибка при добавлении услуги:\n"
                f"{str(e)}\n\n"
                "Формат ввода:\n"
                "<code>Название услуги\n"
                "о: описание (не обязательно)\n"
                "с: стоимость (не обязательно)\n"
                "д: длительность в минутах (не обязательно)</code>\n\n"
                "Пример:\n"
                "<code>Маникюр\n"
                "о: Классический маникюр\n"
                "с: 1500\n"
                "д: 60</code>"
            )
            await message.answer(error_msg)
    else:
        await message.answer(PHRASES_RU.error.state.service_not_text_type)


@router.message(StateFilter(MasterStates.WAITING_FOR_EDIT_SERVICE))
async def _(message: Message, state: FSMContext):
    data = await state.get_data()
    service_id = data.get('service_id')
    if not service_id:
        await message.answer(PHRASES_RU.error.booking.try_again)
        await state.clear()
        return
    if message.text:
        try:
            service = format_string.parse_service_text(message.text)

            response = f"Подтвердите обновление услуги\n\n"          # TODO
            response += f"▪ Название: <i>{service.name}</i>\n"
            if service.description:
                response += f"▪ Описание: <i>{service.description}</i>\n"
            if service.price:
                response += f"▪ Стоимость: <i>{service.price} руб.</i>\n"
            if service.duration:
                response += f"▪ Длительность: <i>{service.duration} мин.</i>"
            service.id = service_id
            await state.update_data(parsed_service=service)
            await message.answer(response, reply_markup=inline_mkb.master_confirm_edit_service(service_id))

        except Exception as e:
            error_msg = (                                            # TODO
                "❌ Ошибка при обновлении услуги:\n"   # TODO подзаголовок отличается
                f"{str(e)}\n\n"
                "Формат ввода:\n"
                "<code>Название услуги\n"
                "о: описание (не обязательно)\n"
                "с: стоимость (не обязательно)\n"
                "д: длительность в минутах (не обязательно)</code>\n\n"
                "Пример:\n"
                "<code>Маникюр\n"
                "о: Классический маникюр\n"
                "с: 1500\n"
                "д: 60</code>"
            )
            await message.answer(error_msg)
    else:
        await message.answer(PHRASES_RU.error.state.service_not_text_type)


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
