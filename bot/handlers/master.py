import logging
from collections import defaultdict
from datetime import datetime, time
from typing import Optional

from aiogram import F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from DB import models
from DB.tables.appointments import AppointmentsTable
from DB.tables.day_schedule import DayScheduleTable
from DB.tables.masters import MastersTable
from DB.tables.users import UsersTable
from bot import pages
from bot.bot_utils import command_arguments
from bot.bot_utils.msg_sender import get_media_from_photos, send_or_edit_message
from bot.bot_utils.routers import MasterRouter, BaseRouter
from bot.keyboards import get_keyboard
from bot.states import MasterStates
from config import const, bot
from phrases import PHRASES_RU
from bot.keyboards.master import inline as inline_mkb
from utils import format_string

logger = logging.getLogger(__name__)


async def send_master_menu(user_id: int, message_id: Optional[int] = None):
    with AppointmentsTable() as db:
        text = PHRASES_RU.replace('answer.master.menu',
                                  clients=db.count_clients(),
                                  appointments=db.count_completed_slots())
        await send_or_edit_message(user_id, text, inline_mkb.menu_master_keyboard(), message_id)

router = MasterRouter()


@router.command(('commands', 'cmd'), 'список всех доступных команд')  # /commands /cmd
async def command_getcmds(message: Message):
    commands_text = PHRASES_RU.title.commands
    master_commands = '\n'.join(str(command) for command in BaseRouter.available_commands if command.is_master)
    if master_commands:
        commands_text += PHRASES_RU.subtitle.master_commands + master_commands
    user_commands = '\n'.join(str(command) for command in BaseRouter.available_commands if command.is_user)
    if user_commands:
        commands_text += PHRASES_RU.subtitle.user_commands + user_commands
    await message.answer(commands_text)


@router.command('ban', 'заблокировать пользователя по ID', 'user_id')  # /ban
@command_arguments.user_id
async def _(message: Message, user_id):
    if message.from_user.id == int(user_id):
        await message.answer(PHRASES_RU.error.ban_yourself)
        return
    with UsersTable() as user_db:
        if user_db.set_ban_status(user_id, message.from_user.id, True):
            await message.answer(PHRASES_RU.replace('success.banned', user_id=user_id))
        else:
            await message.answer(PHRASES_RU.error.db)


@router.command('unban', 'разблокировать пользователя по ID', 'user_id')  # /unban
@command_arguments.user_id
async def _(message: Message, user_id):
    with UsersTable() as user_db:
        if user_db.set_ban_status(user_id, message.from_user.id, False):
            await message.answer(PHRASES_RU.replace('success.unbanned', user_id=user_id))
        else:
            await message.answer(PHRASES_RU.error.db)


@router.message(StateFilter(MasterStates.WAITING_FOR_SLOT))
async def _(message: Message, state: FSMContext):
    if message.text:
        try:
            slots = format_string.parse_slots_text(message.text)
            if not slots:
                await message.answer(PHRASES_RU.error.master.slots_not_found)
                return

            slots_by_date = defaultdict(list)
            for (start, end) in slots:
                date_key = start.date()
                slots_by_date[date_key].append((start, end))

            sorted_dates = sorted(slots_by_date.keys())

            confirmation_text = "🔍 <b>Проверьте распознанные слоты:</b>\n\n"

            for date in sorted_dates:
                date_str = models.format_date(datetime.combine(date, time.min))
                confirmation_text += f"{date_str }\n"
                time_slots = sorted(slots_by_date[date], key=lambda x: x[0])

                for start, end in time_slots:
                    confirmation_text += PHRASES_RU.replace('template.master.slot_time_range', start=start.strftime('%H:%M'), end=end.strftime('%H:%M'))
                confirmation_text += "\n"

            await state.update_data(parsed_slots=slots)
            await message.answer(confirmation_text, reply_markup=inline_mkb.master_confirm_adding_slot())

        except Exception as e:
            await message.answer(PHRASES_RU.replace('error.master.slot_addition', error=str(e), slot_format=PHRASES_RU.answer.master.slot_format))
    else:
        await message.answer(PHRASES_RU.error.state.slot_not_text_type)


@router.message(StateFilter(MasterStates.WAITING_FOR_SCHEDULE))
async def _(message: Message, state: FSMContext):
    if message.text:
        try:
            schedule_data = format_string.parse_schedule_message(message.text)
            with DayScheduleTable() as db:
                for weekday, time_slots in schedule_data.items():
                    # Конвертируем time обратно в строки для хранения
                    time_strings = [(str(start), str(end)) for start, end in time_slots]
                    is_working = bool(time_slots)
                    db.set_day_schedule(weekday, time_strings, is_working)

            schedule_message = "✅ Расписание обновлено!\n\n"

            schedule_message += format_string.show_current_schedule()
            await message.answer(text=schedule_message)
            await state.clear()

        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}\n\nПример формата:\nпн - 10:00 14:00 18:00\nвт - 11:00 19:00\nср - выходной")
    else:
        await message.answer(PHRASES_RU.error.state.schedule_not_text_type)


@router.message(StateFilter(MasterStates.WAITING_FOR_NEW_SERVICE))
async def _(message: Message, state: FSMContext):
    if message.text:
        try:

            service = format_string.parse_service_text(message.text)

            response = PHRASES_RU.replace('answer.master.service_addition', service=format_string.service_text(service))

            await state.update_data(parsed_service=service)
            await message.answer(response, reply_markup=inline_mkb.master_confirm_adding_service())

        except Exception as e:
            await message.answer(PHRASES_RU.replace('error.master.service_addition', error=str(e), service_format=PHRASES_RU.answer.master.service_format))
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
            service = format_string.parse_service_text(message.text, service_id)

            response = PHRASES_RU.replace('answer.master.service_update', service=format_string.service_text(service))
            service.id = service_id
            await state.update_data(parsed_service=service)
            await message.answer(response, reply_markup=inline_mkb.master_confirm_edit_service(service_id))

        except Exception as e:
            await message.answer(PHRASES_RU.replace('error.master.service_update', error=str(e), service_format=PHRASES_RU.answer.master.service_format))
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


@router.message(F.text == PHRASES_RU.button.master.pending_apps)
async def _(message: Message):
    with (MastersTable() as master_db, AppointmentsTable() as app_db):
        master = master_db.get_master(message.from_user.id)
        if not master or not master.is_master:
            await message.answer(PHRASES_RU.error.no_rights, reply_markup=get_keyboard(message.from_user.id))
            return
        if master.current_app_id:
            if master.message_id:
                try:
                    await bot.delete_message(chat_id=message.chat.id, message_id=master.message_id)
                except Exception as e:
                    logger.warning("Couldn't delete message %d: %s", master.message_id, e)
            if master.msg_to_delete:
                try:
                    msgs = list(map(int, master.msg_to_delete.split(',')))
                    msgs_list = [i for i in range(msgs[0], msgs[-1] + 1)]
                    await bot.delete_messages(chat_id=message.chat.id, message_ids=msgs_list)
                except Exception as e:
                    logger.warning("Couldn't delete message %s: %s", master.msg_to_delete, e)
            master_db.update_current_state(message.from_user.id)
        total_items = app_db.count_appointments(const.PENDING)
        if total_items == 0:
            await message.answer(PHRASES_RU.answer.master.no_pending_apps)
            return
        if next_app := app_db.get_nth_pending_appointment(0):
            await pages.update_master_booking_ui(next_app)
