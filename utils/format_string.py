from bot.models import Appointment
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


def user_booking_text(data: Appointment) -> str:
    text = (PHRASES_RU.title.booking +
            PHRASES_RU.replace('template.user.slot', date=data.formatted_date,
                               datetime=data.slot_str)) if data.slot_date and data.slot_str else ''
    if data.service_str:
        text += PHRASES_RU.replace('template.user.service', service=data.service_str)
    if data.photos and len(data.photos) > 0:
        text += PHRASES_RU.replace('template.user.photos', len_photos=len(data.photos))
    if data.text:
        text += PHRASES_RU.replace('template.user.text', text=data.text)
    text += '\n'
    return text


def master_booking_text(data: Appointment) -> str:
    text = PHRASES_RU.title.admin_new_booking
    if data.client_username:
        text += PHRASES_RU.replace('template.master.client_username', username=data.client_username)
    else:
        text += PHRASES_RU.replace('template.master.client_no_username', contact=data.client_contact)
    text += PHRASES_RU.replace('template.master.slot', date=data.formatted_date,
                               datetime=data.slot_str) if data.slot_date and data.slot_str else ''
    if data.service_str:
        text += PHRASES_RU.replace('template.master.service', service=data.service_str)
    if data.text:
        text += PHRASES_RU.replace('template.master.text', text=data.text)
    text += '\n'
    return text
