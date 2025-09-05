import os
from datetime import datetime
from typing import List, Optional

from DB.tables.base import BaseTable
from DB.models import Weekday


class WeekdaysTable(BaseTable):
    __tablename__ = 'weekdays'

    def __init__(self, db_name: str = f'{os.path.dirname(__file__)}/z_users.db'):
        super().__init__(db_name)
        self.create_table()
        self._populate_weekdays()

    def create_table(self) -> None:
        """Создание таблицы weekdays"""
        self.cursor.executescript(f"""
        CREATE TABLE IF NOT EXISTS {self.__tablename__} (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            name_ru TEXT NOT NULL,
            short_name TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_weekdays_name ON {self.__tablename__}(name);
        CREATE INDEX IF NOT EXISTS idx_weekdays_name_ru ON {self.__tablename__}(name_ru);
        """)
        self.conn.commit()
        self._log('CREATE_TABLE')

    def _populate_weekdays(self) -> None:
        """Заполняет таблицу днями недели, если она пустая"""
        self.cursor.execute(f"SELECT COUNT(*) as count FROM {self.__tablename__}")
        count = self.cursor.fetchone()['count']

        if count > 0:
            return

        weekdays_data = [
            (1, 'monday', 'понедельник', 'Пн'),
            (2, 'tuesday', 'вторник', 'Вт'),
            (3, 'wednesday', 'среда', 'Ср'),
            (4, 'thursday', 'четверг', 'Чт'),
            (5, 'friday', 'пятница', 'Пт'),
            (6, 'saturday', 'суббота', 'Сб'),
            (7, 'sunday', 'воскресенье', 'Вс')
        ]

        query = f"""
        INSERT INTO {self.__tablename__} (id, name, name_ru, short_name)
        VALUES (?, ?, ?, ?)
        """

        self.cursor.executemany(query, weekdays_data)
        self.conn.commit()
        self._log('POPULATE_WEEKDAYS', count=len(weekdays_data))

    def get_all_weekdays(self) -> List[Weekday]:
        """Возвращает все дни недели"""
        query = f"SELECT * FROM {self.__tablename__} ORDER BY id"
        self.cursor.execute(query)
        rows = self.cursor.fetchall()

        return [
            Weekday(
                id=row['id'],
                name=row['name'],
                name_ru=row['name_ru'],
                short_name=row['short_name']
            ) for row in rows
        ]

    def get_weekday_by_id(self, weekday_id: int) -> Optional[Weekday]:
        """Возвращает день недели по ID"""
        query = f"SELECT * FROM {self.__tablename__} WHERE id = ?"
        self.cursor.execute(query, (weekday_id,))
        row = self.cursor.fetchone()

        if not row:
            return None

        return Weekday(
            id=row['id'],
            name=row['name'],
            name_ru=row['name_ru'],
            short_name=row['short_name']
        )

    def get_weekday_by_name(self, name: str) -> Optional[Weekday]:
        """Возвращает день недели по английскому названию"""
        query = f"SELECT * FROM {self.__tablename__} WHERE name = ?"
        self.cursor.execute(query, (name,))
        row = self.cursor.fetchone()

        if not row:
            return None

        return Weekday(
            id=row['id'],
            name=row['name'],
            name_ru=row['name_ru'],
            short_name=row['short_name']
        )

    def get_weekday_by_name_ru(self, name_ru: str) -> Optional[Weekday]:
        """Возвращает день недели по русскому названию"""
        query = f"SELECT * FROM {self.__tablename__} WHERE name_ru = ?"
        self.cursor.execute(query, (name_ru,))
        row = self.cursor.fetchone()

        if not row:
            return None

        return Weekday(
            id=row['id'],
            name=row['name'],
            name_ru=row['name_ru'],
            short_name=row['short_name']
        )

    @staticmethod
    def get_weekday_id_by_date(date: datetime) -> int:
        """
        Возвращает ID дня недели для указанной даты.
        SQLite: 0-воскресенье, 6-суббота → наши ID: 1-понедельник, 7-воскресенье
        """
        # SQLite возвращает 0-6 (0=воскресенье, 1=понедельник и т.д.)
        sqlite_weekday = date.weekday()  # Python: 0=понедельник, 6=воскресенье

        # Преобразуем в нашу систему: 1=понедельник, 7=воскресенье
        # Python weekday: 0=пн,1=вт,2=ср,3=чт,4=пт,5=сб,6=вс
        # Наши ID:        1=пн,2=вт,3=ср,4=чт,5=пт,6=сб,7=вс
        return sqlite_weekday + 1 if sqlite_weekday < 6 else 7
