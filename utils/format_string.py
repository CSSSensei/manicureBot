from typing import Optional

from DB.models import AppointmentModel
from config.const import PENDING, CANCELLED, CONFIRMED, REJECTED, COMPLETED
from phrases import PHRASES_RU


def clear_string(text: str):
    if not text:
        return PHRASES_RU.icon.not_text
    return text.replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')


def get_query_count_emoji(count: int) -> str:
    for emoji, threshold in PHRASES_RU.icon.query.thresholds.__dict__.items():
        if count > threshold:
            return emoji
    return PHRASES_RU.icon.query.default


def get_status_app_string(status: str) -> str:
    if status == PENDING:
        return PHRASES_RU.answer.status.pending
    elif status == CONFIRMED:
        return PHRASES_RU.answer.status.confirmed
    elif status == COMPLETED:
        return PHRASES_RU.answer.status.completed
    elif status == CANCELLED:
        return PHRASES_RU.answer.status.cancelled
    elif status == REJECTED:
        return PHRASES_RU.answer.status.rejected
    return ''


def user_booking_text(data: AppointmentModel, header: Optional[str] = PHRASES_RU.title.new_booking) -> str:
    text = header
    text += PHRASES_RU.replace('template.user.slot', date=data.formatted_date,
                               datetime=data.slot_str) if data.slot else ''
    if data.service and data.service.name:
        text += PHRASES_RU.replace('template.user.service', service=data.service.name)
    if data.photos and len(data.photos) > 0:
        text += PHRASES_RU.replace('template.user.photos', len_photos=len(data.photos))
    if data.comment:
        text += PHRASES_RU.replace('template.user.text', text=data.comment)
    text += '\n'
    return text


def user_sent_booking(data: AppointmentModel, header: str) -> str:
    text = user_booking_text(data, header)
    if data.status:
        text += '\n' + get_status_app_string(data.status)
    return text


def master_sent_booking(data: AppointmentModel, header: str) -> str:
    text = user_booking_text(data, header)
    return text


def master_booking_text(data: AppointmentModel, total_items: int = 1) -> str:
    text = PHRASES_RU.title.admin_new_booking + PHRASES_RU.replace('footnote.total', total=total_items)
    if data.client and data.client.username:
        text += PHRASES_RU.replace('template.master.client_username', username=data.client.username)
    else:
        text += PHRASES_RU.replace('template.master.client_no_username', contact=data.client.contact)
    text += PHRASES_RU.replace('template.master.slot', date=data.formatted_date,
                               datetime=data.slot_str) if data.slot else ''
    if data.service and data.service.name:
        text += PHRASES_RU.replace('template.master.service', service=data.service.name)
    if data.comment:
        text += PHRASES_RU.replace('template.master.text', text=data.comment)
    text += '\n'
    return text
