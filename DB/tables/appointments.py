from datetime import datetime, timedelta, timezone, date
from typing import Optional, Set, Tuple, List

from DB.models import AppointmentModel, UserModel, SlotModel, ServiceModel, Pagination
from DB.tables.appointment_photos import AppointmentPhotosTable
from DB.tables.base import BaseTable
from config.const import PENDING, COMPLETED, CONFIRMED, CANCELLED, REJECTED


class AppointmentsTable(BaseTable):
    __tablename__ = 'appointments'
    __valid_statuses = {PENDING, CONFIRMED, CANCELLED, COMPLETED, REJECTED}
    __timezone_offset = timezone(timedelta(hours=3))  # Для MSK (UTC+3)

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        if not dt_str:
            return None
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(self.__timezone_offset)

    def create_table(self) -> None:
        """Создание таблицы appointments с индексами и триггером"""
        self.cursor.executescript(f'''
            CREATE TABLE IF NOT EXISTS {self.__tablename__} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                slot_id INTEGER NOT NULL,
                service_id INTEGER NOT NULL,
                comment TEXT,
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'confirmed', 'completed', 'cancelled', 'rejected')),
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
        self._log('CREATE_TABLE', __timezone_offset=self.__timezone_offset)

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
        SELECT a.*, s.name as service_name, sl.start_time, sl.end_time, u.*
        FROM {self.__tablename__} a
        LEFT JOIN services s ON a.service_id = s.id
        LEFT JOIN slots sl ON a.slot_id = sl.id
        LEFT JOIN users u ON a.client_id = u.user_id
        WHERE a.status = 'pending'
        ORDER BY sl.start_time ASC, a.created_at ASC
        LIMIT 1 OFFSET ?
        """

        # Можно использовать либо n, либо offset в зависимости от логики нумерации
        self.cursor.execute(query, (n,))  # или (offset,)
        row = self.cursor.fetchone()

        if not row:
            return None

        with AppointmentPhotosTable() as app_ph_db:
            return AppointmentModel(
                appointment_id=row['id'],
                client=UserModel(user_id=row['client_id'],
                                 username=row['username'],
                                 first_name=row['first_name'],
                                 last_name=row['last_name'],
                                 contact=row['contact']),
                slot=SlotModel(id=row['slot_id'],
                               start_time=datetime.fromisoformat(row['start_time']),
                               end_time=datetime.fromisoformat(row['end_time']),
                               is_available=False),
                service=ServiceModel(id=row['service_id'],
                                     name=row['service_name']),
                comment=row['comment'],
                status=row['status'],
                created_at=self._parse_datetime(row['created_at']),
                updated_at=self._parse_datetime(row['updated_at']),
                photos=app_ph_db.get_appointment_photos(row['id'])
            )

    def count_appointments(self, status: str = PENDING, only_future: bool = True) -> int:
        """Подсчитывает количество записей, с возможностью фильтрации по статусу и времени.

        Args:
            status: Если указан, подсчитывает только записи с этим статусом
            only_future: Если True, учитывает только записи с start_time >= текущему времени

        Returns:
            Количество найденных записей
        """
        now = datetime.now(self.__timezone_offset)

        base_query = f"""
        SELECT COUNT(*) as count
        FROM {self.__tablename__} a
        LEFT JOIN slots sl ON a.slot_id = sl.id
        """

        conditions = []
        params = []

        if status is not None:
            if status not in self.__valid_statuses:
                raise ValueError(f"Invalid status. Allowed values: {self.__valid_statuses}")
            conditions.append("a.status = ?")
            params.append(status)

        if only_future:
            conditions.append("sl.start_time >= ?")
            params.append(now)

        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)

        self.cursor.execute(base_query, params)
        result = self.cursor.fetchone()
        return result['count'] if result else 0

    def get_client_appointments(self, client_id: int, page: int = 1, only_future: bool = True) -> tuple[Optional[AppointmentModel], Pagination]:
        """Возвращает список актуальных записей клиента с постраничной навигацией.
        Args:
            client_id: ID клиента
            page: Номер страницы
            only_future: Если True, возвращает только будущие записи (end_time >= now)
        """
        now = datetime.now(self.__timezone_offset)
        per_page = 1
        pagination = Pagination(
            page=page,
            per_page=per_page,
            total_items=0,
            total_pages=0
        )

        base_conditions = "a.client_id = ? AND status != 'cancelled'"
        params = [client_id]

        if only_future:
            base_conditions += " AND sl.end_time >= ?"
            params.append(now)

        count_query = f"""
            SELECT COUNT(*) as total
            FROM {self.__tablename__} a
            LEFT JOIN slots sl ON a.slot_id = sl.id
            WHERE {base_conditions}
            """
        self.cursor.execute(count_query, params)
        total_items = self.cursor.fetchone()['total']

        pagination.total_items = total_items
        pagination.total_pages = max(1, (total_items + per_page - 1) // per_page)

        query = f"""
            SELECT 
                a.*, 
                s.name as service_name, 
                sl.start_time, 
                sl.end_time, 
                u.username, 
                u.contact
            FROM {self.__tablename__} a
            LEFT JOIN services s ON a.service_id = s.id
            LEFT JOIN slots sl ON a.slot_id = sl.id
            LEFT JOIN users u ON a.client_id = u.user_id
            WHERE {base_conditions}
            ORDER BY sl.start_time ASC
            LIMIT ? OFFSET ?
            """
        params.extend([per_page, pagination.offset])
        self.cursor.execute(query, params)

        row = self.cursor.fetchone()
        app = None
        if row:
            with AppointmentPhotosTable() as app_ph_db:
                app = AppointmentModel(
                    appointment_id=row['id'],
                    client=UserModel(
                        user_id=row['client_id'],
                        username=row['username'],
                        contact=row['contact']
                    ),
                    slot=SlotModel(
                        id=row['slot_id'],
                        start_time=datetime.fromisoformat(row['start_time']),
                        end_time=datetime.fromisoformat(row['end_time']),
                        is_available=False
                    ),
                    service=ServiceModel(
                        id=row['service_id'],
                        name=row['service_name']
                    ),
                    comment=row['comment'],
                    status=row['status'],
                    created_at=self._parse_datetime(row['created_at']),
                    updated_at=self._parse_datetime(row['updated_at']),
                    photos=app_ph_db.get_appointment_photos(row['id'])
                )

        return app, pagination

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

    def get_appointment_by_id(self, appointment_id: int) -> Optional[AppointmentModel]:
        query = f"""
        SELECT 
            a.*, 
            s.name as service_name, 
            sl.start_time, 
            sl.end_time, 
            u.*
        FROM {self.__tablename__} a
        LEFT JOIN services s ON a.service_id = s.id
        LEFT JOIN slots sl ON a.slot_id = sl.id
        LEFT JOIN users u ON a.client_id = u.user_id
        WHERE a.id = ?
        """

        self.cursor.execute(query, (appointment_id,))
        row = self.cursor.fetchone()

        if not row:
            return None

        with AppointmentPhotosTable() as app_ph_db:
            return AppointmentModel(
                appointment_id=row['id'],
                client=UserModel(
                    user_id=row['client_id'],
                    username=row['username'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    contact=row['contact']
                ),
                slot=SlotModel(
                    id=row['slot_id'],
                    start_time=datetime.fromisoformat(row['start_time']),
                    end_time=datetime.fromisoformat(row['end_time']),
                    is_available=False
                ),
                service=ServiceModel(
                    id=row['service_id'],
                    name=row['service_name']
                ),
                comment=row['comment'],
                status=row['status'],
                created_at=self._parse_datetime(row['created_at']),
                updated_at=self._parse_datetime(row['updated_at']),
                photos=app_ph_db.get_appointment_photos(row['id'])
            )

    def get_appointments_by_status_and_date(self, app_date: datetime, status: str = CONFIRMED) -> list[AppointmentModel]:
        """Возвращает все записи с указанным статусом за указанный день.

        Args:
            status: Статус записи (должен быть одним из допустимых значений)
            app_date: Дата для фильтрации (учитывается только дата, время игнорируется)

        Returns:
            Список AppointmentModel объектов, удовлетворяющих условиям

        Raises:
            ValueError: Если передан недопустимый статус
        """
        if status not in self.__valid_statuses:
            raise ValueError(f"Invalid status. Allowed values: {self.__valid_statuses}")

        start_of_day = app_date.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_of_day = start_of_day + timedelta(days=1)

        query = f"""
        SELECT 
            a.*, 
            s.name as service_name, 
            sl.start_time, 
            sl.end_time, 
            u.*
        FROM {self.__tablename__} a
        LEFT JOIN services s ON a.service_id = s.id
        LEFT JOIN slots sl ON a.slot_id = sl.id
        LEFT JOIN users u ON a.client_id = u.user_id
        WHERE a.status = ? 
        AND sl.end_time >= ? 
        AND sl.start_time <= ?
        ORDER BY sl.start_time ASC
        """

        params = (
            status,
            app_date,
            end_of_day
        )

        self.cursor.execute(query, params)
        rows = self.cursor.fetchall()

        appointments = []
        with AppointmentPhotosTable() as app_ph_db:
            for row in rows:
                appointment = AppointmentModel(
                    appointment_id=row['id'],
                    client=UserModel(
                        user_id=row['client_id'],
                        username=row['username'],
                        first_name=row['first_name'],
                        last_name=row['last_name'],
                        contact=row['contact']
                    ),
                    slot=SlotModel(
                        id=row['slot_id'],
                        start_time=datetime.fromisoformat(row['start_time']),
                        end_time=datetime.fromisoformat(row['end_time']),
                        is_available=False
                    ),
                    service=ServiceModel(
                        id=row['service_id'],
                        name=row['service_name']
                    ),
                    comment=row['comment'],
                    status=row['status'],
                    created_at=self._parse_datetime(row['created_at']),
                    updated_at=self._parse_datetime(row['updated_at']),
                    photos=app_ph_db.get_appointment_photos(row['id'])
                )
                appointments.append(appointment)

        return appointments

    def get_master_actions(self, page: int = 1, per_page: int = 10) -> tuple[list[AppointmentModel], Pagination]:
        """Возвращает список подтвержденных и отклоненных записей (действия админа) с пагинацией"""
        pagination = Pagination(
            page=page,
            per_page=per_page,
            total_items=0,
            total_pages=0
        )

        total_items = (self.count_appointments(status=CONFIRMED, only_future=False) +
                       self.count_appointments(status=REJECTED, only_future=False))
        pagination.total_items = total_items
        pagination.total_pages = max(1, (total_items + per_page - 1) // per_page)

        query = f"""
        SELECT 
            a.*, 
            s.name as service_name, 
            sl.start_time, 
            sl.end_time, 
            u.*
        FROM {self.__tablename__} a
        LEFT JOIN services s ON a.service_id = s.id
        LEFT JOIN slots sl ON a.slot_id = sl.id
        LEFT JOIN users u ON a.client_id = u.user_id
        WHERE a.status IN ('confirmed', 'rejected')
        ORDER BY a.updated_at DESC
        LIMIT ? OFFSET ?
        """

        self.cursor.execute(query, (per_page, pagination.offset))
        rows = self.cursor.fetchall()

        appointments = []
        with AppointmentPhotosTable() as app_ph_db:
            for row in rows:
                appointment = AppointmentModel(
                    appointment_id=row['id'],
                    client=UserModel(
                        user_id=row['client_id'],
                        username=row['username'],
                        first_name=row['first_name'],
                        last_name=row['last_name'],
                        contact=row['contact']
                    ),
                    slot=SlotModel(
                        id=row['slot_id'],
                        start_time=datetime.fromisoformat(row['start_time']),
                        end_time=datetime.fromisoformat(row['end_time']),
                        is_available=False
                    ),
                    service=ServiceModel(
                        id=row['service_id'],
                        name=row['service_name']
                    ),
                    comment=row['comment'],
                    status=row['status'],
                    created_at=self._parse_datetime(row['created_at']),
                    updated_at=self._parse_datetime(row['updated_at']),
                    photos=app_ph_db.get_appointment_photos(row['id'])
                )
                appointments.append(appointment)

        return appointments, pagination

    def get_appointments_by_status_and_time_range(
            self,
            status: str,
            from_time: datetime,
            to_time: datetime,
            page: int = 1,
            per_page: int = 1
    ) -> Tuple[List[AppointmentModel], Pagination]:
        """Возвращает список записей по статусу и временному интервалу с пагинацией.

        Args:
            status: Статус записи (должен быть одним из допустимых значений)
            from_time: Начало временного интервала (включительно)
            to_time: Конец временного интервала (включительно)
            page: Номер страницы (начинается с 1)
            per_page: Количество записей на странице

        Returns:
            Кортеж (список AppointmentModel, объект Pagination)

        Raises:
            ValueError: Если передан недопустимый статус или некорректный временной интервал
        """
        if status not in self.__valid_statuses:
            raise ValueError(f"Invalid status. Allowed values: {self.__valid_statuses}")

        if from_time > to_time:
            raise ValueError("from_time must be less than or equal to to_time")

        pagination = Pagination(
            page=page,
            per_page=per_page,
            total_items=0,
            total_pages=0
        )

        count_query = f"""
        SELECT COUNT(*) as total
        FROM {self.__tablename__} a
        LEFT JOIN slots sl ON a.slot_id = sl.id
        WHERE a.status = ? 
        AND sl.start_time >= ? 
        AND sl.start_time <= ?
        """

        self.cursor.execute(count_query, (status, from_time, to_time))
        total_items = self.cursor.fetchone()['total']

        pagination.total_items = total_items
        pagination.total_pages = max(1, (total_items + per_page - 1) // per_page)

        query = f"""
        SELECT 
            a.*, 
            s.name as service_name, 
            sl.start_time, 
            sl.end_time, 
            u.*
        FROM {self.__tablename__} a
        LEFT JOIN services s ON a.service_id = s.id
        LEFT JOIN slots sl ON a.slot_id = sl.id
        LEFT JOIN users u ON a.client_id = u.user_id
        WHERE a.status = ? 
        AND sl.start_time >= ? 
        AND sl.start_time <= ?
        ORDER BY sl.start_time ASC
        LIMIT ? OFFSET ?
        """

        params = (
            status,
            from_time,
            to_time,
            per_page,
            pagination.offset
        )

        self.cursor.execute(query, params)
        rows = self.cursor.fetchall()

        appointments = []
        with AppointmentPhotosTable() as app_ph_db:
            for row in rows:
                appointment = AppointmentModel(
                    appointment_id=row['id'],
                    client=UserModel(
                        user_id=row['client_id'],
                        username=row['username'],
                        first_name=row['first_name'],
                        last_name=row['last_name'],
                        contact=row['contact']
                    ),
                    slot=SlotModel(
                        id=row['slot_id'],
                        start_time=datetime.fromisoformat(row['start_time']),
                        end_time=datetime.fromisoformat(row['end_time']),
                        is_available=False
                    ),
                    service=ServiceModel(
                        id=row['service_id'],
                        name=row['service_name']
                    ),
                    comment=row['comment'],
                    status=row['status'],
                    created_at=self._parse_datetime(row['created_at']),
                    updated_at=self._parse_datetime(row['updated_at']),
                    photos=app_ph_db.get_appointment_photos(row['id'])
                )
                appointments.append(appointment)

        return appointments, pagination

    def get_booked_slot_dates(self, status: str, from_time: datetime, to_time: datetime) -> Set[date]:
        """Возвращает множество start_time всех слотов, соответствующих условиям.

        Args:
            status: Статус записи (например, CONFIRMED)
            from_time: Начало периода (включительно)
            to_time: Конец периода (включительно)

        Returns:
            Множество datetime объектов start_time без дубликатов.

        Raises:
            ValueError: Если статус некорректен или временной интервал невалиден.
        """
        if status not in self.__valid_statuses:
            raise ValueError(f"Invalid status. Allowed: {self.__valid_statuses}")

        if from_time > to_time:
            raise ValueError("from_time must be <= to_time")

        query = f"""
        SELECT DISTINCT sl.start_time
        FROM {self.__tablename__} a
        JOIN slots sl ON a.slot_id = sl.id
        WHERE a.status = ?
        AND sl.end_time >= ?
        AND sl.start_time <= ?
        """

        self.cursor.execute(query, (status, from_time, to_time))
        rows = self.cursor.fetchall()

        return {datetime.fromisoformat(row['start_time']).date() for row in rows}

    def count_appointments_by_status_and_time(self, status: str, from_time: datetime, to_time: datetime) -> int:
        if status not in self.__valid_statuses:
            raise ValueError(f"Invalid status. Allowed: {self.__valid_statuses}")

        if from_time > to_time:
            raise ValueError("from_time must be <= to_time")

        query = f"""
        SELECT COUNT(*) as count
        FROM {self.__tablename__} a
        JOIN slots sl ON a.slot_id = sl.id
        WHERE a.status = ?
        AND sl.end_time >= ? AND sl.start_time <= ?
        """

        params = (status, from_time, to_time)

        self.cursor.execute(query, params)
        result = self.cursor.fetchone()
        return result['count'] if result else 0

    @property
    def valid_statuses(self):
        return self.__valid_statuses
