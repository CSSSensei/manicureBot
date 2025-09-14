import logging
from datetime import datetime, timedelta
from apscheduler.jobstores.base import JobLookupError

from DB.models import AppointmentModel
from DB.tables.appointments import AppointmentsTable
from bot.bot_utils.msg_sender import send_reminder
from bot.channel_posting import ChannelPostingService
from config import scheduler, const, bot, config

logger = logging.getLogger(__name__)


def load_scheduled_notifications():
    with AppointmentsTable() as db:
        apps, pagination = db.get_appointments_by_status_and_time_range(const.CONFIRMED,
                                                                        datetime.now(),
                                                                        datetime.now() + timedelta(weeks=12),
                                                                        1,
                                                                        1000)

        for app in apps:
            if app.slot.start_time > datetime.now():
                schedule_reminders(app.appointment_id, app.slot.start_time)
        if pagination.total_items > 1000:
            for page in range(2, pagination.total_pages + 1):
                apps, pagination = db.get_appointments_by_status_and_time_range(const.CONFIRMED,
                                                                                datetime.now(),
                                                                                datetime.now() + timedelta(weeks=12),
                                                                                page,
                                                                                1000)

                for app in apps:
                    if app.slot.start_time > datetime.now():
                        schedule_reminders(app.appointment_id, app.slot.start_time)


def schedule_reminders(appointment_id: int, slot_start: datetime):
    notify_24h = slot_start - timedelta(hours=24)
    if notify_24h > datetime.now():
        scheduler.add_job(
            send_reminder,
            trigger='date',
            run_date=notify_24h,
            args=(appointment_id, "24h"),
            id=f"24h_{appointment_id}"
        )

    notify_1h = slot_start - timedelta(hours=1)
    if notify_1h > datetime.now():
        scheduler.add_job(
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
