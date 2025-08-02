import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

from DB.models import AppointmentModel, ServiceModel, SlotModel
from DB.tables.slots import SlotsTable
from config import const
from config.const import PENDING, CANCELLED, CONFIRMED, REJECTED, COMPLETED
from phrases import PHRASES_RU


def split_text(text, n):
    result = []
    lines = text.split('\n')
    current_chunk = ''
    current_length = 0

    for line in lines:
        if len(current_chunk) + len(line) + 1 <= n:  # Check if adding the line and '\n' fits in the chunk
            if current_chunk:  # Add '\n' if it's not the first line in the chunk
                current_chunk += '\n'
            current_chunk += line
            current_length += len(line) + 1
        else:
            result.append(current_chunk)
            current_chunk = line
            current_length = len(line)

    if current_chunk:
        result.append(current_chunk)

    return result


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


def parse_slots_text(text: str) -> List[Tuple[datetime, datetime]]:
    """
    Парсит текст в формате:
    "месяц
    число - время-время время-время
    число - время время"

    Возвращает список кортежей (start_datetime, end_datetime)
    Автоматически определяет год (текущий или следующий) в зависимости от месяца
    """
    now = datetime.now()
    current_year = now.year
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    if not lines:
        raise ValueError("Пустой текст")

    month_line = lines[0].lower()
    month_map = {
        'январь': 1, 'февраль': 2, 'март': 3, 'апрель': 4,
        'май': 5, 'июнь': 6, 'июль': 7, 'август': 8,
        'сентябрь': 9, 'октябрь': 10, 'ноябрь': 11, 'декабрь': 12
    }

    month = next((num for name, num in month_map.items() if name in month_line), None)
    if month is None:
        raise ValueError(f'Не удалось распознать месяц: {month_line}')

    year = current_year if month >= now.month else current_year + 1
    slots = []

    for line in lines[1:]:
        line = line.replace('—', '-')
        if '-' not in line:
            raise ValueError(f'Ожидался символ "-" в строке: {line}')

        try:
            day_part, times_part = line.split('-', 1)
            day = int(day_part.strip())
        except Exception:
            raise ValueError(f'Некорректный формат строки: {line}')

        time_parts = re.findall(r'\b\d{1,2}:\d{2}(?:-\d{1,2}:\d{2})?\b', times_part)
        if not time_parts:
            raise ValueError(f'Не найдено временных интервалов в строке: {line}')

        for time_str in time_parts:
            try:
                if '-' in time_str:
                    start_str, end_str = time_str.split('-')
                    start_time = datetime.strptime(start_str.strip(), '%H:%M').time()
                    end_time = datetime.strptime(end_str.strip(), '%H:%M').time()

                    start_datetime = datetime(year, month, day, start_time.hour, start_time.minute)

                    if end_time > start_time:
                        end_datetime = datetime(year, month, day, end_time.hour, end_time.minute)
                    else:
                        end_datetime = datetime(year, month, day, end_time.hour, end_time.minute) + timedelta(days=1)
                else:
                    start_time = datetime.strptime(time_str.strip(), '%H:%M').time()
                    start_datetime = datetime(year, month, day, start_time.hour, start_time.minute)
                    end_datetime = start_datetime + timedelta(hours=3)

                if start_datetime < now:
                    raise ValueError(f'Слот {start_datetime} уже прошел')

                slots.append((start_datetime, end_datetime))

            except ValueError as e:
                raise ValueError(f'Ошибка при разборе времени "{time_str}": {str(e)}')

    return slots


def slots_to_text(slots: List[SlotModel]) -> str:
    if not slots:
        return ""

    # Группируем слоты сначала по году-месяцу, затем по дню
    slots_by_month = defaultdict(lambda: defaultdict(list))
    for slot in slots:
        year_month = (slot.start_time.year, slot.start_time.month)
        day = slot.start_time.day
        slots_by_month[year_month][day].append(slot)

    # Сортируем месяцы по порядку
    sorted_months = sorted(slots_by_month.keys())

    result_lines = []

    for year, month in sorted_months:
        month_name = const.MONTHS[month].capitalize()
        result_lines.append(month_name)

        days_slots = slots_by_month[(year, month)]

        for day in sorted(days_slots.keys()):
            date_slots = days_slots[day]
            date_slots.sort(key=lambda x: x.start_time)

            slot_strings = []
            for slot in date_slots:
                duration = slot.end_time - slot.start_time
                if duration.total_seconds() == 3 * 3600:
                    # Если длительность ровно 3 часа, пишем только начало
                    slot_str = slot.start_time.strftime("%H:%M")
                else:
                    # Иначе пишем начало-конец
                    slot_str = f"{slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')}"
                slot_strings.append(slot_str)

            line = f"{day} - {' '.join(slot_strings)}"
            result_lines.append(line)

    return "\n".join(result_lines)


def parse_service_text(text: str) -> ServiceModel:
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not lines:
        raise ValueError("Пустой запрос")

    service = ServiceModel(name=lines[0])
    seen_keys = set()

    for line in lines[1:]:
        if ':' not in line:
            raise ValueError(f"Некорректный формат строки: {line}")

        key, value = line[:2], line[2:].strip()
        if key in seen_keys:
            raise ValueError(f"Поле {key} указано более одного раза")
        seen_keys.add(key)

        if key == 'о:':
            service.description = value
        elif key == 'с:':
            if not value.isdigit():
                raise ValueError("Стоимость должна быть числом")
            service.price = int(value)
        elif key == 'д:':
            if not value.isdigit():
                raise ValueError("Длительность должна быть числом (в минутах)")
            service.duration = timedelta(minutes=int(value))
        else:
            raise ValueError(f"Неизвестный префикс: {key}")

    return service


if __name__ == '__main__':
    with SlotsTable() as slots_db:
        slots = slots_db.get_available_slots(datetime(2024, 1, 1), datetime(2027, 1, 1))
        print(slots_to_text(slots))
