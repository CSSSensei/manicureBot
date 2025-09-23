import json
from datetime import time
from typing import Dict, List, Optional, Tuple

from DB.models import DaySchedule
from DB.tables.base import BaseTable


class DayScheduleTable(BaseTable):
    __tablename__ = 'day_schedule'

    def create_table(self):
        self.cursor.executescript(f"""
        CREATE TABLE IF NOT EXISTS {self.__tablename__} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weekday INTEGER NOT NULL UNIQUE,
            time_slots TEXT NOT NULL, -- JSON: [[start, end], [start, end], ...]
            is_working BOOLEAN DEFAULT TRUE
        );
        """)
        self.conn.commit()

        self.cursor.execute(f"SELECT COUNT(*) FROM {self.__tablename__}")
        count = self.cursor.fetchone()[0]

        if count == 0:
            # Только если таблица пустая — инициализируем
            self._initialize_default_schedule()

    def _initialize_default_schedule(self):
        """Инициализирует расписание по умолчанию"""
        default_slots = {
            0: [("10:00", "13:00"), ("14:30", "17:30"), ("18:00", "21:00")],    # Понедельник
            1: [],                                                              # Вторник - выходной
            2: [("10:00", "13:00"), ("14:30", "17:30"), ("18:00", "21:00")],    # Среда
            3: [("14:30", "18:00"), ("18:00", "21:00")],                        # Четверг
            4: [("14:30", "17:30"), ("18:00", "21:00")],                        # Пятница
            5: [],                                                              # Суббота - выходной
            6: [("11:00", "14:00"), ("14:30", "17:30"), ("18:00", "20:00")]     # Воскресенье
        }

        for weekday, slots in default_slots.items():
            self.set_day_schedule(weekday, slots, bool(slots))

    def set_day_schedule(self, weekday: int, time_slots: List[Tuple[str, str]], is_working: bool = True):
        """Устанавливает расписание для дня недели"""
        # Конвертируем в JSON
        slots_json = json.dumps(time_slots)
        query = f"""
        INSERT OR REPLACE INTO {self.__tablename__} 
        (weekday, time_slots, is_working)
        VALUES (?, ?, ?)
        """
        self._log('EDIT_DAY_SCHEDULE', weekday=weekday, time_slots=time_slots, is_working=is_working)
        self.cursor.execute(query, (weekday, slots_json, is_working))
        self.conn.commit()

    def get_day_schedule(self, weekday: int) -> Optional[DaySchedule]:
        """Возвращает расписание для конкретного дня"""
        query = f"SELECT * FROM {self.__tablename__} WHERE weekday = ?"
        self.cursor.execute(query, (weekday,))
        row = self.cursor.fetchone()
        if row:
            slots = [(time.fromisoformat(start), time.fromisoformat(end)) for start, end in json.loads(row['time_slots'])]
            return DaySchedule(
                weekday=row['weekday'],
                time_slots=slots,
                is_working=bool(row['is_working'])
            )
        return None

    def get_all_schedules(self) -> Dict[int, DaySchedule]:
        """Возвращает все расписания"""
        query = f"SELECT * FROM {self.__tablename__} ORDER BY weekday"
        self.cursor.execute(query)

        schedules = {}
        for row in self.cursor.fetchall():
            time_slots = [(time.fromisoformat(start), time.fromisoformat(end)) for start, end in json.loads(row['time_slots'])]
            schedules[row['weekday']] = DaySchedule(
                weekday=row['weekday'],
                time_slots=time_slots,
                is_working=bool(row['is_working'])
            )
        return schedules
