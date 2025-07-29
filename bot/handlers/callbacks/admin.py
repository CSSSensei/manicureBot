from aiogram import Router
from aiogram.types import CallbackQuery

from bot.utils.models import PageCallBack
from bot import pages

router = Router()


@router.callback_query(PageCallBack.filter())
async def cut_message_distributor(callback: CallbackQuery, callback_data: PageCallBack):
    action = callback_data.action
    page = callback_data.page
    user_id = callback_data.user_id
    if action == 1:
        await pages.get_users(callback.from_user.id, page, callback.message.message_id)
    elif action == 2:
        await pages.user_query(callback.from_user.id, user_id, page, callback.message.message_id)
    elif action == -1:
        await callback.answer()
