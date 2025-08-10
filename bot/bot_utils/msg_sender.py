import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from typing import Optional, Union, List
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, Message, InputMediaPhoto

from DB.models import PhotoModel, AppointmentModel
from DB.tables.appointments import AppointmentsTable
from DB.tables.masters import MastersTable
from bot.keyboards import get_keyboard
from config import bot
from config.const import CANCELLED, REJECTED, CONFIRMED
from phrases import PHRASES_RU

logger = logging.getLogger(__name__)


async def send_or_edit_message(
    chat_id: int,
    text: str,
    reply_markup: Optional[Union[InlineKeyboardMarkup, ReplyKeyboardMarkup]] = None,
    message_id: Optional[int] = None,
    **kwargs
) -> Optional[Message]:
    """
    Отправляет новое сообщение или редактирует существующее с детальным логированием.

    :param bot: Объект бота (aiogram.Bot)
    :param chat_id: ID чата
    :param text: Текст сообщения
    :param reply_markup: Клавиатура (Inline или Reply)
    :param message_id: Если передан, редактирует сообщение, иначе отправляет новое
    :param kwargs: Дополнительные аргументы для send_message/edit_message_text
    :return: Объект Message или None в случае ошибки
    """
    try:
        if message_id:
            try:
                message = await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=reply_markup,
                    **kwargs
                )
                return message
            except TelegramBadRequest as e:
                if 'message is not modified' in str(e):
                    return None
                logger.error(
                    f'Editing error (chat_id={chat_id}, message_id={message_id}): {str(e)}',
                    exc_info=True
                )
                raise

        message = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            **kwargs
        )
        return message

    except TelegramBadRequest as e:
        logger.error(
            f'Telegram API ERROR (chat_id={chat_id}): {str(e)}',
            exc_info=True
        )
        raise
    except Exception as e:
        logger.critical(
            f'Unexpected error when sending a message (chat_id={chat_id}): {str(e)}',
            exc_info=True
        )
        raise


def get_media_from_photos(photos: List[PhotoModel], caption: Optional[str] = None) -> List[InputMediaPhoto]:
    media: List[InputMediaPhoto] = []
    for photo in photos:
        media.append(InputMediaPhoto(media=photo.telegram_file_id, caption=caption if len(media) == 0 else None))
    return media[:9]


async def notify_master(bot: Bot, app: AppointmentModel):
    if app.status == CANCELLED:
        text = PHRASES_RU.replace('answer.notify.master.cancelled',
                                  contact='@' + app.client.username if app.client.username
                                  else 'Контакт: ' + app.client.contact,
                                  date=app.formatted_date,
                                  slot_time=app.slot_str)
        with MastersTable() as db:
            masters = db.get_all_masters()
            if len(masters) > 0:
                master = masters[0]
                await bot.send_message(chat_id=master.id, text=text)
            else:
                logger.error('No master in db')


async def notify_client(bot: Bot, app: AppointmentModel):
    try:
        if app.status == CONFIRMED:
            text = PHRASES_RU.replace('answer.notify.client.confirmed', date=app.formatted_date, slot_time=app.slot_str)
            await bot.send_message(chat_id=app.client.user_id, text=text)
        elif app.status == CANCELLED:
            text = PHRASES_RU.replace('answer.notify.client.cancelled', date=app.formatted_date, slot_time=app.slot_str)
            await bot.send_message(chat_id=app.client.user_id, text=text)
        elif app.status == REJECTED:
            text = PHRASES_RU.replace('answer.notify.client.cancelled', date=app.formatted_date, slot_time=app.slot_str)
            await bot.send_message(chat_id=app.client.user_id, text=text)
    except Exception as e:
        logger.error(f'Unexpected error when notifying client (chat_id={app.client.user_id}): {str(e)})')


async def send_reminder(appointment_id: int, reminder_type: str):
    with AppointmentsTable() as db:
        appointment = db.get_appointment_by_id(appointment_id)
        if appointment.status != CONFIRMED:
            return

        time_left = PHRASES_RU.error.unknown
        match reminder_type:
            case '1h':
                time_left = '1 ч до вашей записи!'  # TODO
            case '24h':
                time_left = 'завтра у Вас запланирована запись'
        text = PHRASES_RU.replace('answer.notify.client.scheduled', time_left=time_left)

        await bot.send_message(
            chat_id=appointment.client.user_id,
            text=text,
            reply_markup=get_keyboard(appointment.client.user_id)
        )
