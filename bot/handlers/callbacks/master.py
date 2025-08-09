from datetime import datetime, date

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from DB.tables.appointments import AppointmentsTable
from DB.tables.masters import MastersTable
from DB.tables.services import ServicesTable
from DB.tables.slots import SlotsTable
from bot import pages
from bot.bot_utils import msg_sender
from bot.bot_utils.filters import NotBookingCalendar, MasterFilter
from bot.bot_utils.models import MasterButtonCallBack, AddSlotsMonthCallBack, MasterServiceCallBack, EditServiceCallBack, MonthCallBack, \
    DeleteSlotCallBack
from bot.handlers.master import send_master_menu
from bot.states import MasterStates
from bot.keyboards.master import inline as inline_mkb
from bot.keyboards.default import inline as ikb
from config import const, bot
from config.const import CalendarMode
from phrases import PHRASES_RU
from utils import format_list, format_string, db_manager

router = Router()


@router.callback_query(MonthCallBack.filter(), NotBookingCalendar())
async def handle_slot_choosing(callback: CallbackQuery, callback_data: MonthCallBack):
    if callback_data.action != 0:
        # Обработка переключения месяцев
        month = callback_data.month + callback_data.action
        year = callback_data.year
        year += month // 12 if month > 12 else -1 if month < 1 else 0
        mode = callback_data.mode
        month = 1 if month > 12 else 12 if month < 1 else month

        prev_enabled = not (month == datetime.now().month and year == datetime.now().year)
        text, reply_markup = ikb.create_calendar_keyboard(month, year, prev_enabled, mode)
        await callback.message.edit_text(text=text, reply_markup=reply_markup)
        return
    if callback_data.day <= 0:
        await callback.answer(PHRASES_RU.error.date)
        return
    mode = callback_data.mode
    selected_date = date(callback_data.year, callback_data.month, callback_data.day)
    match mode:
        case CalendarMode.DELETE:
            await callback.message.edit_text(text=PHRASES_RU.replace('answer.master.choose_slot_to_delete',
                                                                     date=selected_date.strftime('%d.%m.%Y')),
                                             reply_markup=inline_mkb.delete_slots_menu(selected_date))
        case CalendarMode.APPOINTMENT_MAP:
            await pages.get_master_apps(callback, selected_date, 1)


@router.callback_query(DeleteSlotCallBack.filter(), MasterFilter())
async def handle_slot_deletion(callback: CallbackQuery, callback_data: DeleteSlotCallBack):
    action = callback_data.action
    slot_date = callback_data.slot_date
    match action:
        case const.Action.slot_calendar:  # BACK
            prev_enabled = not (slot_date.month == datetime.now().month and slot_date.year == datetime.now().year)
            text, reply_markup = ikb.create_calendar_keyboard(slot_date.month, slot_date.year, prev_enabled, CalendarMode.DELETE)
            await callback.message.edit_text(text=text, reply_markup=reply_markup)
        case const.Action.check_slot_to_delete:
            slot_id = callback_data.slot_id
            with SlotsTable() as db:
                slot = db.get_slot(slot_id)
                await callback.message.edit_text(text=PHRASES_RU.replace('answer.master.slot_info',
                                                                         date=slot.start_time.date().strftime('%d.%m.%Y'),
                                                                         slot_str=str(slot)),
                                                 reply_markup=inline_mkb.slot_deletion(slot))
        case const.Action.delete_slot:
            slot_id = callback_data.slot_id
            with SlotsTable() as db:
                success, message = db.delete_slot(slot_id)
                await callback.answer(message)
            reply_markup = inline_mkb.delete_slots_menu(slot_date)
            if len(reply_markup.inline_keyboard) > 1:  # проверка, что после удаления остались ещё свободные слоты на этот день
                await callback.message.edit_text(text=PHRASES_RU.replace('answer.master.choose_slot_to_delete',
                                                                         date=slot_date.strftime('%d.%m.%Y')),
                                                 reply_markup=reply_markup)
            else:  # если слотов не осталось, то отправляем клавиатуру календаря
                current_date = datetime.now()
                is_current_month = (slot_date.month == current_date.month and
                                    slot_date.year == current_date.year)
                prev_enabled = not is_current_month
                text, reply_markup = ikb.create_calendar_keyboard(slot_date.month, slot_date.year, prev_enabled, CalendarMode.DELETE)
                await callback.message.edit_text(text=text, reply_markup=reply_markup)


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
            case (_, const.REJECTED):
                with SlotsTable() as slots_db:
                    slots_db.set_slot_availability(app.slot.id, True)
                app_db.update_appointment_status(app.appointment_id, const.REJECTED)
                await callback.answer(PHRASES_RU.answer.status.rejected)
                app.status = const.REJECTED
                await msg_sender.notify_client(bot, app)
            case (_, const.CONFIRMED):
                app_db.update_appointment_status(app.appointment_id, const.CONFIRMED)
                await callback.answer(PHRASES_RU.answer.status.confirmed)
                app.status = const.CONFIRMED
                await msg_sender.notify_client(bot, app)
            case (_, status) if status in app_db.valid_statuses:
                app_db.update_appointment_status(app.appointment_id, status)
                await callback.answer(status)
                app.status = status
                await msg_sender.notify_client(bot, app)

        await callback.message.delete()

        if callback_data.msg_to_delete:
            msgs = list(map(int, callback_data.msg_to_delete.split(',')))
            msgs_list = [i for i in range(msgs[0], msgs[-1] + 1)]
            await bot.delete_messages(chat_id=callback.from_user.id, message_ids=msgs_list)

        master_db.update_current_state(callback.from_user.id)

        if next_app := app_db.get_nth_pending_appointment(0):
            await pages.notify_master(next_app)


