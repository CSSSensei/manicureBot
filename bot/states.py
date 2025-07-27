from aiogram.fsm.state import StatesGroup, State


class AppointmentStates(StatesGroup):
    WAITING_FOR_DATE = State()
    WAITING_FOR_SLOT = State()
    WAITING_FOR_SERVICE = State()
    WAITING_FOR_PHOTOS = State()
    WAITING_FOR_COMMENT = State()
    WAITING_FOR_PHONE = State()
    CONFIRMATION = State()
    PENDING_MASTER_APPROVAL = State()
