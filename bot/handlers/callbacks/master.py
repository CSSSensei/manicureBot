from datetime import date, datetime, time

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot import pages, scheduler
from bot.bot_utils import msg_sender
from bot.bot_utils.filters import MasterFilter, NotBookingCalendar
from bot.bot_utils.models import (
    AddSlotsMonthCallBack,
    DeleteSlotCallBack,
    EditServiceCallBack,
    MasterButtonCallBack,
    MasterServiceCallBack,
    MonthCallBack,
    ScheduleServiceCallBack,
)
from bot.handlers.master import send_master_menu
from bot.keyboards.default import inline as ikb
from bot.keyboards.master import inline as inline_mkb
from bot.navigation import AppointmentNavigation
from bot.scheduler import SlotNotifierBot
from bot.states import MasterStates
from config import const
from config.const import CalendarMode
from DB import models
from DB.models import format_date
from DB.tables.appointments import AppointmentsTable
from DB.tables.masters import MastersTable
from DB.tables.service_schedule import ServiceScheduleTable
from DB.tables.services import ServicesTable
from DB.tables.slots import SlotsTable
from phrases import PHRASES_RU
from utils import db_manager, format_string
from utils.slot_generator import SlotGenerator

router = Router()


@router.callback_query(MonthCallBack.filter(), NotBookingCalendar())
async def handle_slot_choosing(callback: CallbackQuery, callback_data: MonthCallBack, state: FSMContext):
    if callback_data.action != 0:
        # Обработка переключения месяцев
        month = callback_data.month + callback_data.action
        year = callback_data.year
        year += month // 12 if month > 12 else -1 if month < 1 else 0
        mode = callback_data.mode
        month = 1 if month > 12 else 12 if month < 1 else month

        prev_enabled = (
            not (month == datetime.now().month and year == datetime.now().year)
            if mode != CalendarMode.APPOINTMENT_MAP
            else True
        )
        app = await AppointmentNavigation.get_appointment_data(state)
        if mode == CalendarMode.BOOKING and (not app or not app.service):
            await callback.message.edit_text(PHRASES_RU.error.booking.try_again)
            return
        text, reply_markup = ikb.create_calendar_keyboard(month, year, prev_enabled, mode, app)
        await callback.message.edit_text(text=text, reply_markup=reply_markup)
        return
    mode = callback_data.mode
    if callback_data.day <= 0:
        no_info_for_this_day = PHRASES_RU.error.no_slots_for_this_day
        if mode == CalendarMode.APPOINTMENT_MAP:
            no_info_for_this_day = PHRASES_RU.error.no_apps_for_this_day
        await callback.answer(PHRASES_RU.error.date if callback_data.day == 0 else no_info_for_this_day)
        return

    selected_date = date(callback_data.year, callback_data.month, callback_data.day)
    match mode:
        case CalendarMode.DELETE:
            await callback.message.edit_text(
                text=PHRASES_RU.replace(
                    'answer.master.choose_slot_to_delete',
                    date=models.format_date(datetime.combine(selected_date, time.min)),
                ),
                reply_markup=inline_mkb.delete_slots_menu(selected_date),
            )
        case CalendarMode.APPOINTMENT_MAP:
            await pages.get_master_apps(callback.bot, callback, selected_date, 1)


