from aiogram import Router
from aiogram.types import CallbackQuery

from DB.tables.appointments import AppointmentsTable
from DB.tables.masters import MastersTable
from bot import pages
from bot.utils.models import MasterButtonCallBack
from config import bot

router = Router()


@router.callback_query(MasterButtonCallBack.filter())
async def handle_navigation_actions(callback: CallbackQuery, callback_data: MasterButtonCallBack):
    status = callback_data.status
    appointment_id = callback_data.appointment_id
    msg_to_delete = callback_data.msg_to_delete
    with AppointmentsTable() as app_db, MastersTable() as master_db:
        if status in app_db.valid_statuses:
            app_db.update_appointment_status(appointment_id, status)
            await callback.answer(status)  # TODO переделать коллбэк
            await callback.message.delete()
            if msg_to_delete:
                msgs = list(map(int, msg_to_delete.split(',')))
                msgs_list = [i for i in range(msgs[0], msgs[-1] + 1)]
                await bot.delete_messages(chat_id=callback.from_user.id, message_ids=msgs_list)
            master_db.update_current_state(callback.from_user.id)
            app_data = app_db.get_nth_pending_appointment(0)
            if app_data:
                await pages.notify_master(app_data)
