from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
USERS_PER_PAGE = 15
ACTIONS_PER_PAGE = 5
QUERIES_PER_PAGE = 6

MONTHS = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}

PENDING = 'pending'
CONFIRMED = 'confirmed'
COMPLETED = 'completed'
CANCELLED = 'cancelled'
REJECTED = 'rejected'
BACK = 'back'
