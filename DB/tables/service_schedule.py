from DB.models import ServiceSchedule, Weekday
from DB.tables.base import BaseTable


class ServiceScheduleTable(BaseTable):
    __tablename__ = 'service_schedule'

    def create_table(self) -> None:
        self.cursor.executescript(f"""
        CREATE TABLE IF NOT EXISTS {self.__tablename__} (
            service_id INTEGER,
            weekday_id INTEGER,
            is_available BOOLEAN DEFAULT TRUE,
            PRIMARY KEY (service_id, weekday_id),
            FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE,
            FOREIGN KEY (weekday_id) REFERENCES weekdays(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_service_schedule_service ON {self.__tablename__}(service_id);
        CREATE INDEX IF NOT EXISTS idx_service_schedule_weekday ON {self.__tablename__}(weekday_id);
        CREATE INDEX IF NOT EXISTS idx_service_schedule_available ON {self.__tablename__}(is_available);
        """)
        self.conn.commit()
        self._log('CREATE_TABLE')

    def set_service_availability(self, service_id: int, weekday_id: int, is_available: bool) -> bool:
        """
        Устанавливает доступность услуги в конкретный день недели.

        Returns:
            True если успешно, False если ошибка
        """
        try:
            query = f"""
            INSERT OR REPLACE INTO {self.__tablename__}
            (service_id, weekday_id, is_available)
            VALUES (?, ?, ?)
            """
            self.cursor.execute(query, (service_id, weekday_id, is_available))
            self.conn.commit()
            self._log(
                'SET_SERVICE_AVAILABILITY', service_id=service_id, weekday_id=weekday_id, is_available=is_available
            )
            return True
        except Exception as e:
            self._log('SET_SERVICE_AVAILABILITY_ERROR', error=str(e))
            return False

    def set_service_weekdays(self, service_id: int, weekday_ids: list[int]) -> bool:
        """
        Устанавливает доступные дни недели для услуги.
        Все указанные дни будут доступны, остальные - недоступны.

        Returns:
            True если успешно, False если ошибка
        """
        try:
            query_disable = f"""
            INSERT OR REPLACE INTO {self.__tablename__}
            (service_id, weekday_id, is_available)
            SELECT ?, id, FALSE FROM weekdays
            """
            self.cursor.execute(query_disable, (service_id,))

            if weekday_ids:
                query_enable = f"""
                INSERT OR REPLACE INTO {self.__tablename__}
                (service_id, weekday_id, is_available)
                VALUES (?, ?, TRUE)
                """
                for weekday_id in weekday_ids:
                    self.cursor.execute(query_enable, (service_id, weekday_id))

            self.conn.commit()
            self._log('SET_SERVICE_WEEKDAYS', service_id=service_id, weekday_ids=weekday_ids)
            return True
        except Exception as e:
            self._log('SET_SERVICE_WEEKDAYS_ERROR', error=str(e))
            return False

    def get_service_schedule(self, service_id: int) -> list[ServiceSchedule]:
        query = f"""
        SELECT ss.*, w.*
        FROM {self.__tablename__} ss
        JOIN weekdays w ON ss.weekday_id = w.id
        WHERE ss.service_id = ?
        ORDER BY w.id
        """
        self.cursor.execute(query, (service_id,))
        rows = self.cursor.fetchall()

        return [
            ServiceSchedule(
                service_id=row['service_id'],
                weekday=Weekday(
                    id=row['weekday_id'], name=row['name'], name_ru=row['name_ru'], short_name=row['short_name']
                ),
                is_available=bool(row['is_available']),
            )
            for row in rows
        ]

    def get_available_weekdays(self, service_id: int) -> list[int]:
        query = f"""
        SELECT weekday_id
        FROM {self.__tablename__}
        WHERE service_id = ? AND is_available = TRUE
        ORDER BY weekday_id
        """
        self.cursor.execute(query, (service_id,))
        rows = self.cursor.fetchall()

        return [row['weekday_id'] for row in rows]

    def is_service_available(self, service_id: int, weekday_id: int) -> bool:
        query = f"""
        SELECT is_available
        FROM {self.__tablename__}
        WHERE service_id = ? AND weekday_id = ?
        """
        self.cursor.execute(query, (service_id, weekday_id))
        row = self.cursor.fetchone()

        return bool(row['is_available']) if row else False

    def get_services_for_weekday(self, weekday_id: int) -> list[int]:
        query = f"""
        SELECT service_id
        FROM {self.__tablename__}
        WHERE weekday_id = ? AND is_available = TRUE
        """
        self.cursor.execute(query, (weekday_id,))
        rows = self.cursor.fetchall()

        return [row['service_id'] for row in rows]

    def delete_service_schedule(self, service_id: int) -> int:
        """
        Удаляет всё расписание для указанной услуги.

        Returns:
            Количество удалённых записей
        """
        query = f'DELETE FROM {self.__tablename__} WHERE service_id = ?'
        self.cursor.execute(query, (service_id,))
        self.conn.commit()
        deleted_count = self.cursor.rowcount
        self._log('DELETE_SERVICE_SCHEDULE', service_id=service_id, count=deleted_count)
        return deleted_count

    def initialize_default_schedule(self, service_id: int) -> bool:
        try:
            query = f"""
            INSERT INTO {self.__tablename__}
            (service_id, weekday_id, is_available)
            SELECT ?, id, TRUE FROM weekdays
            """
            self.cursor.execute(query, (service_id,))
            self.conn.commit()
            self._log('INIT_DEFAULT_SCHEDULE', service_id=service_id)
            return True
        except Exception as e:
            self._log('INIT_DEFAULT_SCHEDULE_ERROR', error=str(e))
            return False
