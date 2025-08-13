from aiogram.fsm.state import StatesGroup, State


class AppointmentStates(StatesGroup):
    WAITING_FOR_DATE = State()
    WAITING_FOR_SLOT = State()
    WAITING_FOR_SERVICE = State()
    WAITING_FOR_PHOTOS = State()
    WAITING_FOR_COMMENT = State()
    CONFIRMATION = State()


class MasterStates(StatesGroup):
    WAITING_FOR_SLOT = State()
    WAITING_FOR_NEW_SERVICE = State()
    WAITING_FOR_EDIT_SERVICE = State()
