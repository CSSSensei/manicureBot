import calendar
from datetime import datetime, timedelta, date
from typing import Optional, List, Set, Tuple

from aiogram.types import InlineKeyboardButton as IButton
from aiogram.types import InlineKeyboardMarkup as IMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from DB.tables.appointments import AppointmentsTable
from DB.tables.services import ServicesTable
from DB.tables.slots import SlotsTable
from bot.bot_utils.models import BookingPageCallBack, ActionButtonCallBack, MonthCallBack, ServiceCallBack, SlotCallBack, BookingStatusCallBack, \
    PhotoAppCallBack
from DB.models import Pagination, AppointmentModel
from config.const import MONTHS, CANCELLED, REJECTED, CONFIRMED, CalendarMode, AppListMode, AppointmentPageAction
from phrases import PHRASES_RU


def booking_page_keyboard(appointment: AppointmentModel, pagination: Pagination, mode: AppListMode) -> Optional[IMarkup]:
    booking_keyboard = []
    if pagination.total_pages > 1:
        no_action = BookingPageCallBack().pack()

        past_button = IButton(
            text=PHRASES_RU.button.prev_page,
            callback_data=BookingPageCallBack(page=pagination.page - 1,
                                              mode=mode,
                                              app_id=appointment.appointment_id,
                                              app_date=appointment.slot.start_time.date()).pack()
        ) if pagination.has_prev else IButton(text=' ', callback_data=no_action)

        next_button = IButton(
            text=PHRASES_RU.button.next_page,
            callback_data=BookingPageCallBack(page=pagination.page + 1,
                                              mode=mode,
                                              app_id=appointment.appointment_id,
                                              app_date=appointment.slot.start_time.date()).pack()
        ) if pagination.has_next else IButton(text=' ', callback_data=no_action)
        booking_keyboard.append([
            past_button,
            IButton(text=f'{pagination.page}{PHRASES_RU.icon.page_separator}{pagination.total_pages}', callback_data=no_action),
            next_button
        ])
    if appointment.photos and len(appointment.photos) > 0:
        booking_keyboard.append([
            IButton(text=PHRASES_RU.button.photos, callback_data=PhotoAppCallBack(
                app_id=appointment.appointment_id
            ).pack())
        ])
    if appointment.status != CANCELLED and appointment.status != REJECTED:
        booking_keyboard.append([
            IButton(text=PHRASES_RU.button.cancel2, callback_data=BookingPageCallBack(
                page=pagination.page,
                action=AppointmentPageAction.SET_CANCELLED,
                app_id=appointment.appointment_id,
                app_date=appointment.slot.start_time.date(),
                mode=mode
            ).pack())
        ])
    if mode == AppListMode.MASTER:
        booking_keyboard.append([
            IButton(text=PHRASES_RU.button.back, callback_data=BookingPageCallBack(
                page=pagination.page,
                app_date=appointment.slot.start_time.date(),
                action=AppointmentPageAction.BACK_TO_MAP,
                mode=mode
            ).pack())
        ])

    return IMarkup(inline_keyboard=booking_keyboard)


def user_cancel_keyboard(appointment_id: int, page: int, mode: AppListMode, app_date: Optional[date]) -> Optional[IMarkup]:
    back_button = IButton(
        text=PHRASES_RU.button.back, callback_data=BookingPageCallBack(
            page=page,
            action=AppointmentPageAction.BACK,
            app_id=appointment_id,
            app_date=app_date,
            mode=mode).pack()
    )

    cancel_button = IButton(
        text=PHRASES_RU.button.cancel3,
        callback_data=BookingStatusCallBack(
            status=CANCELLED if mode == AppListMode.USER else REJECTED,
            app_id=appointment_id).pack()
    )
    keyboard = [[cancel_button], [back_button]]
    return IMarkup(inline_keyboard=keyboard)