@router.callback_query(DeleteSlotCallBack.filter(), MasterFilter())
async def handle_slot_deletion(callback: CallbackQuery, callback_data: DeleteSlotCallBack):
    action = callback_data.action
    slot_date = callback_data.slot_date
    formatted_date = format_date(datetime.combine(slot_date, time.min))

    def is_current_month(date_to_check):
        current_date = datetime.now()
        return date_to_check.month == current_date.month and date_to_check.year == current_date.year

    # Отображение календаря
    async def show_calendar(target_date=None):
        target_date = target_date or slot_date
        prev_enabled = not is_current_month(target_date)
        text, reply_markup = ikb.create_calendar_keyboard(
            target_date.month, target_date.year, prev_enabled, CalendarMode.DELETE
        )
        await callback.message.edit_text(text=text, reply_markup=reply_markup)

    match action:
        case const.Action.slot_calendar:  # BACK
            await show_calendar()

        case const.Action.check_slot_to_delete:
            slot_id = callback_data.slot_id

            with SlotsTable() as db:
                if not slot_id:  # Удалить все слоты за день
                    await callback.message.edit_text(
                        text=PHRASES_RU.replace('answer.master.delete_all_slots', date=formatted_date),
                        reply_markup=inline_mkb.slot_deletion(None, slot_date),
                    )

                else:
                    # Показать информацию о конкретном слоте
                    slot = db.get_slot(slot_id)
                    await callback.message.edit_text(
                        text=PHRASES_RU.replace('answer.master.slot_info', date=formatted_date, slot_str=str(slot)),
                        reply_markup=inline_mkb.slot_deletion(slot, slot_date),
                    )

        case const.Action.delete_slot:
            slot_id = callback_data.slot_id
            with SlotsTable() as db:
                if not slot_id:
                    # Удаление всех слотов за день
                    slots = db.get_available_slots_by_day(slot_date)
                    for slot in slots:
                        db.delete_slot(slot.id)
                    await SlotNotifierBot(callback.bot).update_channel_slots()
                    await callback.answer(PHRASES_RU.replace('callback.answer.delete_slots', date=formatted_date))
                    await show_calendar()
                    return
                success, message = db.delete_slot(slot_id)
                await SlotNotifierBot(callback.bot).update_channel_slots()
                await callback.answer(message)

            # Проверить, остались ли еще слоты на этот день
            with SlotsTable() as db:
                remaining_slots = db.get_available_slots_by_day(slot_date)

            if remaining_slots:
                # Есть еще слоты - показать меню удаления
                await callback.message.edit_text(
                    text=PHRASES_RU.replace('answer.master.choose_slot_to_delete', date=formatted_date),
                    reply_markup=inline_mkb.delete_slots_menu(slot_date),
                )
            else:
                # Слотов не осталось - вернуться к календарю
                await show_calendar()


@router.callback_query(MasterButtonCallBack.filter(), MasterFilter())
async def handle_navigation_actions(callback: CallbackQuery, callback_data: MasterButtonCallBack):
    status_to_set = callback_data.status

    with AppointmentsTable() as app_db, MastersTable() as master_db:
        if status_to_set not in app_db.valid_statuses:
            return
        app = app_db.get_appointment_by_id(callback_data.appointment_id)
        if not app:
            await callback.answer(PHRASES_RU.error.app_not_found)
            return

        match (app.status, status_to_set):
            case (const.CANCELLED, _):
                await callback.answer(PHRASES_RU.answer.status.already_cancelled)
                await callback.message.delete()

                if callback_data.msg_to_delete:
                    msgs = list(map(int, callback_data.msg_to_delete.split(',')))
                    msgs_list = list(range(msgs[0], msgs[-1] + 1))
                    await callback.bot.delete_messages(chat_id=callback.from_user.id, message_ids=msgs_list)
            case (_, const.REJECTED):
                success = AppointmentsTable.cancel_appointment(app, const.REJECTED)
                if success:
                    await SlotNotifierBot(callback.bot).update_channel_slots()
                    app.status = const.REJECTED
                    await msg_sender.notify_client(callback.bot, app)
                    await callback.message.edit_text(text=format_string.master_reviewed_appointment(app))
                else:
                    await callback.message.edit_text(text=PHRASES_RU.error.booking.try_again)
            case (_, const.CONFIRMED):
                app_db.update_appointment_status(app.appointment_id, const.CONFIRMED)
                app.status = const.CONFIRMED
                await msg_sender.notify_client(callback.bot, app)
                if app.appointment_id is not None and app.slot is not None:
                    scheduler.schedule_reminders(app.appointment_id, app.slot.start_time, callback.bot)
                await callback.message.edit_text(text=format_string.master_reviewed_appointment(app))

        master_db.update_current_state(callback.from_user.id)

        if next_app := app_db.get_nth_pending_appointment(0):
            await pages.update_master_booking_ui(callback.bot, next_app)


@router.callback_query(AddSlotsMonthCallBack.filter(), MasterFilter())
async def handle_month_generation(callback: CallbackQuery, callback_data: AddSlotsMonthCallBack):
    action = callback_data.action
    month = callback_data.month
    year = callback_data.year

    slots = SlotGenerator().generate_slots_for_month(month, year)
    slots_text = format_string.slots_to_text(slots)
    match action:
        case 'check':
            text = f'Проверьте, что слоты сгенерированы верно\n\n<code>{slots_text}</code>'
            await callback.message.edit_text(text=text, reply_markup=inline_mkb.master_confirm_adding_slot(month, year))
        case 'add':
            text = await db_manager.add_slots_from_list(callback.bot, [(sl.start_time, sl.end_time) for sl in slots])
            text_chunks = format_string.split_text(text, 4096)
            for i in range(len(text_chunks)):
                if i == 0:
                    await callback.message.edit_text(text_chunks[i])
                else:
                    await callback.bot.send_message(chat_id=callback.from_user.id, text=text_chunks[i])


