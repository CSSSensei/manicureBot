from datetime import datetime, date
from typing import Optional
from aiogram.types import InlineKeyboardButton as IButton
from aiogram.types import InlineKeyboardMarkup as IMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from DB.models import Pagination, ServiceModel, SlotModel
from DB.tables.services import ServicesTable
from DB.tables.slots import SlotsTable
from bot.bot_utils.models import MasterButtonCallBack, AddSlotsMonthCallBack, MasterServiceCallBack, EditServiceCallBack, \
    DeleteSlotCallBack, MonthCallBack
from bot.keyboards.admin import inline as admin_ikb
from config import const
from config.const import CalendarMode, PageListSection
from phrases import PHRASES_RU


def action_master_keyboard(appointment_id: int, msg_to_delete: Optional[str] = None) -> IMarkup:
    keyboard = [[
        IButton(
            text=PHRASES_RU.button.admin.reject,
            callback_data=MasterButtonCallBack(status=const.REJECTED,
                                               appointment_id=appointment_id,
                                               msg_to_delete=msg_to_delete).pack()),
        IButton(
            text=PHRASES_RU.button.admin.confirm,
            callback_data=MasterButtonCallBack(status=const.CONFIRMED,
                                               appointment_id=appointment_id,
                                               msg_to_delete=msg_to_delete).pack())
    ]]
    return IMarkup(inline_keyboard=keyboard)


def menu_master_keyboard() -> IMarkup:
    keyboard = [
        [
            IButton(text=PHRASES_RU.button.master.appointment_map, callback_data=PHRASES_RU.callback_data.master.appointment_map),
            IButton(text=PHRASES_RU.button.master.clients, callback_data=PHRASES_RU.callback_data.master.clients)],  # TODO сделать кнопку клиентов
        [
            IButton(text=PHRASES_RU.button.master.delete_slots, callback_data=PHRASES_RU.callback_data.master.delete_slots),
            IButton(text=PHRASES_RU.button.master.add_slots, callback_data=PHRASES_RU.callback_data.master.add_slots)
        ],
        [
            IButton(text=PHRASES_RU.button.master.history, callback_data=PHRASES_RU.callback_data.master.history),
            IButton(text=PHRASES_RU.button.master.service_editor, callback_data=PHRASES_RU.callback_data.master.service_editor)
        ]
    ]
    return IMarkup(inline_keyboard=keyboard)


def back_to_service_menu() -> IMarkup:
    keyboard = [[IButton(text=PHRASES_RU.button.back, callback_data=PHRASES_RU.callback_data.master.back_to_service_menu)]]
    return IMarkup(inline_keyboard=keyboard)


def back_to_adding() -> IMarkup:
    keyboard = [[IButton(text=PHRASES_RU.button.back, callback_data=PHRASES_RU.callback_data.master.back_to_adding_slots)]]
    return IMarkup(inline_keyboard=keyboard)


def add_slots_menu() -> IMarkup:
    now = datetime.now()
    current_month = now.month
    current_year = now.year

    next_month = current_month + 1 if current_month < 12 else 1
    next_year = current_year + 1 if current_month == 12 else current_year

    keyboard = [
        [
            IButton(
                text=f'на {const.MONTHS[current_month].lower()}',
                callback_data=AddSlotsMonthCallBack(month=current_month, year=current_year).pack()),
            IButton(
                text=f'на {const.MONTHS[next_month].lower()}',
                callback_data=AddSlotsMonthCallBack(month=next_month, year=next_year).pack())
        ],
        [
            IButton(text=PHRASES_RU.button.master.add_manual_slots, callback_data=PHRASES_RU.callback_data.master.add_manual_slots)
        ],
        [
            IButton(text=PHRASES_RU.button.back, callback_data=PHRASES_RU.callback_data.master.cancel)
        ]
    ]
    return IMarkup(inline_keyboard=keyboard)


def master_confirm_adding_slot(month: Optional[int] = None, year: Optional[int] = None) -> IMarkup:
    keyboard = [
        [IButton(text=PHRASES_RU.button.cancel,
                 callback_data=PHRASES_RU.callback_data.master.back_to_adding_slots)],
        [IButton(text=PHRASES_RU.button.confirm,
                 callback_data=AddSlotsMonthCallBack(action='add', month=month, year=year).pack() if month and year else
                 PHRASES_RU.callback_data.master.confirm_add_slot)]
    ]
    return IMarkup(inline_keyboard=keyboard)


def master_confirm_adding_service() -> IMarkup:
    keyboard = [
        [IButton(text=PHRASES_RU.button.cancel,
                 callback_data=PHRASES_RU.callback_data.master.back_to_service_menu)],
        [IButton(text=PHRASES_RU.button.confirm,
                 callback_data=PHRASES_RU.callback_data.master.confirm_add_service)]
    ]
    return IMarkup(inline_keyboard=keyboard)


