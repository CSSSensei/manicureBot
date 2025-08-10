from datetime import datetime, timedelta

from DB.tables.appointments import AppointmentsTable
from bot.bot_utils.msg_sender import send_reminder
from config import scheduler, const


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


def cancel_scheduled_reminders(appointment_id: int):
    scheduler.remove_job(f"24h_{appointment_id}")
    scheduler.remove_job(f"1h_{appointment_id}")
