import sqlite3
from datetime import date, datetime, timedelta, timezone

from config.const import CANCELLED, COMPLETED, CONFIRMED, DB_DIR, PENDING, REJECTED
from DB.models import AppointmentModel, ClientStats, ClientWithStats, Pagination, ServiceModel, SlotModel, UserModel
from DB.tables.appointment_photos import AppointmentPhotosTable
from DB.tables.base import BaseTable
from DB.tables.slots import SlotsTable


class AppointmentsTable(BaseTable):
    __tablename__ = 'appointments'
    __valid_statuses = {PENDING, CONFIRMED, CANCELLED, COMPLETED, REJECTED}
    __timezone_offset = timezone(timedelta(hours=3))  # Для MSK (UTC+3)

    def _parse_datetime(self, dt_str: str | None) -> datetime | None:
        if not dt_str:
            return None
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(self.__timezone_offset)

    def create_table(self) -> None:
        self.cursor.executescript(f"""
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
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_active_slot
            ON {self.__tablename__}(slot_id)
            WHERE status IN ('pending', 'confirmed');

            CREATE TRIGGER IF NOT EXISTS update_appointments_timestamp
            AFTER UPDATE ON {self.__tablename__}
            FOR EACH ROW
            BEGIN
                UPDATE {self.__tablename__} SET updated_at = datetime('now') WHERE id = OLD.id;
            END;
            """)
        self.conn.commit()
        self._log('CREATE_TABLE', __timezone_offset=self.__timezone_offset)

    def create_appointment(
        self, client_id: int, slot_id: int, service_id: int, comment: str | None = None, status: str = 'pending'
    ) -> int:
        if status not in self.__valid_statuses:
            raise ValueError(f'Invalid status. Allowed values: {self.__valid_statuses}')

        if not self._check_record_exists('users', 'user_id', client_id):
            raise ValueError(f'Client with id {client_id} not found')
        if not self._check_record_exists('slots', 'id', slot_id):
            raise ValueError(f'Slot with id {slot_id} not found')
        if not self._check_record_exists('services', 'id', service_id):
            raise ValueError(f'Service with id {service_id} not found')

        query = f"""
        INSERT INTO {self.__tablename__} (client_id, slot_id, service_id, comment, status)
        VALUES (?, ?, ?, ?, ?)
        """
        self.cursor.execute(
            query, (client_id, slot_id, service_id, comment, status)
        )  # Атомарная операция, поэтому коммит не делается
        appointment_id = self.cursor.lastrowid
        self._log('CREATE_APPOINTMENT', client_id=client_id, slot_id=slot_id, appointment_id=appointment_id)
        return appointment_id

    def get_nth_pending_appointment(self, n: int = 0) -> AppointmentModel | None:
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
                client=UserModel(
                    user_id=row['client_id'],
                    username=row['username'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    contact=row['contact'],
                ),
                slot=SlotModel(
                    id=row['slot_id'],
                    start_time=datetime.fromisoformat(row['start_time']),
                    end_time=datetime.fromisoformat(row['end_time']),
                    is_available=False,
                ),
                service=ServiceModel(id=row['service_id'], name=row['service_name']),
                comment=row['comment'],
                status=row['status'],
                created_at=self._parse_datetime(row['created_at']),
                updated_at=self._parse_datetime(row['updated_at']),
                photos=app_ph_db.get_appointment_photos(row['id']),
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
                raise ValueError(f'Invalid status. Allowed values: {self.__valid_statuses}')
            conditions.append('a.status = ?')
            params.append(status)

        if only_future:
            conditions.append('sl.start_time >= ?')
            params.append(now)

        if conditions:
            base_query += ' WHERE ' + ' AND '.join(conditions)

        self.cursor.execute(base_query, params)
        result = self.cursor.fetchone()
        return result['count'] if result else 0

    def get_client_appointments(
        self, client_id: int, page: int = 1, only_future: bool = True
    ) -> tuple[AppointmentModel | None, Pagination]:
        """Возвращает список актуальных записей клиента с постраничной навигацией.
        Args:
            client_id: ID клиента
            page: Номер страницы
            only_future: Если True, возвращает только будущие записи (end_time >= now)
        """
        now = datetime.now(self.__timezone_offset)
        per_page = 1
        pagination = Pagination(page=page, per_page=per_page, total_items=0, total_pages=0)

        base_conditions = "a.client_id = ? AND status != 'cancelled'"
        params = [client_id]

        if only_future:
            base_conditions += ' AND sl.end_time >= ?'
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
                    client=UserModel(user_id=row['client_id'], username=row['username'], contact=row['contact']),
                    slot=SlotModel(
                        id=row['slot_id'],
                        start_time=datetime.fromisoformat(row['start_time']),
                        end_time=datetime.fromisoformat(row['end_time']),
                        is_available=False,
                    ),
                    service=ServiceModel(id=row['service_id'], name=row['service_name']),
                    comment=row['comment'],
                    status=row['status'],
                    created_at=self._parse_datetime(row['created_at']),
                    updated_at=self._parse_datetime(row['updated_at']),
                    photos=app_ph_db.get_appointment_photos(row['id']),
                )

        return app, pagination

    def _update_appointment_status(self, appointment_id: int, status: str) -> None:
        if status not in self.__valid_statuses:
            raise ValueError(f'Invalid status. Allowed values: {self.__valid_statuses}')

        # Проверка существования записи
        if not self._check_record_exists(self.__tablename__, 'id', appointment_id):
            raise ValueError(f'Appointment with id {appointment_id} not found')

        query = f"""
        UPDATE {self.__tablename__}
        SET status = ?
        WHERE id = ?
        """
        self.cursor.execute(query, (status, appointment_id))
        self._log('UPDATE_APPOINTMENT_STATUS', appointment_id=appointment_id, status=status)

    def update_appointment_status(self, appointment_id: int, status: str) -> None:
        self._update_appointment_status(appointment_id, status)
        self.conn.commit()

    def get_appointment_by_id(self, appointment_id: int) -> AppointmentModel | None:
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
                    contact=row['contact'],
                ),
                slot=SlotModel(
                    id=row['slot_id'],
                    start_time=datetime.fromisoformat(row['start_time']),
                    end_time=datetime.fromisoformat(row['end_time']),
                    is_available=False,
                ),
                service=ServiceModel(id=row['service_id'], name=row['service_name']),
                comment=row['comment'],
                status=row['status'],
                created_at=self._parse_datetime(row['created_at']),
                updated_at=self._parse_datetime(row['updated_at']),
                photos=app_ph_db.get_appointment_photos(row['id']),
            )

    def get_appointments_by_status_and_date(
        self, app_date: datetime, status: str = CONFIRMED
    ) -> list[AppointmentModel]:
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
            raise ValueError(f'Invalid status. Allowed values: {self.__valid_statuses}')

        start_of_day = app_date.replace(hour=0, minute=0, second=0, microsecond=0)
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

        params = (status, app_date, end_of_day)

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
                        contact=row['contact'],
                    ),
                    slot=SlotModel(
                        id=row['slot_id'],
                        start_time=datetime.fromisoformat(row['start_time']),
                        end_time=datetime.fromisoformat(row['end_time']),
                        is_available=False,
                    ),
                    service=ServiceModel(id=row['service_id'], name=row['service_name']),
                    comment=row['comment'],
                    status=row['status'],
                    created_at=self._parse_datetime(row['created_at']),
                    updated_at=self._parse_datetime(row['updated_at']),
                    photos=app_ph_db.get_appointment_photos(row['id']),
                )
                appointments.append(appointment)

        return appointments

    def get_master_actions(self, page: int = 1, per_page: int = 10) -> tuple[list[AppointmentModel], Pagination]:
        pagination = Pagination(page=page, per_page=per_page, total_items=0, total_pages=0)

        count_query = f'SELECT COUNT(*) as total FROM {self.__tablename__}'
        self.cursor.execute(count_query)
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
                        contact=row['contact'],
                    ),
                    slot=SlotModel(
                        id=row['slot_id'],
                        start_time=datetime.fromisoformat(row['start_time']),
                        end_time=datetime.fromisoformat(row['end_time']),
                        is_available=False,
                    ),
                    service=ServiceModel(id=row['service_id'], name=row['service_name']),
                    comment=row['comment'],
                    status=row['status'],
                    created_at=self._parse_datetime(row['created_at']),
                    updated_at=self._parse_datetime(row['updated_at']),
                    photos=app_ph_db.get_appointment_photos(row['id']),
                )
                appointments.append(appointment)

        return appointments, pagination

    def get_appointments_by_status_and_time_range(
        self, status: str, from_time: datetime, to_time: datetime, page: int = 1, per_page: int = 1
    ) -> tuple[list[AppointmentModel], Pagination]:
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
            raise ValueError(f'Invalid status. Allowed values: {self.__valid_statuses}')

        if from_time > to_time:
            raise ValueError('from_time must be less than or equal to to_time')

        pagination = Pagination(page=page, per_page=per_page, total_items=0, total_pages=0)

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

        params = (status, from_time, to_time, per_page, pagination.offset)

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
                        contact=row['contact'],
                    ),
                    slot=SlotModel(
                        id=row['slot_id'],
                        start_time=datetime.fromisoformat(row['start_time']),
                        end_time=datetime.fromisoformat(row['end_time']),
                        is_available=False,
                    ),
                    service=ServiceModel(id=row['service_id'], name=row['service_name']),
                    comment=row['comment'],
                    status=row['status'],
                    created_at=self._parse_datetime(row['created_at']),
                    updated_at=self._parse_datetime(row['updated_at']),
                    photos=app_ph_db.get_appointment_photos(row['id']),
                )
                appointments.append(appointment)

        return appointments, pagination

    def get_booked_slot_dates(self, status: str, from_time: datetime, to_time: datetime) -> set[date]:
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
            raise ValueError(f'Invalid status. Allowed: {self.__valid_statuses}')

        if from_time > to_time:
            raise ValueError('from_time must be <= to_time')

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
            raise ValueError(f'Invalid status. Allowed: {self.__valid_statuses}')

        if from_time > to_time:
            raise ValueError('from_time must be <= to_time')

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

    def count_clients(self) -> int:
        """
        Возвращает количество уникальных пользователей,
        у которых есть хотя бы одна запись со статусом 'confirmed'.

        Returns:
            Количество пользователей (int)
        """
        count_query = f"""
        SELECT COUNT(DISTINCT client_id) as total
        FROM {self.__tablename__}
        """

        self.cursor.execute(count_query)
        result = self.cursor.fetchone()
        return result['total'] if result else 0

    def count_completed_slots(self) -> int:
        """
        Возвращает количество отработанных слотов (confirmed записи с прошедшей датой).

        Returns:
            Количество завершённых слотов (int)
        """
        query = """
        SELECT COUNT(*) as completed_count
        FROM appointments a
        JOIN slots s ON a.slot_id = s.id
        WHERE
            a.status = 'confirmed' AND
            s.end_time < datetime('now', '+3 hours')
        """

        self.cursor.execute(query)
        result = self.cursor.fetchone()
        return result['completed_count'] if result else 0

    def get_clients_with_stats(self, page: int = 1, per_page: int = 10) -> tuple[list[ClientWithStats], Pagination]:
        """Возвращает список клиентов со статистикой по их записям с пагинацией.
        Клиенты отсортированы по количеству завершённых записей (по убыванию).

        Args:
            page: Номер страницы (начинается с 1)
            per_page: Количество клиентов на странице

        Returns:
            Кортеж из:
            - Список объектов ClientWithStats для текущей страницы
            - Объект Pagination с информацией о пагинации
        """
        total_items = self.count_clients()

        pagination = Pagination(
            page=page,
            per_page=per_page,
            total_items=total_items,
            total_pages=max(1, (total_items + per_page - 1) // per_page),
        )

        query = f"""
        SELECT
            u.user_id,
            u.username,
            u.first_name,
            u.last_name,
            u.is_admin,
            u.is_banned,
            u.contact,

            COUNT(a.id)                                                                      AS total,
            MIN(sl.start_time)                                                               AS first_appointment,
            MAX(sl.start_time)                                                               AS last_appointment,

            SUM(CASE WHEN a.status = 'completed'                          THEN 1 ELSE 0 END) AS completed_explicit,
            SUM(CASE WHEN a.status = 'confirmed'
                        AND sl.end_time <  datetime('now', '+3 hours')    THEN 1 ELSE 0 END) AS completed_confirmed,
            SUM(CASE WHEN a.status = 'confirmed'
                        AND sl.end_time >= datetime('now', '+3 hours')    THEN 1 ELSE 0 END) AS upcoming,
            SUM(CASE WHEN a.status = 'pending'                            THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN a.status = 'cancelled'                          THEN 1 ELSE 0 END) AS cancelled,
            SUM(CASE WHEN a.status = 'rejected'                           THEN 1 ELSE 0 END) AS rejected,

            SUM(CASE WHEN a.status = 'completed'                          THEN 1
                        WHEN a.status = 'confirmed'
                        AND sl.end_time <  datetime('now', '+3 hours')    THEN 1
                                                                          ELSE 0 END) AS completed_total

        FROM {self.__tablename__} a
        JOIN users u ON a.client_id = u.user_id
        LEFT JOIN slots sl ON a.slot_id = sl.id
        GROUP BY
            u.user_id,
            u.username,
            u.first_name,
            u.last_name,
            u.is_admin,
            u.is_banned,
            u.contact
        ORDER BY completed_total DESC, u.user_id
        LIMIT ? OFFSET ?
        """

        self.cursor.execute(query, (per_page, pagination.offset))
        rows = self.cursor.fetchall()

        clients_with_stats: list[ClientWithStats] = []

        for row in rows:
            user = UserModel(
                user_id=row['user_id'],
                username=row['username'],
                first_name=row['first_name'],
                last_name=row['last_name'],
                is_admin=row['is_admin'],
                is_banned=row['is_banned'],
                contact=row['contact'],
            )

            completed = row['completed_explicit'] + row['completed_confirmed']

            stats = ClientStats(
                total=row['total'],
                completed=completed,
                upcoming=row['upcoming'],
                pending=row['pending'],
                cancelled=row['cancelled'],
                rejected=row['rejected'],
                first_appointment=(
                    datetime.fromisoformat(row['first_appointment']) if row['first_appointment'] else None
                ),
                last_appointment=(datetime.fromisoformat(row['last_appointment']) if row['last_appointment'] else None),
            )

            clients_with_stats.append(ClientWithStats(user=user, stats=stats))

        return clients_with_stats, pagination

    @staticmethod
    def cancel_appointment(app: AppointmentModel, status: str) -> bool:
        """
        Отменяет встречу и освобождает слот атомарно.

        Args:
            app (AppointmentModel): объект встречи
            status (str): статус, с которым будет отменена встреча

        Returns:
            bool: True если успешно отменено, False если встреча не найдена или уже отменена
        """

        conn = sqlite3.connect(DB_DIR)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute('BEGIN IMMEDIATE')

            app_db = AppointmentsTable(conn=conn)
            slots_db = SlotsTable(conn=conn)
            app_db._update_appointment_status(app.appointment_id, status)
            slots_db.set_slot_availability_no_commit(app.slot.id, True)

            # Фиксируем транзакцию
            conn.commit()
            return True

        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @property
    def valid_statuses(self):
        return self.__valid_statuses
