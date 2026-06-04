import re
from collections import defaultdict
from datetime import datetime, time, timedelta

from config import const
from config.const import CANCELLED, COMPLETED, CONFIRMED, PENDING, REJECTED
from DB.models import AppointmentModel, ServiceModel, SlotModel, format_date
from DB.tables.day_schedule import DayScheduleTable
from DB.tables.services import ServicesTable
from DB.tables.slots import SlotsTable
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
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def get_query_count_emoji(count: int) -> str:
    for emoji, threshold in PHRASES_RU.icon.query.thresholds.__dict__.items():
        if count > threshold:
            return emoji
    return PHRASES_RU.icon.query.default


def bold_numbers(number):
    return ''.join(const.BOLD_DIGITS.get(char, char) for char in str(number))


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


def user_booking_text(data: AppointmentModel, header: str | None = PHRASES_RU.title.new_booking) -> str:
    text = header
    if data.service and data.service.name:
        text += PHRASES_RU.replace('template.user.service', service=data.service.name)
    if data.slot_date or data.slot:
        date = data.slot.formatted_date if data.slot else format_date(datetime.combine(data.slot_date, time.min))
        text += PHRASES_RU.replace('template.user.date', date=date)
    if data.slot:
        text += PHRASES_RU.replace('template.user.slot', datetime=data.slot_str)
    if data.photos and len(data.photos) > 0:
        text += PHRASES_RU.replace('template.user.photos', len_photos=len(data.photos))
    if data.comment:
        text += PHRASES_RU.replace('template.user.text', text=data.comment)
    text += '\n'
    return text


def user_sent_booking(data: AppointmentModel, header: str) -> str:
    text = user_booking_text(data, header)
    if data.status:
        text += get_status_app_string(data.status)
    return text


def master_sent_booking(data: AppointmentModel, header: str) -> str:
    text = header
    if data.client:
        text += PHRASES_RU.replace(
            'template.master.client_username',
            user_id=data.client.user_id,
            username=f'@{data.client.username}'
            if data.client.username
            else data.client.first_name or PHRASES_RU.error.no_username,
        )
    text += (
        PHRASES_RU.replace('template.master.slot', date=data.formatted_date, datetime=data.slot_str)
        if data.slot
        else ''
    )
    if data.service and data.service.name:
        text += PHRASES_RU.replace('template.user.service', service=data.service.name)
    if data.photos and len(data.photos) > 0:
        text += PHRASES_RU.replace('template.user.photos', len_photos=len(data.photos))
    if data.comment:
        text += PHRASES_RU.replace('template.user.text', text=data.comment)
    text += '\n'
    return text


def master_reviewed_appointment(data: AppointmentModel):
    text = master_sent_booking(data, PHRASES_RU.title.booking)
    if data.status:
        text += get_status_app_string(data.status)
    return text


def master_booking_text(data: AppointmentModel, total_items: int = 1) -> str:
    text = PHRASES_RU.title.admin_new_booking + PHRASES_RU.replace('footnote.total', total=total_items)
    if data.client:
        text += PHRASES_RU.replace(
            'template.master.client_username',
            user_id=data.client.user_id,
            username=f'@{data.client.username}'
            if data.client.username
            else data.client.first_name or PHRASES_RU.error.no_username,
        )
    text += (
        PHRASES_RU.replace('template.master.slot', date=data.formatted_date, datetime=data.slot_str)
        if data.slot
        else ''
    )
    if data.service and data.service.name:
        text += PHRASES_RU.replace('template.master.service', service=data.service.name)
    if data.comment:
        text += PHRASES_RU.replace('template.master.text', text=data.comment)
    text += '\n'
    return text


