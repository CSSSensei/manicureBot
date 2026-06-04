
from DB.models import ServiceModel
from DB.tables.base import BaseTable
from DB.tables.service_schedule import ServiceScheduleTable


class ServicesTable(BaseTable):
    __tablename__ = 'services'

    def create_table(self):
        self.cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {self.__tablename__} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            duration INTEGER,
            price REAL,
            is_active BOOLEAN NOT NULL DEFAULT 1  -- В SQLite BOOLEAN как INTEGER (0/1)
        )''')
        self.conn.commit()
        self._log('CREATE_TABLE')

    def add_service(self, service: ServiceModel) -> int:
        query = f"""
        INSERT INTO {self.__tablename__} (name, description, duration, price)
        VALUES (?, ?, ?, ?)
        """
        self.cursor.execute(query, (service.name, service.description, service.duration, service.price))
        self._log('ADD_SERVICE', name=service.name, price=service.price)
        self.conn.commit()
        last_row_id = self.cursor.lastrowid
        with ServiceScheduleTable() as db:
            db.initialize_default_schedule(last_row_id)
        return last_row_id

    def get_active_services(self) -> list[ServiceModel]:
        query = f"SELECT * FROM {self.__tablename__} WHERE is_active = TRUE"
        self.cursor.execute(query)
        return [ServiceModel(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            duration=row['duration'],
            price=row['price'],
            is_active=bool(row['is_active'])
        ) for row in self.cursor]

    def get_all_services(self) -> list[ServiceModel]:
        query = f"SELECT * FROM {self.__tablename__}"
        self.cursor.execute(query)
        return [ServiceModel(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            duration=row['duration'],
            price=row['price'],
            is_active=bool(row['is_active'])
        ) for row in self.cursor]

    def get_service(self, service_id) -> ServiceModel | None:
        query = f"SELECT * FROM {self.__tablename__} WHERE id = ?"
        self.cursor.execute(query, (service_id,))
        row = self.cursor.fetchone()
        if not row:
            return None
        return ServiceModel(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            duration=row['duration'],
            price=row['price'],
            is_active=bool(row['is_active']))

    def toggle_service_active(self, service_id: int, is_active: bool) -> None:
        if not self._check_record_exists('services', 'id', service_id):
            raise ValueError(f"Service with id {service_id} not found")
        query = f"UPDATE {self.__tablename__} SET is_active = ? WHERE id = ?"
        self.cursor.execute(query, (int(is_active), service_id))
        self.conn.commit()
        self._log('TOGGLE_SERVICE_ACTIVE', service_id=service_id, is_active=is_active)

    def update_service(self, service: ServiceModel) -> None:
        if not self._check_record_exists(self.__tablename__, 'id', service.id):
            raise ValueError(f"Service with id {service.id} not found")

        query = f"""
        UPDATE {self.__tablename__}
        SET name = ?,
            description = ?,
            duration = ?,
            price = ?,
            is_active = ?
        WHERE id = ?
        """
        self.cursor.execute(query, (
            service.name,
            service.description,
            service.duration,
            service.price,
            int(service.is_active),
            service.id
        ))
        self.conn.commit()
        self._log('UPDATE_SERVICE', service_id=service.id)

    def service_name_exists(self, name: str, exclude_id: int = None) -> bool:
        clean_name = name.strip().lower()
        all_services = self.get_all_services()

        for service in all_services:
            if service.name.strip().lower() == clean_name:
                if exclude_id is not None and service.id == exclude_id:
                    continue
                return True
        return False


if __name__ == '__main__':
    with ServicesTable() as serv_db:
        serv_db.add_service(ServiceModel('однотон'))
        serv_db.add_service(ServiceModel('дизайн'))
