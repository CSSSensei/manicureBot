from aiogram import Router, F
from aiogram.types import CallbackQuery

from DB.tables.appointments import AppointmentsTable
from DB.tables.masters import MastersTable
from DB.tables.slots import SlotsTable
from bot import pages
from bot.utils.models import MasterButtonCallBack
from config import bot
from config import const
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


@router.callback_query(F.data == PHRASES_RU.callback_data.master.clients)
async def _(callback: CallbackQuery):
    await callback.message.edit_text(text='Была нажата истории')


@router.callback_query(F.data == PHRASES_RU.callback_data.master.history)
async def _(callback: CallbackQuery):
    await pages.get_history(callback.from_user.id)