def parse_slots_text(text: str) -> list[tuple[datetime, datetime]]:
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
        raise ValueError('Пустой текст')

    month_line = lines[0].lower()
    month_map = {
        'январь': 1,
        'февраль': 2,
        'март': 3,
        'апрель': 4,
        'май': 5,
        'июнь': 6,
        'июль': 7,
        'август': 8,
        'сентябрь': 9,
        'октябрь': 10,
        'ноябрь': 11,
        'декабрь': 12,
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
        except Exception as err:
            raise ValueError(f'Некорректный формат строки: {line}') from err

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

            except ValueError as err:
                raise ValueError(f'Ошибка при разборе времени "{time_str}": {err}') from err

    return slots


def slots_to_text(slots: list[SlotModel]) -> str:
    if not slots:
        return ''

    slots_by_month = defaultdict(lambda: defaultdict(list))
    for slot in slots:
        year_month = (slot.start_time.year, slot.start_time.month)
        day = slot.start_time.day
        slots_by_month[year_month][day].append(slot)

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
                slot_strings.append(slot.start_time.strftime('%H:%M'))

            line = f'{day} — {" ".join(slot_strings)}'
            result_lines.append(line)

    return '\n'.join(result_lines)


def parse_service_text(text: str, service_id: int | None = None) -> ServiceModel:
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not lines:
        raise ValueError('Пустой запрос')

    service_name = lines[0].strip()

    with ServicesTable() as db:
        if db.service_name_exists(service_name, service_id):
            raise ValueError(f"Услуга с названием '{service_name}' уже существует")

    service = ServiceModel(name=service_name)
    seen_keys = set()

    for line in lines[1:]:
        if ':' not in line:
            raise ValueError(f'Некорректный формат строки: {line}')

        key, value = line[:2], line[2:].strip()
        if key in seen_keys:
            raise ValueError(f'Поле {key} указано более одного раза')
        seen_keys.add(key)

        if key == 'о:':
            service.description = value
        elif key == 'с:':
            if not value.isdigit():
                raise ValueError('Стоимость должна быть числом')
            service.price = int(value)
        elif key == 'д:':
            if not value.isdigit():
                raise ValueError('Длительность должна быть числом (в минутах)')
            service.duration = int(value)
        else:
            raise ValueError(f'Неизвестный префикс: {key}')

    return service


def service_text(service: ServiceModel):
    text = f'Название: <u>{service.name}</u>\n'
    if service.price:
        text += f'Цена: <i>{service.price} ₽</i>\n'
    if service.duration:
        text += f'Приблизительная длительность: <i>{service.duration} мин</i>\n'
    if service.description:
        text += f'Описание: <i>{service.description}</i>\n'
    return text


def parse_schedule_message(text: str) -> dict[int, list[tuple[time, time]]]:
    """
    Парсит сообщение мастера в формате:
    "пн - 10:00
    вт - 11:00 18:00
    ср - выходной
    чт - 10:00-14:00"

    Возвращает словарь:
    {
        0: [(time(10,0), time(13,0))],
        1: [(time(11,0), time(14,0)), (time(18,0), time(21,0))],
        2: [],  # выходной
        3: [(time(10,0), time(14,0))],
        ...
    }
    """
    day_mapping = {
        'пн': 0,
        'понедельник': 0,
        'вт': 1,
        'вторник': 1,
        'ср': 2,
        'среда': 2,
        'чт': 3,
        'четверг': 3,
        'пт': 4,
        'пятница': 4,
        'сб': 5,
        'суббота': 5,
        'вс': 6,
        'воскресенье': 6,
    }

    result: dict[int, list[tuple[time, time]]] = {i: [] for i in range(7)}

    lines = text.strip().replace('—', '-').split('\n')
    for line in lines:
        line = line.strip()
        if not line or '-' not in line:
            continue

        day_part, slots_part = line.split('-', 1)
        day_key = day_part.strip().lower()

        if day_key not in day_mapping:
            continue

        weekday = day_mapping[day_key]
        slots_text = slots_part.strip().lower()

        if 'выходной' in slots_text or 'отдых' in slots_text:
            result[weekday] = []
            continue

        slots: list[tuple[time, time]] = []
        for token in slots_text.split():
            if '-' in token:
                # интервал времени
                start_str, end_str = token.split('-', 1)
                try:
                    start = time.fromisoformat(start_str)
                    end = time.fromisoformat(end_str)
                    slots.append((start, end))
                except ValueError:
                    continue
            else:
                # одиночное время = слот на 3 часа
                try:
                    start = time.fromisoformat(token)
                    dt = datetime.combine(datetime.today(), start) + timedelta(hours=3)
                    end = dt.time()
                    slots.append((start, end))
                except ValueError:
                    continue

        result[weekday] = slots

    return result


def show_current_schedule() -> str:
    with DayScheduleTable() as db:
        schedules = db.get_all_schedules()

    weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    response = '<b>📅 Текущее расписание:</b>\n'

    for i, day_name in enumerate(weekdays):
        schedule = schedules.get(i)
        if schedule and schedule.is_working:
            times = ' '.join(start.strftime('%H:%M') for start, _ in schedule.time_slots)
            response += f'{day_name} — {times}\n'
        else:
            response += f'{day_name} — выходной\n'

    return response


if __name__ == '__main__':
    with SlotsTable() as slots_db:
        slots_from_db = slots_db.get_available_slots(datetime(2024, 1, 1), datetime(2027, 1, 1))
        print(slots_to_text(slots_from_db))