@router.callback_query(AddSlotsMonthCallBack.filter(), MasterFilter())
async def handle_month_generation(callback: CallbackQuery, callback_data: AddSlotsMonthCallBack):
    action = callback_data.action
    month = callback_data.month
    year = callback_data.year

    slots = format_list.generate_slots_for_month(month, year)
    slots_text = format_string.slots_to_text(slots)
    match action:
        case 'check':
            text = f'Проверьте, что слоты сгенерированы верно\n\n<code>{slots_text}</code>'
            await callback.message.edit_text(text=text,
                                             reply_markup=inline_mkb.master_confirm_adding_slot(month, year))
        case 'add':
            text = db_filler.add_slots_from_list([(sl.start_time, sl.end_time) for sl in slots])
            text_chunks = format_string.split_text(text, 4096)
            for i in range(len(text_chunks)):
                if i == 0:
                    await callback.message.edit_text(text_chunks[i], parse_mode="Markdown")
                else:
                    await bot.send_message(chat_id=callback.from_user.id, text=text_chunks[i], parse_mode="Markdown")


@router.callback_query(MasterServiceCallBack.filter(), MasterFilter())
async def handle_service_edit(callback: CallbackQuery, callback_data: MasterServiceCallBack, state: FSMContext):
    await state.clear()
    service_id = callback_data.service_id
    action = callback_data.action
    with ServicesTable() as db:
        service = db.get_service(service_id)
        service_text = format_string.service_text(service)
        text = '<i>Нажмите на соответствующую кнопку для изменения текущей услуги</i>\n\n'
        if action:
            match action:
                case const.Action.set_active:
                    db.toggle_service_active(service_id, True)
                    service.is_active = True
                case const.Action.set_inactive:
                    db.toggle_service_active(service_id, False)
                    service.is_active = False
                case const.Action.service_update:
                    text = '✅ Услуга обновлена и уже активна!\n\n' + text

        await callback.message.edit_text(text=text + service_text, reply_markup=inline_mkb.edit_current_service(service))


@router.callback_query(EditServiceCallBack.filter(), MasterFilter())
async def _(callback: CallbackQuery, callback_data: EditServiceCallBack, state: FSMContext):
    service_id = callback_data.service_id
    await state.update_data(service_id=service_id)
    await state.set_state(MasterStates.WAITING_FOR_EDIT_SERVICE)
    await callback.message.edit_text(text=PHRASES_RU.answer.master.add_service,
                                     reply_markup=inline_mkb.back_to_edit_service(service_id))


