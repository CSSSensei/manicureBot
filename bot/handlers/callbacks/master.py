from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from DB.tables.appointments import AppointmentsTable
from DB.tables.masters import MastersTable
from DB.tables.services import ServicesTable
from DB.tables.slots import SlotsTable
from bot import pages
from bot.bot_utils.models import MasterButtonCallBack
from bot.handlers.master import send_master_menu
from bot.states import MasterStates
from bot.keyboards.master import inline as inline_mkb
from config import const, bot
from phrases import PHRASES_RU

router = Router()


@router.callback_query(MasterButtonCallBack.filter())
async def handle_navigation_actions(callback: CallbackQuery, callback_data: MasterButtonCallBack):
    status_to_set = callback_data.status

    with AppointmentsTable() as app_db, MastersTable() as master_db:
        if status_to_set not in app_db.valid_statuses:
            return
        app = app_db.get_appointment_by_id(callback_data.appointment_id)
        if not app:
            await callback.answer("Запись не найдена")  # TODO переделать коллбэк
            return

        match (app.status, status_to_set):
            case (const.CANCELLED, _):
                await callback.answer('Запись уже отменена пользователем')  # TODO переделать коллбэк
            case (_, const.REJECTED):
                with SlotsTable() as slots_db:
                    slots_db.set_slot_availability(app.slot.id, True)
                app_db.update_appointment_status(app.appointment_id, const.REJECTED)
                await callback.answer(const.REJECTED)  # TODO переделать коллбэк
            case (_, status) if status in app_db.valid_statuses:
                app_db.update_appointment_status(app.appointment_id, status)
                await callback.answer(status)  # TODO переделать коллбэк

        await callback.message.delete()

        if callback_data.msg_to_delete:
            msgs = list(map(int, callback_data.msg_to_delete.split(',')))
            msgs_list = [i for i in range(msgs[0], msgs[-1] + 1)]
            await bot.delete_messages(chat_id=callback.from_user.id, message_ids=msgs_list)

        master_db.update_current_state(callback.from_user.id)

        if next_app := app_db.get_nth_pending_appointment(0):
            await pages.notify_master(next_app)


@router.callback_query(StateFilter(MasterStates.WAITING_FOR_SLOT), F.data == PHRASES_RU.callback_data.master.confirm_add_slot)
async def _(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    slots = data.get('parsed_slots', [])

    if not slots:
        await callback.message.edit_text("⚠️ Не найдены слоты для добавления")  # TODO
        return
    added_slots = []
    with SlotsTable() as db:
        for start, end in slots:
            slot_id = db.add_slot(start, end)
            added_slots.append((slot_id, start, end))

    result_text = "✅ *Успешно добавлены слоты:*\n\n"
    for slot_id, start, end in added_slots:
        result_text += (
            f"• *{start.strftime('%d.%m.%Y')}* "
            f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')} "
            f"(ID: `{slot_id}`)\n"
        )
    await callback.message.edit_text(result_text, parse_mode="Markdown", reply_markup=inline_mkb.cancel_button())
    await state.clear()


@router.callback_query(StateFilter(MasterStates.WAITING_FOR_SERVICE), F.data == PHRASES_RU.callback_data.master.confirm_add_slot)
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

    await callback.message.edit_text(response, reply_markup=inline_mkb.cancel_button())
    await state.clear()


@router.callback_query(F.data == PHRASES_RU.callback_data.master.clients)
async def _(callback: CallbackQuery):
    await callback.message.edit_text(text='Клиенты')


@router.callback_query(F.data == PHRASES_RU.callback_data.master.add_slots)
async def _(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MasterStates.WAITING_FOR_SLOT)
    await callback.message.edit_text(text=PHRASES_RU.answer.master.add_slot, reply_markup=inline_mkb.cancel_button())


@router.callback_query(F.data == PHRASES_RU.callback_data.master.cancel)
async def _(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await send_master_menu(callback.from_user.id, callback.message.message_id)


@router.callback_query(F.data == PHRASES_RU.callback_data.master.service_editor)
async def _(callback: CallbackQuery):
    await callback.message.edit_text(text=PHRASES_RU.answer.master.service_editor, reply_markup=inline_mkb.master_service_editor())


@router.callback_query(F.data == PHRASES_RU.callback_data.master.add_service)
async def _(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MasterStates.WAITING_FOR_SERVICE)
    await callback.message.edit_text(text=PHRASES_RU.answer.master.add_service, reply_markup=inline_mkb.cancel_button())


@router.callback_query(F.data == PHRASES_RU.callback_data.master.history)
async def _(callback: CallbackQuery):
    await pages.get_history(user_id=callback.from_user.id, message_id=callback.message.message_id)
    await callback.answer()
