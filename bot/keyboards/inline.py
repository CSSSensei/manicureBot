from typing import Union, List, Set, Optional
from aiogram.types import InlineKeyboardButton as IButton
from aiogram.types import InlineKeyboardMarkup as IMarkup
import datetime
import calendar

from aiogram.utils.keyboard import InlineKeyboardBuilder

from DB.models import Pagination
from DB.tables.services import ServicesTable
from DB.tables.slots import SlotsTable
from config.const import MONTHS
from phrases import PHRASES_RU
from bot.utils.models import PageCallBack, MonthCallBack, ServiceCallBack, ActionButtonCallBack, SlotCallBack


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


def page_keyboard(action: int, pagination: Pagination, user_id: int = 0) -> Union[IMarkup, None]:
    if pagination.total_pages <= 1:
        return None

    no_action = PageCallBack(action=-1).pack()

    past_button = IButton(
        text=PHRASES_RU.button.prev_page,
        callback_data=PageCallBack(action=action, page=pagination.page - 1, user_id=user_id).pack()
    ) if pagination.page > 1 else IButton(text=' ', callback_data=no_action)

    next_button = IButton(
        text=PHRASES_RU.button.next_page,
        callback_data=PageCallBack(action=action, page=pagination.page + 1, user_id=user_id).pack()
    ) if pagination.page < pagination.total_pages else IButton(text=' ', callback_data=no_action)

    return IMarkup(inline_keyboard=[[
        past_button,
        IButton(text=f'{pagination.page}{PHRASES_RU.icon.page_separator}{pagination.total_pages}', callback_data=no_action),
        next_button
    ]])


def month_keyboard(m: int, y: int, prev: bool) -> IMarkup:
    """Создает календарную клавиатуру с активными днями, где есть свободные слоты"""

    now = datetime.datetime.now()
    today = now.date()

    if m == now.month and y == now.year:
        start_date = now
        end_date = datetime.datetime(y, m, calendar.monthrange(y, m)[1]) + datetime.timedelta(days=1)
    else:
        start_date = datetime.datetime(y, m, 1)
        end_date = datetime.datetime(y, m, calendar.monthrange(y, m)[1]) + datetime.timedelta(days=1)

    with SlotsTable() as slots_db:
        slots = slots_db.get_available_slots(start_date, end_date)

        available_dates: Set[datetime.date] = set()
        for slot in slots:
            slot_date = slot.start_time.date()
            if slot_date >= today:
                available_dates.add(slot_date)

        array_buttons: List[List[IButton]] = [
            [
                IButton(
                    text=' ' if not prev else PHRASES_RU.button.prev_page,
                    callback_data=MonthCallBack(day=-1, month=m, year=y, action=(0 if not prev else -1)).pack()
                ),
                IButton(
                    text=f'{MONTHS[m]} {y}',
                    callback_data=MonthCallBack(action=0).pack()
                ),
                IButton(
                    text=PHRASES_RU.button.next_page,
                    callback_data=MonthCallBack(month=m, year=y, action=1).pack()
                )
            ]
        ]

        week_days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        array_buttons.append([
            IButton(text=day, callback_data=MonthCallBack(month=-1).pack())
            for day in week_days
        ])

        cal = calendar.monthcalendar(y, m)
        for week in cal:
            week_buttons = []
            for day in week:
                if day == 0:
                    week_buttons.append(IButton(text=' ', callback_data=MonthCallBack(day=-1).pack()))
                    continue

                target_date = datetime.date(y, m, day)
                is_available = target_date in available_dates
                is_today = target_date == today

                if is_available:
                    text = f'[{day}]' if is_today else str(day)
                    callback = MonthCallBack(day=day, month=m, year=y, action=0).pack()
                else:
                    text = ' '
                    callback = MonthCallBack(day=-1, month=m, year=y, action=0).pack()

                week_buttons.append(IButton(
                    text=text,
                    callback_data=callback
                ))
            array_buttons.append(week_buttons)

        return IMarkup(inline_keyboard=array_buttons)


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


def slots_keyboard(date: datetime.date) -> IMarkup:
    """Клавиатура со слотами времени."""
    builder = InlineKeyboardBuilder()
    with SlotsTable() as slots_db:
        for slot in slots_db.get_available_slots_by_day(date):
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
