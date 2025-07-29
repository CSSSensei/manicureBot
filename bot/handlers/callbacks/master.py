from aiogram import Router
from aiogram.types import CallbackQuery

from bot.utils.models import MasterButtonCallBack

router = Router()


@router.callback_query(MasterButtonCallBack.filter())
async def handle_navigation_actions(callback: CallbackQuery, callback_data: MasterButtonCallBack):
    ...