import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, InputMediaPhoto, Message, ReplyKeyboardMarkup

from config.const import CANCELLED, CONFIRMED, REJECTED
from DB.models import AppointmentModel, PhotoModel
from DB.tables.appointments import AppointmentsTable
from DB.tables.masters import MastersTable
from phrases import PHRASES_RU

logger = logging.getLogger(__name__)


async def send_or_edit_message(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | None = None,
    message_id: int | None = None,
    **kwargs,
) -> Message | None:
    try:
        if message_id:
            try:
                message = await bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id, text=text, reply_markup=reply_markup, **kwargs
                )
                return message
            except TelegramBadRequest as e:
                if 'message is not modified' in str(e):
                    return None
                logger.error(f'Editing error (chat_id={chat_id}, message_id={message_id}): {str(e)}', exc_info=True)
                raise

        message = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, **kwargs)
        return message

    except TelegramBadRequest as e:
        logger.error(f'Telegram API ERROR (chat_id={chat_id}): {str(e)}', exc_info=True)
        raise
    except Exception as e:
        logger.critical(f'Unexpected error when sending a message (chat_id={chat_id}): {str(e)}', exc_info=True)
        raise


def get_media_from_photos(photos: list[PhotoModel], caption: str | None = None) -> list[InputMediaPhoto]:
    media: list[InputMediaPhoto] = []
    for photo in photos:
        media.append(InputMediaPhoto(media=photo.telegram_file_id, caption=caption if len(media) == 0 else None))
    return media[:9]


async def notify_master(bot: Bot, app: AppointmentModel):
    if app.status == CANCELLED:
        text = PHRASES_RU.replace(
            'answer.notify.master.cancelled',
            username=f'@{app.client.username}'
            if app.client.username
            else app.client.first_name or PHRASES_RU.error.no_username,
            user_id=app.client.user_id,
            date=app.formatted_date,
            slot_time=app.slot_str,
        )
        with MastersTable() as db:
            masters = db.get_all_masters()
            if len(masters) > 0:
                master = masters[0]
                await bot.send_message(chat_id=master.user.user_id, text=text)
            else:
                logger.error('No master in db')


async def notify_client(bot: Bot, app: AppointmentModel):
    with MastersTable() as db:
        masters = db.get_all_masters()
        if not masters:
            logger.error('No master in db')
            return
        master = masters[0]
    try:
        data = {
            'date': app.formatted_date,
            'slot_time': app.slot_str,
            'master_id': master.user.user_id,
            'master_username': master.user.username or master.user.first_name or '(здесь)',
        }
        if app.status == CONFIRMED:
            text = PHRASES_RU.replace('answer.notify.client.confirmed', **data)
            await bot.send_message(chat_id=app.client.user_id, text=text, disable_web_page_preview=True)
        elif app.status == CANCELLED:
            text = PHRASES_RU.replace('answer.notify.client.cancelled', **data)
            await bot.send_message(chat_id=app.client.user_id, text=text)
        elif app.status == REJECTED:
            text = PHRASES_RU.replace('answer.notify.client.rejected', **data)
            await bot.send_message(chat_id=app.client.user_id, text=text)
    except Exception as e:
        logger.error(f'Unexpected error when notifying client (chat_id={app.client.user_id}): {str(e)})')


async def send_reminder(bot: Bot, appointment_id: int, reminder_type: str):
    with AppointmentsTable() as db:
        appointment = db.get_appointment_by_id(appointment_id)
        if appointment.status != CONFIRMED:
            return

        time_left = PHRASES_RU.error.unknown
        match reminder_type:
            case '1h':
                time_left = PHRASES_RU.answer.notify.client.h1_notification
            case '24h':
                time_left = PHRASES_RU.replace(
                    'answer.notify.client.h24_notification', service=appointment.service.name.lower()
                )
        text = PHRASES_RU.replace('answer.notify.client.scheduled', time_left=time_left)

        from bot.keyboards import get_keyboard

        await bot.send_message(
            chat_id=appointment.client.user_id, text=text, reply_markup=get_keyboard(appointment.client.user_id)
        )