def master_confirm_edit_service(service_id: int) -> IMarkup:
    keyboard = [
        [IButton(text=PHRASES_RU.button.back,
                 callback_data=MasterServiceCallBack(service_id=service_id).pack())],
        [IButton(text=PHRASES_RU.button.confirm,
                 callback_data=PHRASES_RU.callback_data.master.confirm_edit_service)]
    ]
    return IMarkup(inline_keyboard=keyboard)


def master_service_menu() -> IMarkup:
    keyboard = [
        [IButton(text=PHRASES_RU.button.master.edit_service, callback_data=PHRASES_RU.callback_data.master.edit_service),
         IButton(text=PHRASES_RU.button.master.add_service, callback_data=PHRASES_RU.callback_data.master.add_service)],
        [IButton(text=PHRASES_RU.button.back, callback_data=PHRASES_RU.callback_data.master.cancel)]
    ]
    return IMarkup(inline_keyboard=keyboard)


def master_page_keyboard(type_of_event: PageListSection, pagination: Pagination) -> IMarkup:
    reply_markup = admin_ikb.page_keyboard(type_of_event=type_of_event, pagination=pagination)
    back_button = IButton(
        text=PHRASES_RU.button.back,
        callback_data=PHRASES_RU.callback_data.master.cancel)
    if reply_markup:
        reply_markup.inline_keyboard.append([back_button])
    else:
        reply_markup = IMarkup(inline_keyboard=[[back_button]])
    return reply_markup


def master_service_editor() -> IMarkup:
    with ServicesTable() as db:
        services = db.get_all_services()

        builder = InlineKeyboardBuilder()
        for service in services:
            is_active = '🟢' if service.is_active else '🔴'
            builder.button(
                text=f'{is_active} {service.name}',
                callback_data=MasterServiceCallBack(service_id=service.id).pack()
            )

        # кнопки услуг (по 2 в ряд)
        builder.adjust(2)
        # кнопка "Назад" в отдельный ряд
        builder.row(
            IButton(
                text=PHRASES_RU.button.back,
                callback_data=PHRASES_RU.callback_data.master.back_to_service_menu
            )
        )

        return builder.as_markup()


def edit_current_service(service: ServiceModel) -> IMarkup:
    active_str = PHRASES_RU.button.master.deactivate if service.is_active else PHRASES_RU.button.master.activate
    action = const.Action.set_inactive if service.is_active else const.Action.set_active
    keyboard = [
        [IButton(text=active_str,
                 callback_data=MasterServiceCallBack(service_id=service.id, action=action).pack())],
        [IButton(text=PHRASES_RU.button.master.edit,
                 callback_data=EditServiceCallBack(service_id=service.id).pack())],

        [IButton(text=PHRASES_RU.button.back,
                 callback_data=PHRASES_RU.callback_data.master.edit_service)]
    ]
    return IMarkup(inline_keyboard=keyboard)


def back_to_edit_service(service_id: int) -> IMarkup:
    keyboard = [[IButton(text=PHRASES_RU.button.back,
                         callback_data=MasterServiceCallBack(service_id=service_id).pack())]]
    return IMarkup(inline_keyboard=keyboard)


def delete_slots_menu(cur_date: datetime.date) -> IMarkup:
    builder = InlineKeyboardBuilder()
    with SlotsTable() as slots_db:
        available_slots = slots_db.get_available_slots_by_day(cur_date)
        for slot in available_slots:
            builder.button(
                text=str(slot),
                callback_data=DeleteSlotCallBack(slot_id=slot.id,
                                                 slot_date=slot.start_time.date(),
                                                 action=const.Action.check_slot_to_delete).pack())
        if len(available_slots) > 0:
            builder.button(
                text=PHRASES_RU.button.master.delete_all_slots,
                callback_data=DeleteSlotCallBack(slot_id=None,
                                                 slot_date=slot.start_time.date(),
                                                 action=const.Action.check_slot_to_delete).pack())
    builder.adjust(1)
    builder.row(
        IButton(
            text=PHRASES_RU.button.back,
            callback_data=DeleteSlotCallBack(slot_date=cur_date).pack()
        )
    )
    return builder.as_markup()


def slot_deletion(slot: Optional[SlotModel], slot_date: date) -> IMarkup:
    keyboard = [
        [IButton(text=PHRASES_RU.button.delete,
                 callback_data=DeleteSlotCallBack(slot_id=slot.id if slot else None,
                                                  slot_date=slot_date,
                                                  action=const.Action.delete_slot).pack())],
        [IButton(
            text=PHRASES_RU.button.master.do_not_delete,
            callback_data=MonthCallBack(
                day=slot_date.day,
                month=slot_date.month,
                year=slot_date.year,
                action=0,
                mode=CalendarMode.DELETE
            ).pack())]
    ]
    return IMarkup(inline_keyboard=keyboard)