@router.callback_query(MasterServiceCallBack.filter(), MasterFilter())
async def handle_service_edit(callback: CallbackQuery, callback_data: MasterServiceCallBack, state: FSMContext):
    await state.clear()
    service_id = callback_data.service_id
    action = callback_data.action
    with ServicesTable() as db:
        service = db.get_service(service_id)
        service_text = format_string.service_text(service)
        text = PHRASES_RU.replace('answer.master.service_edit', service=service_text)
        if action:
            match action:
                case const.Action.set_active:
                    db.toggle_service_active(service_id, True)
                    service.is_active = True
                case const.Action.set_inactive:
                    db.toggle_service_active(service_id, False)
                    service.is_active = False
                case const.Action.service_update:
                    text = PHRASES_RU.replace('answer.master.service_update_successfully', service=service_text)

        await callback.message.edit_text(text=text, reply_markup=inline_mkb.edit_current_service(service))


@router.callback_query(EditServiceCallBack.filter(), MasterFilter())
async def _(callback: CallbackQuery, callback_data: EditServiceCallBack, state: FSMContext):
    service_id = callback_data.service_id
    await state.update_data(service_id=service_id)
    await state.set_state(MasterStates.WAITING_FOR_EDIT_SERVICE)
    await callback.message.edit_text(
        text=PHRASES_RU.answer.master.add_service, reply_markup=inline_mkb.back_to_edit_service(service_id)
    )


@router.callback_query(ScheduleServiceCallBack.filter(), MasterFilter())
async def _(callback: CallbackQuery, callback_data: ScheduleServiceCallBack, state: FSMContext):
    service_id = callback_data.service_id
    weekday = callback_data.weekday
    action = callback_data.action
    with ServiceScheduleTable() as db:
        match action:
            case const.Action.set_active:
                db.set_service_availability(service_id, weekday, True)
            case const.Action.set_inactive:
                db.set_service_availability(service_id, weekday, False)

    await handle_service_edit(callback, MasterServiceCallBack(service_id=service_id), state)


