import logging
from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.bot_utils.msg_sender import send_reminder
from bot.channel_posting import ChannelPostingService
from config import config, const, scheduler
from DB.models import AppointmentModel
from DB.tables.appointments import AppointmentsTable
from utils.slot_generator import SlotGenerator

logger = logging.getLogger(__name__)


def load_scheduled_notifications(async_scheduler: AsyncIOScheduler, bot: Bot):
    with AppointmentsTable() as db:
        apps, pagination = db.get_appointments_by_status_and_time_range(
            const.CONFIRMED, datetime.now(), datetime.now() + timedelta(weeks=12), 1, 1000
        )

        for app in apps:
            if app.slot.start_time > datetime.now():
                schedule_reminders(app.appointment_id, app.slot.start_time, bot, async_scheduler)
        if pagination.total_items > 1000:
            for page in range(2, pagination.total_pages + 1):
                apps, pagination = db.get_appointments_by_status_and_time_range(
                    const.CONFIRMED, datetime.now(), datetime.now() + timedelta(weeks=12), page, 1000
                )

                for app in apps:
                    if app.slot.start_time > datetime.now():
                        schedule_reminders(app.appointment_id, app.slot.start_time, bot, async_scheduler)


def schedule_reminders(
    appointment_id: int, slot_start: datetime, bot: Bot, async_scheduler: AsyncIOScheduler = scheduler
):
    notify_24h = slot_start - timedelta(hours=24)
    if notify_24h > datetime.now():
        async_scheduler.add_job(
            send_reminder,
            trigger='date',
            run_date=notify_24h,
            args=(bot, appointment_id, '24h'),
            id=f'24h_{appointment_id}',
        )

    notify_1h = slot_start - timedelta(hours=1)
    if notify_1h > datetime.now():
        async_scheduler.add_job(
            send_reminder,
            trigger='date',
            run_date=notify_1h,
            args=(bot, appointment_id, '1h'),
            id=f'1h_{appointment_id}',
        )


def cancel_scheduled_reminders(appointment: AppointmentModel):
    now = datetime.now()

    if appointment.slot.start_time - now > timedelta(hours=24):
        try:
            scheduler.remove_job(f'24h_{appointment.appointment_id}')
        except JobLookupError:
            logger.warning(f'24-hour reminder for recording {appointment.appointment_id} not found')
        except Exception as e:
            logger.error(f'Error deleting a 24-hour reminder: {e}')

    if appointment.slot.start_time - now > timedelta(hours=1):
        try:
            scheduler.remove_job(f'1h_{appointment.appointment_id}')
        except JobLookupError:
            logger.warning(f'1-hour reminder for recording {appointment.appointment_id} not found')
        except Exception as e:
            logger.error(f'Error deleting a 1-hour reminder: {e}')


class SlotNotifierBot:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = scheduler
        self.channel_service = ChannelPostingService(config.tg_bot.channel_id, bot)

    async def on_startup(self):
        await self.channel_service.post_or_update_slots_message()

        self.scheduler.add_job(self.update_channel_slots, 'interval', hours=1, id='channel_slots_update')

    async def update_channel_slots(self):
        await self.channel_service.post_or_update_slots_message()


async def setup_scheduler(async_scheduler: AsyncIOScheduler, bot: Bot):
    load_scheduled_notifications(async_scheduler, bot)

    async def _auto_generate_month_after_next():
        generator = SlotGenerator()
        generated_count = generator.generate_for_month_after_next()
        if generated_count > 0:
            await SlotNotifierBot(bot).update_channel_slots()

    async def _daily_check_generation():
        today = datetime.now()

        if 26 <= today.day <= 31:
            generator = SlotGenerator()

            next_month = today.month + 2
            next_year = today.year
            if next_month > 12:
                next_month -= 12
                next_year += 1

            setting_key = f'generated_{next_year}_{next_month}'
            already_generated = generator.settings_db.get_setting(setting_key)

            if not already_generated:
                logger.warning('Пропущена генерация на следующий месяц! Генерируем...')
                generated_count = generator.generate_for_month_after_next()
                if generated_count > 0:
                    await SlotNotifierBot(bot).update_channel_slots()

    async_scheduler.add_job(
        _auto_generate_month_after_next, CronTrigger(day=25, hour=6, minute=13), id='month_after_next_generation'
    )

    async_scheduler.add_job(_daily_check_generation, CronTrigger(hour=8, minute=29), id='daily_generation_check')

    await SlotNotifierBot(bot).on_startup()
