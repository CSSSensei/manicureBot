import logging
from datetime import datetime, timedelta
from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from DB.models import AppointmentModel
from DB.tables.appointments import AppointmentsTable
from bot.bot_utils.msg_sender import send_reminder
from bot.channel_posting import ChannelPostingService
from config import scheduler, const, bot, config
from utils.slot_generator import SlotGenerator

logger = logging.getLogger(__name__)


def load_scheduled_notifications(async_scheduler: AsyncIOScheduler):
    with AppointmentsTable() as db:
        apps, pagination = db.get_appointments_by_status_and_time_range(const.CONFIRMED,
                                                                        datetime.now(),
                                                                        datetime.now() + timedelta(weeks=12),
                                                                        1,
                                                                        1000)

        for app in apps:
            if app.slot.start_time > datetime.now():
                schedule_reminders(app.appointment_id, app.slot.start_time, async_scheduler)
        if pagination.total_items > 1000:
            for page in range(2, pagination.total_pages + 1):
                apps, pagination = db.get_appointments_by_status_and_time_range(const.CONFIRMED,
                                                                                datetime.now(),
                                                                                datetime.now() + timedelta(weeks=12),
                                                                                page,
                                                                                1000)

                for app in apps:
                    if app.slot.start_time > datetime.now():
                        schedule_reminders(app.appointment_id, app.slot.start_time, async_scheduler)


def schedule_reminders(appointment_id: int, slot_start: datetime, async_scheduler: AsyncIOScheduler = scheduler):
    notify_24h = slot_start - timedelta(hours=24)
    if notify_24h > datetime.now():
        async_scheduler.add_job(
            send_reminder,
            trigger='date',
            run_date=notify_24h,
            args=(appointment_id, "24h"),
            id=f"24h_{appointment_id}"
        )

    notify_1h = slot_start - timedelta(hours=1)
    if notify_1h > datetime.now():
        async_scheduler.add_job(
            send_reminder,
            trigger='date',
            run_date=notify_1h,
            args=(appointment_id, "1h"),
            id=f"1h_{appointment_id}"
        )


def cancel_scheduled_reminders(appointment: AppointmentModel):
    now = datetime.now()

    if appointment.slot.start_time - now > timedelta(hours=24):
        try:
            scheduler.remove_job(f'24h_{appointment.appointment_id}')
        except JobLookupError:
            logger.warning(f"24-hour reminder for recording {appointment.appointment_id} not found")
        except Exception as e:
            logger.error(f"Error deleting a 24-hour reminder: {e}")

    if appointment.slot.start_time - now > timedelta(hours=1):
        try:
            scheduler.remove_job(f'1h_{appointment.appointment_id}')
        except JobLookupError:
            logger.warning(f"1-hour reminder for recording {appointment.appointment_id} not found")
        except Exception as e:
            logger.error(f"Error deleting a 1-hour reminder: {e}")


class SlotNotifierBot:
    def __init__(self):
        self.bot = bot
        self.scheduler = scheduler
        self.channel_service = ChannelPostingService(config.tg_bot.channel_id)

    async def on_startup(self):
        """Запуск при старте бота."""
        # Первоначальная публикация
        await self.channel_service.post_or_update_slots_message()

        # Планируем регулярное обновление (каждый час)
        self.scheduler.add_job(
            self.update_channel_slots,
            'interval',
            hours=1,
            id='channel_slots_update'
        )

    async def update_channel_slots(self):
        """Обновляет сообщение со слотами в канале."""
        await self.channel_service.post_or_update_slots_message()


async def auto_generate_month_after_next():
    """Генерация слотов на месяц после следующего"""
    generator = SlotGenerator()
    generated_count = generator.generate_for_month_after_next()
    if generated_count > 0:
        await SlotNotifierBot().update_channel_slots()


async def daily_check_generation():
    """Ежедневная проверка необходимости генерации"""
    today = datetime.now()

    # Если сегодня 26-31 число и еще не генерировали на следующий месяц
    if 26 <= today.day <= 31:
        generator = SlotGenerator()

        # Проверяем статус генерации
        next_month = today.month + 1
        next_year = today.year
        if next_month > 12:
            next_month = 1
            next_year += 1

        setting_key = f"generated_{next_year}_{next_month}"
        already_generated = generator.settings_db.get_setting(setting_key)

        if not already_generated:
            logger.warning("Пропущена генерация на следующий месяц! Генерируем...")
            generated_count = generator.monthly_auto_generation()
            if generated_count > 0:
                await SlotNotifierBot().update_channel_slots()


async def setup_scheduler(async_scheduler: AsyncIOScheduler):
    """Настройка автоматических задач"""

    load_scheduled_notifications(async_scheduler)
    # Генерация на месяц после следующего (cur_month + 2) - 25 числа в 10:00
    async_scheduler.add_job(
        auto_generate_month_after_next,
        # CronTrigger(day=25, hour=10, minute=13),
        CronTrigger(day=15, hour=22, minute=47),
        id='month_after_next_generation'
    )

    # Ежедневная проверка (на случай если 25 число было пропущено)
    async_scheduler.add_job(
        daily_check_generation,
        # CronTrigger(hour=8, minute=29),
        CronTrigger(day=15, hour=22, minute=48),
        id='daily_generation_check'
    )

    await SlotNotifierBot().on_startup()
