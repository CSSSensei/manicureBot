from typing import List

from DB.models import PhotoModel
from DB.tables.base import BaseTable


class AppointmentPhotosTable(BaseTable):
    __tablename__ = 'appointment_photos'

    def create_table(self) -> None:
        """Создание таблицы appointment_photos с индексами"""
        self.cursor.executescript(f'''
        CREATE TABLE IF NOT EXISTS {self.__tablename__} (
            appointment_id INTEGER NOT NULL,
            photo_id INTEGER NOT NULL,
            PRIMARY KEY (appointment_id, photo_id),
            FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE,
            FOREIGN KEY (photo_id) REFERENCES photos(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_appointment_photos_appointment ON {self.__tablename__}(appointment_id);
        CREATE INDEX IF NOT EXISTS idx_appointment_photos_photo ON {self.__tablename__}(photo_id);
        ''')
        self.conn.commit()
        self._log('CREATE_TABLE')

    def add_photo_to_appointment(self, appointment_id: int, photo_id: int) -> bool:
        """Добавляет связь между записью и фото.
        Возвращает True, если связь была добавлена, False если уже существовала."""
        if not self._check_record_exists('appointments', 'id', appointment_id):
            raise ValueError(f"Appointment with id {appointment_id} not found")
        if not self._check_record_exists('photos', 'id', photo_id):
            raise ValueError(f"Photo with id {photo_id} not found")

        query = f"""
        INSERT OR IGNORE INTO {self.__tablename__} (appointment_id, photo_id)
        VALUES (?, ?)
        """
        self.cursor.execute(query, (appointment_id, photo_id))
        self.conn.commit()
        added = self.cursor.rowcount > 0
        self._log('ADD_PHOTO_TO_APPOINTMENT',
                  appointment_id=appointment_id,
                  photo_id=photo_id,
                  added=added)
        return added

    def get_appointment_photos(self, appointment_id: int) -> List[PhotoModel]:
        """Возвращает фото, связанные с записью."""
        query = f"""
        SELECT p.* 
        FROM {self.__tablename__} ap
        JOIN photos p ON ap.photo_id = p.id
        WHERE ap.appointment_id = ?
        """
        self.cursor.execute(query, (appointment_id,))
        return [PhotoModel(
            id=row['id'],
            telegram_file_id=row['telegram_file_id'],
            file_unique_id=row['file_unique_id'],
            caption=row['caption']
        ) for row in self.cursor]
