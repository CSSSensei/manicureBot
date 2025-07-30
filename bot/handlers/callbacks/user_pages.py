from aiogram import Router
from aiogram.types import CallbackQuery

from bot.pages import get_active_bookings
from bot.utils.models import BookingPageCallBack
from config import bot

router = Router()


@router.callback_query(BookingPageCallBack.filter())
async def booking_page_distributor(callback: CallbackQuery, callback_data: BookingPageCallBack):
    await callback.answer()
    page = callback_data.page
    msg_to_delete = callback_data.msg_to_delete
    if page is None:  # пустой коллбэк
        return
    await callback.message.delete()
    if msg_to_delete:
        msgs = list(map(int, msg_to_delete.split(',')))
        msgs_list = [i for i in range(msgs[0], msgs[-1] + 1)]
        await bot.delete_messages(chat_id=callback.from_user.id, message_ids=msgs_list)
    await get_active_bookings(callback.from_user.id, page)
