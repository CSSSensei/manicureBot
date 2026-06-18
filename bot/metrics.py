import logging
import os

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

BOT_NAME = os.getenv('BOT_NAME', 'manicure')


APPOINTMENTS_CREATED = Counter(
    'bot_appointments_created_total',
    'Total appointments (bookings) created by clients',
    ['bot'],
)

APPOINTMENT_STATUS_CHANGES = Counter(
    'bot_appointment_status_changes_total',
    'Total appointment status transitions',
    ['bot', 'status', 'actor'],
)

BOOKINGS_WITH_COMMENT = Counter(
    'bot_bookings_with_comment_total',
    'Bookings created with a non-empty comment',
    ['bot'],
)

BOOKINGS_WITH_PHOTOS = Counter(
    'bot_bookings_with_photos_total',
    'Bookings created with at least one photo',
    ['bot'],
)

APPOINTMENT_PHOTOS = Counter(
    'bot_appointment_photos_total',
    'Total photos attached to bookings',
    ['bot'],
)

PHOTOS_PER_BOOKING = Histogram(
    'bot_appointment_photos_per_booking',
    'Distribution of photo count per booking',
    ['bot'],
    buckets=(0, 1, 2, 3, 4, 5, 10),
)

USERS_REGISTERED = Counter(
    'bot_users_registered_total',
    'Total new users registered',
    ['bot'],
)

SLOTS_CREATED = Counter(
    'bot_slots_created_total',
    'Total appointment slots created',
    ['bot'],
)

REMINDERS_SENT = Counter(
    'bot_reminders_sent_total',
    'Total appointment reminders delivered to clients',
    ['bot', 'kind'],
)

CHANNEL_UPDATES = Counter(
    'bot_channel_updates_total',
    'Total channel slot-board posts/edits',
    ['bot', 'action'],
)

APPOINTMENTS_PENDING = Gauge(
    'bot_appointments_pending',
    'Appointments currently awaiting master confirmation',
    ['bot'],
)

APPOINTMENTS_UPCOMING = Gauge(
    'bot_appointments_upcoming',
    'Confirmed upcoming appointments',
    ['bot'],
)

SLOTS_AVAILABLE = Gauge(
    'bot_slots_available',
    'Available future booking slots',
    ['bot'],
)


def record_booking_created(comment: str | None, photos: list | None) -> None:
    APPOINTMENTS_CREATED.labels(bot=BOT_NAME).inc()

    photo_count = len(photos) if photos else 0
    PHOTOS_PER_BOOKING.labels(bot=BOT_NAME).observe(photo_count)
    if photo_count:
        BOOKINGS_WITH_PHOTOS.labels(bot=BOT_NAME).inc()
        APPOINTMENT_PHOTOS.labels(bot=BOT_NAME).inc(photo_count)

    if comment and comment.strip():
        BOOKINGS_WITH_COMMENT.labels(bot=BOT_NAME).inc()


def refresh_business_gauges() -> None:
    from datetime import datetime

    from config import const
    from DB.tables.appointments import AppointmentsTable
    from DB.tables.slots import SlotsTable

    try:
        with AppointmentsTable() as app_db:
            APPOINTMENTS_PENDING.labels(bot=BOT_NAME).set(app_db.count_appointments(const.PENDING, only_future=True))
            APPOINTMENTS_UPCOMING.labels(bot=BOT_NAME).set(app_db.count_appointments(const.CONFIRMED, only_future=True))
        with SlotsTable() as slots_db:
            SLOTS_AVAILABLE.labels(bot=BOT_NAME).set(len(slots_db.get_available_slots(from_time=datetime.now())))
    except Exception:
        logger.exception('Failed to refresh business gauges')