def _base_keyboard(
        buttons: List[List[IButton]],
        *,
        cur_page: int,
        next_page: Optional[int] = None,
) -> IMarkup:
    """Базовая клавиатура с кнопками Назад/Далее/Отмена."""
    row = [IButton(
        text=PHRASES_RU.button.back,
        callback_data=ActionButtonCallBack(action=-1, current_page=cur_page).pack()
    )]
    if next_page == -1:
        row.append(IButton(
            text=PHRASES_RU.button.confirm,
            callback_data=ActionButtonCallBack(action=1, current_page=cur_page).pack()
        ))

    elif next_page is not None:
        row.append(IButton(
            text=PHRASES_RU.button.next,
            callback_data=ActionButtonCallBack(action=1, current_page=cur_page).pack()
        ))

    buttons.append(row)
    cancel_button = IButton(
        text=PHRASES_RU.button.cancel,
        callback_data=ActionButtonCallBack(action=0).pack()
    )
    if len(buttons[-1]) < 2:
        buttons[-1].append(cancel_button)
    else:
        buttons.append([cancel_button])
    return IMarkup(inline_keyboard=buttons)


def first_page_calendar(mode: CalendarMode = CalendarMode.BOOKING) -> Tuple[Optional[str], Optional[IMarkup]]:
    with SlotsTable() as slots_db:
        first_slot = slots_db.get_first_available_slot()
        if not first_slot:
            return None, None

        current_date = datetime.now()
        is_current_month = (first_slot.month == current_date.month and
                            first_slot.year == current_date.year)
        prev_enabled = not is_current_month

        return create_calendar_keyboard(first_slot.month, first_slot.year, prev_enabled, mode)


def create_calendar_keyboard(month: int, year: int, prev: bool, mode: CalendarMode = CalendarMode.BOOKING) -> Tuple[str, IMarkup]:
    now = datetime.now()
    today = now.date()
    month_days = calendar.monthrange(year, month)[1]

    if month == now.month and year == now.year:
        start_date = now
        end_date = datetime(year, month, month_days) + timedelta(days=1)
    else:
        start_date = datetime(year, month, 1)
        end_date = datetime(year, month, month_days) + timedelta(days=1)

    available_dates, slots_len = {}, 0

    match mode:
        case CalendarMode.BOOKING | CalendarMode.DELETE:
            available_dates, slots_len = _get_available_dates(start_date, end_date)
        case CalendarMode.APPOINTMENT_MAP:
            available_dates, slots_len = _get_appointment_dates(start_date, end_date)
    header_text = _generate_header_text(month, slots_len, mode)

    keyboard = _build_calendar_keyboard(
        month=month,
        year=year,
        prev_enabled=prev,
        available_dates=available_dates,
        today=today,
        mode=mode
    )
    if mode == CalendarMode.DELETE or mode == CalendarMode.APPOINTMENT_MAP:
        keyboard.inline_keyboard.append([IButton(text=PHRASES_RU.button.back, callback_data=PHRASES_RU.callback_data.master.cancel)])

    return header_text, keyboard


def _get_available_dates(start_date: datetime, end_date: datetime) -> Tuple[Set[date], int]:
    with SlotsTable() as slots_db:
        slots = slots_db.get_available_slots(start_date, end_date)
        return {s.start_time.date() for s in slots}, len(slots)


def _get_appointment_dates(start_date: datetime, end_date: datetime) -> Tuple[Set[date], int]:
    with AppointmentsTable() as db:
        booked_slots = db.get_booked_slot_dates(CONFIRMED, start_date, end_date)
        len_booked_slots = db.count_appointments_by_status_and_time(CONFIRMED, start_date, end_date)
        return booked_slots, len_booked_slots


def _generate_header_text(month: int, slots_count: int, mode: CalendarMode) -> str:
    match mode:
        case CalendarMode.BOOKING:
            if slots_count > 0:
                return (PHRASES_RU.replace('answer.available_slots', month=MONTHS[month], len_slots=slots_count) +
                        PHRASES_RU.answer.choose_date)
            return PHRASES_RU.replace('answer.no_available_slots', month=MONTHS[month].lower())

        case CalendarMode.DELETE:
            if slots_count > 0:
                return PHRASES_RU.replace('answer.master.choose_date_to_delete', month=MONTHS[month], len_slots=slots_count)
            return PHRASES_RU.replace('answer.master.no_available_slots', month=MONTHS[month])

        case CalendarMode.APPOINTMENT_MAP:
            if slots_count > 0:
                return PHRASES_RU.replace('answer.master.choose_appointment_date', month=MONTHS[month], len_slots=slots_count)
            return PHRASES_RU.replace('answer.master.no_appointments', month=MONTHS[month])

    return ""


