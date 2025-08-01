import logging
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from typing import Optional, Union, List
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, Message, InputMediaPhoto

from DB.models import PhotoModel

logger = logging.getLogger(__name__)


async def send_or_edit_message(
    bot: Bot,
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
                if "message is not modified" in str(e):
                    return None
                logger.error(
                    f"Editing error (chat_id={chat_id}, message_id={message_id}): {str(e)}",
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
            f"Telegram API ERROR (chat_id={chat_id}): {str(e)}",
            exc_info=True
        )
        raise
    except Exception as e:
        logger.critical(
            f"Unexpected error when sending a message (chat_id={chat_id}): {str(e)}",
            exc_info=True
        )
        raise


def get_media_from_photos(photos: List[PhotoModel], caption: Optional[str] = None) -> List[InputMediaPhoto]:
    media: List[InputMediaPhoto] = []
    for photo in photos:
        media.append(InputMediaPhoto(media=photo.telegram_file_id, caption=caption if len(media) == 0 else None))
    return media[:9]
