from aiogram import Router
from aiogram.types import CallbackQuery

from bot.bot_utils.models import AdminPageCallBack
from bot import pages
from config.const import PageListSection

router = Router()


@router.callback_query(AdminPageCallBack.filter())
async def cut_message_distributor(callback: CallbackQuery, callback_data: AdminPageCallBack):
    type_of_event = callback_data.type_of_event
    page = callback_data.page
    user_id = callback_data.user_id
    match type_of_event:
        case PageListSection.USERS:
            await pages.get_users(callback.from_user.id, page, callback.message.message_id)
        case PageListSection.QUERY:
            await pages.user_query(callback.from_user.id, user_id, page, callback.message.message_id)
        case PageListSection.ACTION_HISTORY:
            await pages.get_history(callback.from_user.id, page, callback.message.message_id)
        case PageListSection.CLIENTS:
            await pages.get_clients(callback.from_user.id, callback.message.id, page)
        case PageListSection.NO_ACTION:
            await callback.answer()
