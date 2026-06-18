import logging
from collections import defaultdict
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from bot.metrics import BOT_NAME, CHANNEL_UPDATES
from config import const
from DB.tables.channel_messages import ChannelMessagesTable
from DB.tables.slots import SlotsTable

logger = logging.getLogger(__name__)


class ChannelPostingService:
    def __init__(self, channel_id: int, bot: Bot):
        self.bot = bot
        self.channel_id = channel_id
        self.messages_db = ChannelMessagesTable()
        self.slots_db = SlotsTable()

    async def generate_slots_message(self) -> str:
        # Получаем слоты на ближайшие 2 месяца
        end_date = datetime.now() + timedelta(weeks=8)
        slots = self.slots_db.get_available_slots(to_time=end_date)
        if not slots:
            return 'На данный момент все окошки заняты!\n\nСледите за обновлениями ❤️'
        message = '<b>Свободные окошки</b>\n'
        slots_by_month = defaultdict(lambda: defaultdict(list))
        for slot in slots:
            year_month = (slot.start_time.year, slot.start_time.month)
            day = slot.start_time.day
            slots_by_month[year_month][day].append(slot)

        sorted_months = sorted(slots_by_month.keys())

        result_lines = []

        for year, month in sorted_months:
            month_name = const.MONTHS[month].capitalize()
            result_lines.append(f'\n<i>{month_name}</i>')

            days_slots = slots_by_month[(year, month)]

            for day in sorted(days_slots.keys()):
                date_slots = days_slots[day]
                date_slots.sort(key=lambda x: x.start_time)

                slot_strings = []
                for slot in date_slots:
                    slot_strings.append(slot.start_time.strftime('%H:%M'))

                line = f'{day} — {" ".join(slot_strings)}'
                result_lines.append(line)

        message += '\n'.join(result_lines)
        message += f'\n\n💅 Записаться: @{(await self.bot.get_me()).username}'
        return message

    async def post_or_update_slots_message(self) -> bool:
        try:
            message_text = await self.generate_slots_message()

            existing_message = self.messages_db.get_message_info(
                self.channel_id,
                'slots',
            )

            if existing_message:
                await self.bot.edit_message_text(
                    chat_id=self.channel_id,
                    message_id=existing_message.message_id,
                    text=message_text,
                    parse_mode='HTML',
                )
                CHANNEL_UPDATES.labels(bot=BOT_NAME, action='edited').inc()
                return True
            else:
                message = await self.bot.send_message(chat_id=self.channel_id, text=message_text, parse_mode='HTML')

                self.messages_db.save_or_update_message(
                    channel_id=self.channel_id,
                    message_id=message.message_id,
                    message_type='slots',
                )
                CHANNEL_UPDATES.labels(bot=BOT_NAME, action='posted').inc()
                return True

        except TelegramBadRequest as e:
            if 'message is not modified' in str(e):
                return True
            else:
                raise

        except Exception as e:
            logger.error(f'CHANNEL_POST_ERROR: {str(e)}')
            return False

    async def delete_slots_message(self) -> bool:
        try:
            message_info = self.messages_db.get_message_info(
                self.channel_id,
                'slots',
            )

            if message_info:
                await self.bot.delete_message(
                    chat_id=self.channel_id,
                    message_id=message_info.message_id,
                )
                self.messages_db.deactivate_message(
                    self.channel_id,
                    'slots',
                )
                return True
            return False

        except Exception as e:
            logger.error(f'CHANNEL_DELETE_ERROR: {str(e)}')
            return False
