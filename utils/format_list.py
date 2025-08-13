from datetime import time, date, timedelta, datetime
from typing import List, Optional
from DB.models import UserModel, QueryModel, AppointmentModel, SlotModel, ClientWithStats
from phrases import PHRASES_RU
from DB.models import Pagination
from utils import format_string
from utils.format_string import get_status_app_string


def format_user_list(users_info: List[UserModel], pagination: Pagination) -> str:
    txt = [PHRASES_RU.title.users,
           PHRASES_RU.replace('footnote.total', total=pagination.total_items)]

    for user in users_info:
        line_data = {
            'username': user.username or user.first_name or PHRASES_RU.icon.not_username,
            'user_id': str(user.user_id).ljust(12),
            'query_stat': f'{format_string.get_query_count_emoji(user.query_count)} {user.query_count}',
            'registration_date': user.registration_date.strftime('%d.%m.%Y'),
        }

        user_line = PHRASES_RU.replace('template.user_str', **line_data)

        if user.is_banned:
            txt.append(f'<s>{user_line}</s>')
        elif user.is_admin:
            txt.append(f'<b>{user_line}</b>')
        else:
            txt.append(user_line)

    if pagination.total_pages > 1:
        txt.append(PHRASES_RU.icon.row_placeholder * (pagination.per_page - len(users_info)))

    return ''.join(txt)


def format_queries_text(
        queries: List[QueryModel],
        username: Optional[str] = None,
        user_id: Optional[int] = None,
        footnote_template: str = PHRASES_RU.footnote.user_query,
        line_template: str = PHRASES_RU.template.user_query,
        show_username: bool = False
) -> str:
    """
    Форматирует список запросов в текстовое сообщение.

    Args:
        queries: Список объектов QueryModel
        username: Имя пользователя (если есть)
        user_id: ID пользователя (если username отсутствует)
        footnote_template: Шаблон заголовка с {username} placeholder
        line_template: Шаблон строки запроса с {time} и {query} placeholders
        show_username: Показывать ли имя пользователя в каждой строке

    Returns:
        Отформатированная строка с историей запросов
    """
    username_display = username or user_id or PHRASES_RU.error.unknown
    txt = [PHRASES_RU.title.query,
           footnote_template.format(username=username_display, user_id=user_id)]

    for query in queries:
        line_data = {
            'user_id': query.user.user_id,
            'time': query.query_date.strftime('%d.%m.%Y %H:%M:%S') if query.query_date else PHRASES_RU.error.unknown,
            'query': query.query_text,
            'username': query.user.username if show_username and query.user and (query.user.username or query.user.first_name) else ''
        }
        txt.append(line_template.format(**line_data))

    return ''.join(txt)


def format_client_list(clients_info: List[ClientWithStats], pagination: Pagination) -> str:
    txt = [PHRASES_RU.title.clients,
           PHRASES_RU.replace('footnote.total', total=pagination.total_items)]

    for client in clients_info:
        line_data = {
            'username': client.user.username or client.user.first_name or PHRASES_RU.icon.not_username,
            'user_id': str(client.user.user_id).ljust(12),
            'total_apps': client.stats.total,
            'cancelled_apps': client.stats.cancelled,
            'completed_apps': client.stats.completed,
            'pending_apps': f' ⏳ {client.stats.pending}' if client.stats.pending != 0 else ''
        }

        user_line = PHRASES_RU.replace('template.client_str', **line_data)

        if client.user.is_banned:
            txt.append(f'<s>{user_line}</s>')
        else:
            txt.append(user_line)

    if pagination.total_pages > 1:
        txt.append(PHRASES_RU.icon.row_placeholder * (pagination.per_page - len(clients_info)))

    return ''.join(txt)


def format_app_actions(appointments: List[AppointmentModel], pagination: Pagination) -> str:
    txt = [PHRASES_RU.title.actions,
           PHRASES_RU.replace('footnote.total', total=pagination.total_items)]

    for app in appointments:
        slot_time = PHRASES_RU.error.unknown
        slot_date = PHRASES_RU.error.unknown
        status = get_status_app_string(app.status)
        username = ''
        if app.slot:
            slot_time = str(app.slot)
            slot_date = app.formatted_date
        if app.client:
            username = app.client.username or app.client.first_name or username
        line_data = {
            'time': app.updated_at.strftime('%d.%m.%Y %H:%M:%S') if app.updated_at else PHRASES_RU.error.unknown,
            'slot_date': slot_date,
            'slot_time': slot_time,
            'status': status,
            'username': username,
            'user_id': app.client.user_id
        }

        app_line = PHRASES_RU.replace('template.master.appointment_str', **line_data) + '\n'
        txt.append(app_line)

    return ''.join(txt)


def generate_slots_for_month(month: int, year: int) -> List[SlotModel]:
    time_slots = [
        (time(11, 0), time(14, 0)),
        (time(14, 30), time(17, 30)),
        (time(18, 0), time(21, 0))
    ]

    added_slots = []
    today = datetime.now().date()

    first_day = date(year, month, 1)

    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)

    # Если передан текущий месяц, начинаем со следующего дня
    start_day = today + timedelta(days=1) if (today.year == year and today.month == month) else first_day

    current_day = start_day
    while current_day <= last_day:
        # вторник - 1, суббота - 5
        if current_day.weekday() not in [1, 5]:
            for slot in time_slots:
                start_datetime = datetime.combine(current_day, slot[0])
                end_datetime = datetime.combine(current_day, slot[1])
                added_slots.append(SlotModel(
                    start_time=start_datetime,
                    end_time=end_datetime,
                    is_available=True
                ))
        current_day += timedelta(days=1)

    return added_slots