def _build_calendar_keyboard(
        month: int,
        year: int,
        prev_enabled: bool,
        available_dates: Set[date],
        today: date,
        mode: CalendarMode
) -> IMarkup:
    navigation_buttons = _create_navigation_row(month, year, prev_enabled, mode)
    weekdays_row = _create_weekdays_row(mode)
    calendar_rows = _create_calendar_days_rows(
        month=month,
        year=year,
        available_dates=available_dates,
        today=today,
        mode=mode
    )

    all_buttons = [navigation_buttons, weekdays_row] + calendar_rows

    return IMarkup(inline_keyboard=all_buttons)


def _create_navigation_row(
        month: int,
        year: int,
        prev_enabled: bool,
        mode: CalendarMode
) -> List[IButton]:
    return [
        IButton(
            text=' ' if not prev_enabled else PHRASES_RU.button.prev_page,
            callback_data=MonthCallBack(
                day=-1, month=month, year=year,
                action=(0 if not prev_enabled else -1),
                mode=mode
            ).pack()
        ),
        IButton(
            text=f'{MONTHS[month]} {year}',
            callback_data=MonthCallBack(action=0, mode=mode).pack()
        ),
        IButton(
            text=PHRASES_RU.button.next_page,
            callback_data=MonthCallBack(
                month=month, year=year, action=1, mode=mode
            ).pack()
        )
    ]


def _create_weekdays_row(mode: CalendarMode) -> List[IButton]:
    return [
        IButton(
            text=day,
            callback_data=MonthCallBack(month=-1, mode=mode).pack()
        )
        for day in ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    ]


def _create_calendar_days_rows(
        month: int,
        year: int,
        available_dates: Set[date],
        today: date,
        mode: CalendarMode
) -> List[List[IButton]]:
    rows = []
    month_cal = calendar.monthcalendar(year, month)

    for week in month_cal:
        week_buttons = []
        for day in week:
            if day == 0:
                week_buttons.append(
                    IButton(text=' ', callback_data=MonthCallBack(day=-1, mode=mode).pack())
                )
                continue

            target_date = date(year, month, day)
            is_available = target_date in available_dates
            is_today = target_date == today

            btn_text = _get_day_button_text(day, is_today, is_available)
            callback = _get_day_callback_data(day, month, year, is_available, mode)

            week_buttons.append(IButton(text=btn_text, callback_data=callback))

        rows.append(week_buttons)

    return rows


def _get_day_button_text(day: int, is_today: bool, is_available: bool) -> str:
    if is_today and is_available:
        return f'· [{day}]'
    elif is_today:
        return f'[{day}]'
    elif is_available:
        return f'· {day}'
    return f'{day}'


def _get_day_callback_data(day: int, month: int, year: int, is_available: bool, mode: CalendarMode) -> str:
    return MonthCallBack(
        day=day if is_available else -1,
        month=month,
        year=year,
        action=0,
        mode=mode
    ).pack()


def service_keyboard() -> IMarkup:
    """Клавиатура с услугами."""
    builder = InlineKeyboardBuilder()
    with ServicesTable() as service_db:
        for service in service_db.get_active_services():
            builder.button(
                text=service.name,
                callback_data=ServiceCallBack(service_id=service.id).pack()
            )
    builder.adjust(2)  # 2 кнопки в ряд
    return _base_keyboard(
        builder.export(),  # type: ignore
        cur_page=2,
        next_page=None  # Нет кнопки "Далее"
    )


def slots_keyboard(cur_date: datetime.date) -> IMarkup:
    """Клавиатура со слотами времени."""
    builder = InlineKeyboardBuilder()
    with SlotsTable() as slots_db:
        for slot in slots_db.get_available_slots_by_day(cur_date):
            builder.button(
                text=str(slot),
                callback_data=SlotCallBack(slot_id=slot.id).pack()
            )
    builder.adjust(2)
    return _base_keyboard(
        builder.export(),  # type: ignore
        cur_page=1,
        next_page=None
    )


def photo_keyboard() -> IMarkup:
    """Клавиатура для загрузки фото."""
    return _base_keyboard(
        [],
        cur_page=3,
        next_page=4  # Переход к комментарию
    )


def comment_keyboard() -> IMarkup:
    """Клавиатура для комментария."""
    return _base_keyboard(
        [],
        cur_page=4,
        next_page=5  # Переход к подтверждению
    )


def confirm_keyboard() -> IMarkup:
    """Клавиатура подтверждения."""
    return _base_keyboard(
        [],
        cur_page=5,
        next_page=-1  # Нет кнопки "Далее" (финальный шаг)
    )