@router.callback_query(StateFilter(MasterStates.WAITING_FOR_SLOT), F.data == PHRASES_RU.callback_data.master.confirm_add_slot, MasterFilter())
async def _(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    slots = data.get('parsed_slots', [])

    if not slots:
        await callback.message.edit_text(PHRASES_RU.error.slots_not_flound)
        return
    result_text = db_filler.add_slots_from_list(slots)
    text_chunks = format_string.split_text(result_text, 4096)
    await state.clear()
    for i in range(len(text_chunks)):
        if i == 0:
            await callback.message.edit_text(text_chunks[i], parse_mode="Markdown")
        else:
            await bot.send_message(chat_id=callback.from_user.id, text=text_chunks[i], parse_mode="Markdown")


@router.callback_query(F.data == PHRASES_RU.callback_data.master.confirm_add_slot, MasterFilter())
async def _(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(PHRASES_RU.error.booking.try_again)
    await state.clear()


@router.callback_query(StateFilter(MasterStates.WAITING_FOR_EDIT_SERVICE),
                       F.data == PHRASES_RU.callback_data.master.confirm_edit_service,
                       MasterFilter())
async def _(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    service = data.get('parsed_service')

    if not service:
        await callback.message.edit_text(PHRASES_RU.error.booking.try_again)
        return
    with ServicesTable() as db:
        db.update_service(service)

    await handle_service_edit(callback, MasterServiceCallBack(service_id=service.id, action=const.Action.service_update), state)


@router.callback_query(F.data == PHRASES_RU.callback_data.master.confirm_edit_service, MasterFilter())
async def _(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(PHRASES_RU.error.booking.try_again)
    await state.clear()


@router.callback_query(StateFilter(MasterStates.WAITING_FOR_NEW_SERVICE),
                       F.data == PHRASES_RU.callback_data.master.confirm_add_service,
                       MasterFilter())
async def _(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    service = data.get('parsed_service')

    if not service:
        await callback.message.edit_text(PHRASES_RU.error.booking.try_again)
        return
    with ServicesTable() as db:
        db.add_service(service)
    response = f"✅ Услуга добавлена\n\n"
    response += f"▪ Название: <i>{service.name}</i>\n"  # TODO
    if service.description:
        response += f"▪ Описание: <i>{service.description}</i>\n"
    if service.price:
        response += f"▪ Стоимость: <i>{service.price} руб.</i>\n"
    if service.duration:
        response += f"▪ Длительность: <i>{service.duration} мин.</i>"

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
    await callback.message.edit_text(text='Клиенты')


@router.callback_query(F.data == PHRASES_RU.callback_data.master.appointment_map, MasterFilter())
async def _(callback: CallbackQuery):
    now = datetime.now()
    text, reply_markup = ikb.create_calendar_keyboard(now.month, now.year, False, CalendarMode.APPOINTMENT_MAP)
    await callback.message.edit_text(text=text, reply_markup=reply_markup)


@router.callback_query(F.data == PHRASES_RU.callback_data.master.add_manual_slots, MasterFilter())
async def _(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MasterStates.WAITING_FOR_SLOT)
    await callback.message.edit_text(text=PHRASES_RU.answer.master.add_manual_slot,
                                     reply_markup=inline_mkb.back_to_adding())


@router.callback_query(F.data == PHRASES_RU.callback_data.master.add_slots, MasterFilter())
async def add_menu(callback: CallbackQuery):
    await callback.message.edit_text(text=PHRASES_RU.answer.master.add_slots_menu,
                                     reply_markup=inline_mkb.add_slots_menu())


@router.callback_query(F.data == PHRASES_RU.callback_data.master.delete_slots, MasterFilter())
async def delete_slots_calendar_handler(callback: CallbackQuery):
    text, reply_markup = ikb.first_page_calendar(CalendarMode.DELETE)
    if text and reply_markup:
        await callback.message.edit_text(text=text, reply_markup=reply_markup)
    else:
        await callback.answer(text=PHRASES_RU.error.no_slots)
        await send_master_menu(callback.from_user.id, callback.message.message_id)


@router.callback_query(F.data == PHRASES_RU.callback_data.master.cancel, MasterFilter())
async def _(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await send_master_menu(callback.from_user.id, callback.message.message_id)


@router.callback_query(F.data == PHRASES_RU.callback_data.master.back_to_service_menu, MasterFilter())
async def _(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await message_service_editor(callback)


@router.callback_query(F.data == PHRASES_RU.callback_data.master.service_editor, MasterFilter())
async def message_service_editor(callback: CallbackQuery):
    await callback.message.edit_text(text=PHRASES_RU.answer.master.service_editor,
                                     reply_markup=inline_mkb.master_service_menu())


@router.callback_query(F.data == PHRASES_RU.callback_data.master.add_service, MasterFilter())
async def _(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MasterStates.WAITING_FOR_NEW_SERVICE)
    await callback.message.edit_text(text=PHRASES_RU.title.new_service + PHRASES_RU.answer.master.add_service,
                                     reply_markup=inline_mkb.back_to_service_menu())


@router.callback_query(F.data == PHRASES_RU.callback_data.master.edit_service, MasterFilter())
async def edit_service_menu(callback: CallbackQuery):
    await callback.message.edit_text(text=PHRASES_RU.answer.master.edit_service,
                                     reply_markup=inline_mkb.master_service_editor())


@router.callback_query(F.data == PHRASES_RU.callback_data.master.history, MasterFilter())
async def _(callback: CallbackQuery):
    await pages.get_history(user_id=callback.from_user.id, message_id=callback.message.message_id)
    await callback.answer()