@router.callback_query(
    StateFilter(MasterStates.WAITING_FOR_SLOT),
    F.data == PHRASES_RU.callback_data.master.confirm_add_slot,
    MasterFilter(),
)
async def _(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    slots = data.get('parsed_slots', [])

    if not slots:
        await callback.message.edit_text(PHRASES_RU.error.slots_not_found)
        return
    result_text = await db_manager.add_slots_from_list(callback.bot, slots)
    text_chunks = format_string.split_text(result_text, 4096)
    await state.clear()
    for i in range(len(text_chunks)):
        if i == 0:
            await callback.message.edit_text(text_chunks[i])
        else:
            await callback.bot.send_message(chat_id=callback.from_user.id, text=text_chunks[i])


@router.callback_query(F.data == PHRASES_RU.callback_data.master.confirm_add_slot, MasterFilter())
async def _(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(PHRASES_RU.error.booking.try_again)
    await state.clear()


@router.callback_query(
    StateFilter(MasterStates.WAITING_FOR_EDIT_SERVICE),
    F.data == PHRASES_RU.callback_data.master.confirm_edit_service,
    MasterFilter(),
)
async def _(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    service = data.get('parsed_service')

    if not service:
        await callback.message.edit_text(PHRASES_RU.error.booking.try_again)
        return
    with ServicesTable() as db:
        db.update_service(service)

    await handle_service_edit(
        callback, MasterServiceCallBack(service_id=service.id, action=const.Action.service_update), state
    )


@router.callback_query(F.data == PHRASES_RU.callback_data.master.confirm_edit_service, MasterFilter())
async def _(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(PHRASES_RU.error.booking.try_again)
    await state.clear()


@router.callback_query(
    StateFilter(MasterStates.WAITING_FOR_NEW_SERVICE),
    F.data == PHRASES_RU.callback_data.master.confirm_add_service,
    MasterFilter(),
)
async def _(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    service = data.get('parsed_service')

    if not service:
        await callback.message.edit_text(PHRASES_RU.error.booking.try_again)
        return
    with ServicesTable() as db:
        db.add_service(service)
    response = PHRASES_RU.replace(
        'answer.master.service_added_successfully', service=format_string.service_text(service)
    )
    await callback.message.edit_text(response, reply_markup=inline_mkb.back_to_service_menu())
    await state.clear()


@router.callback_query(F.data == PHRASES_RU.callback_data.master.confirm_add_service, MasterFilter())
async def _(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(PHRASES_RU.error.booking.try_again)


@router.callback_query(F.data == PHRASES_RU.callback_data.master.back_to_adding_slots, MasterFilter())
async def _(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await add_menu(callback)


@router.callback_query(F.data == PHRASES_RU.callback_data.master.clients, MasterFilter())
async def _(callback: CallbackQuery):
    await pages.get_clients(callback.bot, callback.from_user.id, callback.message.message_id)


@router.callback_query(F.data == PHRASES_RU.callback_data.master.appointment_map, MasterFilter())
async def _(callback: CallbackQuery):
    now = datetime.now()
    text, reply_markup = ikb.create_calendar_keyboard(now.month, now.year, True, CalendarMode.APPOINTMENT_MAP)
    await callback.message.edit_text(text=text, reply_markup=reply_markup)


@router.callback_query(F.data == PHRASES_RU.callback_data.master.add_manual_slots, MasterFilter())
async def _(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MasterStates.WAITING_FOR_SLOT)
    await callback.message.edit_text(
        text=PHRASES_RU.replace('answer.master.add_manual_slot', slot_format=PHRASES_RU.answer.master.slot_format),
        reply_markup=inline_mkb.back_to_adding(),
    )


@router.callback_query(F.data == PHRASES_RU.callback_data.master.edit_slot_generation_format, MasterFilter())
async def _(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MasterStates.WAITING_FOR_SCHEDULE)
    await callback.message.edit_text(
        text=PHRASES_RU.answer.master.send_slot_schedule, reply_markup=inline_mkb.back_to_adding()
    )


@router.callback_query(F.data == PHRASES_RU.callback_data.master.add_slots, MasterFilter())
async def add_menu(callback: CallbackQuery):
    schedule = format_string.show_current_schedule()
    await callback.message.edit_text(
        text=PHRASES_RU.replace('answer.master.add_slots_menu', schedule=schedule),
        reply_markup=inline_mkb.add_slots_menu(),
    )


@router.callback_query(F.data == PHRASES_RU.callback_data.master.delete_slots, MasterFilter())
async def delete_slots_calendar_handler(callback: CallbackQuery, state: FSMContext):
    text, reply_markup = ikb.first_page_calendar(
        await AppointmentNavigation.get_appointment_data(state), CalendarMode.DELETE
    )
    if text and reply_markup:
        await callback.message.edit_text(text=text, reply_markup=reply_markup)
    else:
        await callback.answer(text=PHRASES_RU.error.no_slots)
        await send_master_menu(callback.bot, callback.from_user.id, callback.message.message_id)


@router.callback_query(F.data == PHRASES_RU.callback_data.master.cancel, MasterFilter())
async def _(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await send_master_menu(callback.bot, callback.from_user.id, callback.message.message_id)


@router.callback_query(F.data == PHRASES_RU.callback_data.master.back_to_service_menu, MasterFilter())
async def _(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await message_service_editor(callback)


@router.callback_query(F.data == PHRASES_RU.callback_data.master.service_editor, MasterFilter())
async def message_service_editor(callback: CallbackQuery):
    await callback.message.edit_text(
        text=PHRASES_RU.answer.master.service_editor, reply_markup=inline_mkb.master_service_menu()
    )


@router.callback_query(F.data == PHRASES_RU.callback_data.master.add_service, MasterFilter())
async def _(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MasterStates.WAITING_FOR_NEW_SERVICE)
    await callback.message.edit_text(
        text=PHRASES_RU.title.new_service + PHRASES_RU.answer.master.add_service,
        reply_markup=inline_mkb.back_to_service_menu(),
    )


@router.callback_query(F.data == PHRASES_RU.callback_data.master.edit_service, MasterFilter())
async def edit_service_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        text=PHRASES_RU.answer.master.edit_service, reply_markup=inline_mkb.master_service_editor()
    )


@router.callback_query(F.data == PHRASES_RU.callback_data.master.history, MasterFilter())
async def _(callback: CallbackQuery):
    await pages.get_history(callback.bot, user_id=callback.from_user.id, message_id=callback.message.message_id)
    await callback.answer()
