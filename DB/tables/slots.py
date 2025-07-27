from datetime import datetime, date, timedelta, time
from typing import Optional, List

from DB.models import SlotModel
from DB.tables.base import BaseTable


class SlotsTable(BaseTable):
    __tablename__ = 'slots'

    def create_table(self):
        """Создание таблицы slots"""
        self.cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {self.__tablename__} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP NOT NULL,
            is_available BOOLEAN NOT NULL DEFAULT 1,
            UNIQUE (start_time)
        )''')
        self.conn.commit()
        self._log('CREATE_TABLE')

    def add_slot(self, start_time: datetime, end_time: datetime) -> int:
        """Добавляет новый слот для записи и возвращает его ID."""
        query = f"""
        INSERT INTO {self.__tablename__} (start_time, end_time)
        VALUES (?, ?)
        """
        self.cursor.execute(query, (start_time, end_time))
        self._log('ADD_SLOT', start_time=start_time, end_time=end_time)
        self.conn.commit()
        return self.cursor.lastrowid

    def is_available(self, slot_id: int) -> Optional[bool]:
        query = f"""
            SELECT * FROM {self.__tablename__} 
            WHERE id = ?
            """

        self.cursor.execute(query, (slot_id,))
        row = self.cursor.fetchone()
        if row:
            return bool(row['is_available'])
        else:
            return None

    def get_slot(self, slot_id: int) -> Optional[SlotModel]:
        """Возвращает список доступных слотов."""
        query = f"""
            SELECT * FROM {self.__tablename__} 
            WHERE id = ?
            """
        self.cursor.execute(query, (slot_id,))

        row = self.cursor.fetchone()
        if row:
            return SlotModel(
                id=row['id'],
                start_time=datetime.fromisoformat(row['start_time'])
                if row['start_time'] is not None else None,
                end_time=datetime.fromisoformat(row['end_time'])
                if row['end_time'] is not None else None,
                is_available=bool(row['is_available'])
            )
        return None

    def get_available_slots(self, from_time: Optional[datetime] = None, to_time: Optional[datetime] = None) -> List[SlotModel]:
        """Возвращает список доступных слотов."""
        if from_time and to_time and to_time < from_time:
            raise ValueError("Конечное время не может быть раньше начального")

        query = f"""
            SELECT * FROM {self.__tablename__} 
            WHERE is_available = TRUE
            """

        params = []

        if from_time:
            query += " AND start_time >= ?"
            params.append(from_time)

        if to_time:
            query += " AND start_time <= ?"
            params.append(to_time)

        query += " ORDER BY start_time ASC"

        self.cursor.execute(query, tuple(params))

        return [
            SlotModel(
                id=row['id'],
                start_time=datetime.fromisoformat(row['start_time'])
                if row['start_time'] is not None else None,
                end_time=datetime.fromisoformat(row['end_time'])
                if row['end_time'] is not None else None,
                is_available=bool(row['is_available'])
            )
            for row in self.cursor
        ]

    def get_available_slots_by_day(self, day: date) -> List[SlotModel]:
        """Возвращает список доступных слотов на указанный день."""
        start = datetime.combine(day, time.min)
        end = datetime.combine(day, time.max)
        return self.get_available_slots(from_time=start, to_time=end)

    def reserve_slot(self, slot_id: int) -> bool:
        """Помечает слот как занятый."""
        if not self._check_record_exists('slots', 'id', slot_id):
            raise ValueError(f"Slot with id {slot_id} not found")
        if self.is_available(slot_id):
            query = f"UPDATE {self.__tablename__} SET is_available = FALSE WHERE id = ?"
            self.cursor.execute(query, (slot_id,))
            self.conn.commit()
            self._log('RESERVE_SLOT', slot_id=slot_id)
            return True
        else:
            return False


if __name__ == '__main__':
    with SlotsTable() as slots_db:
        slots_db.add_slot(datetime.now() + timedelta(hours=3), datetime.now() + timedelta(hours=5))
        slots_db.add_slot(datetime.now() + timedelta(hours=6), datetime.now() + timedelta(hours=8))
        slots_db.add_slot(datetime.now() + timedelta(hours=13), datetime.now() + timedelta(hours=15))
        slots_db.add_slot(datetime.now() + timedelta(hours=23), datetime.now() + timedelta(hours=25))
        slots_db.add_slot(datetime.now() + timedelta(hours=33), datetime.now() + timedelta(hours=35))
        slots_db.add_slot(datetime.now() + timedelta(hours=26), datetime.now() + timedelta(hours=27))
        slots_db.add_slot(datetime.now() + timedelta(hours=56), datetime.now() + timedelta(hours=59))
        slots_db.add_slot(datetime.now() + timedelta(hours=50), datetime.now() + timedelta(hours=52))

        print(slots_db.get_available_slots(datetime.now(), datetime.now() + timedelta(hours=8)))
        print(slots_db.get_available_slots(datetime.now(), datetime.now() + timedelta(hours=40)))