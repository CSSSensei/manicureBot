from datetime import datetime, timedelta, timezone
from typing import List, Optional

from DB.models import AppointmentModel
from DB.tables.appointment_photos import AppointmentPhotosTable
from DB.tables.base import BaseTable


class AppointmentsTable(BaseTable):
    __tablename__ = 'appointments'
    __valid_statuses = {'pending', 'confirmed', 'completed', 'cancelled'}
    __timezone_offset = timezone(timedelta(hours=3))  # Для MSK (UTC+3)

    def create_table(self) -> None:
        """Создание таблицы appointments с индексами и триггером"""
        self.cursor.executescript(f'''
            CREATE TABLE IF NOT EXISTS {self.__tablename__} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                slot_id INTEGER NOT NULL,
                service_id INTEGER NOT NULL,
                comment TEXT,
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'confirmed', 'completed', 'cancelled')),
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (client_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (slot_id) REFERENCES slots(id) ON DELETE RESTRICT,
                FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE RESTRICT
            );

            CREATE INDEX IF NOT EXISTS idx_appointments_client ON {self.__tablename__}(client_id);
            CREATE INDEX IF NOT EXISTS idx_appointments_slot ON {self.__tablename__}(slot_id);
            CREATE INDEX IF NOT EXISTS idx_appointments_status ON {self.__tablename__}(status);

            CREATE TRIGGER IF NOT EXISTS update_appointments_timestamp
            AFTER UPDATE ON {self.__tablename__}
            FOR EACH ROW
            BEGIN
                UPDATE {self.__tablename__} SET updated_at = datetime('now') WHERE id = OLD.id;
            END;
            ''')
        self.conn.commit()
        self._log('CREATE_TABLE')

    def create_appointment(
            self,
            client_id: int,
            slot_id: int,
            service_id: int,
            comment: Optional[str] = None,
            status: str = 'pending'
    ) -> int:
        """Создает новую запись и возвращает её ID."""
        if status not in self.__valid_statuses:
            raise ValueError(f"Invalid status. Allowed values: {self.__valid_statuses}")

        if not self._check_record_exists('users', 'user_id', client_id):
            raise ValueError(f"Client with id {client_id} not found")
        if not self._check_record_exists('slots', 'id', slot_id):
            raise ValueError(f"Slot with id {slot_id} not found")
        if not self._check_record_exists('services', 'id', service_id):
            raise ValueError(f"Service with id {service_id} not found")

        query = f"""
        INSERT INTO {self.__tablename__} (client_id, slot_id, service_id, comment, status)
        VALUES (?, ?, ?, ?, ?)
        """
        self.cursor.execute(query, (client_id, slot_id, service_id, comment, status))
        self.conn.commit()
        appointment_id = self.cursor.lastrowid
        self._log('CREATE_APPOINTMENT',
                  client_id=client_id,
                  slot_id=slot_id,
                  appointment_id=appointment_id)
        return appointment_id

    def get_nth_pending_appointment(self, n: int = 0) -> Optional[AppointmentModel]:
        """Возвращает N-ю по счету pending запись (по умолчанию первую) с возможностью смещения.

        Args:
            n: Порядковый номер записи (начинается с 0)

        Returns:
            AppointmentModel или None, если записи не найдены
        """
        query = f"""
        SELECT a.*, s.name as service_name, sl.start_time, sl.end_time
        FROM {self.__tablename__} a
        LEFT JOIN services s ON a.service_id = s.id
        LEFT JOIN slots sl ON a.slot_id = sl.id
        WHERE a.status = 'pending'
        ORDER BY sl.start_time ASC, a.created_at ASC
        LIMIT 1 OFFSET ?
        """

        # Можно использовать либо n, либо offset в зависимости от логики нумерации
        self.cursor.execute(query, (n,))  # или (offset,)
        row = self.cursor.fetchone()

        if not row:
            return None

        def parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
            if not dt_str:
                return None
            dt = datetime.fromisoformat(dt_str)
            return dt.astimezone(self.__timezone_offset) if dt.tzinfo else dt.replace(tzinfo=self.__timezone_offset)

        with AppointmentPhotosTable() as app_ph_db:
            return AppointmentModel(
                appointment_id=row['id'],
                client_id=row['client_id'],
                slot_id=row['slot_id'],
                service_id=row['service_id'],
                comment=row['comment'],
                status=row['status'],
                created_at=parse_datetime(row['created_at']),
                updated_at=parse_datetime(row['updated_at']),
                service_name=row['service_name'],
                start_time=parse_datetime(row['start_time']),
                end_time=parse_datetime(row['end_time']),
                photos=app_ph_db.get_appointment_photos(row['id'])
            )

    def count_pending_appointments(self) -> int:
        """Возвращает количество записей со статусом 'pending'."""
        query = f"""
        SELECT COUNT(*) as count
        FROM {self.__tablename__}
        WHERE status = 'pending'
        """
        self.cursor.execute(query)
        result = self.cursor.fetchone()
        return result['count'] if result else 0

    def get_client_appointments(self, client_id: int) -> List[AppointmentModel]:
        """Возвращает список записей клиента."""
        query = f"""
        SELECT a.*, s.name as service_name, sl.start_time, sl.end_time
        FROM {self.__tablename__} a
        LEFT JOIN services s ON a.service_id = s.id
        LEFT JOIN slots sl ON a.slot_id = sl.id
        WHERE a.client_id = ?
        ORDER BY sl.start_time
        """
        self.cursor.execute(query, (client_id,))

        def parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
            if not dt_str:
                return None
            dt = datetime.fromisoformat(dt_str)
            return dt.astimezone(self.__timezone_offset) if dt.tzinfo else dt.replace(tzinfo=self.__timezone_offset)

        return [AppointmentModel(
            id=row['id'],
            client_id=row['client_id'],
            slot_id=row['slot_id'],
            service_id=row['service_id'],
            comment=row['comment'],
            status=row['status'],
            created_at=parse_datetime(row['created_at']),
            updated_at=parse_datetime(row['updated_at']),
            service_name=row['service_name'],
            start_time=parse_datetime(row['start_time']),
            end_time=parse_datetime(row['end_time'])
        ) for row in self.cursor]

    def update_appointment_status(self, appointment_id: int, status: str) -> None:
        """Обновляет статус записи."""
        if status not in self.__valid_statuses:
            raise ValueError(f"Invalid status. Allowed values: {self.__valid_statuses}")

        # Проверка существования записи
        if not self._check_record_exists(self.__tablename__, 'id', appointment_id):
            raise ValueError(f"Appointment with id {appointment_id} not found")

        query = f"""
        UPDATE {self.__tablename__} 
        SET status = ?
        WHERE id = ?
        """
        self.cursor.execute(query, (status, appointment_id))
        self.conn.commit()
        self._log('UPDATE_APPOINTMENT_STATUS',
                  appointment_id=appointment_id,
                  status=status)
