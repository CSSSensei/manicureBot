from DB.models import PhotoModel
from DB.tables.base import BaseTable


class PhotosTable(BaseTable):
    __tablename__ = 'photos'

    def create_table(self):
        """Создание таблицы photos"""
        self.cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {self.__tablename__} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_file_id TEXT NOT NULL,
            file_unique_id TEXT NOT NULL,
            caption TEXT
        )""")
        self.conn.commit()
        self._log('CREATE_TABLE')

    def add_photo_no_commit(self, telegram_file_id: str, file_unique_id: str, caption: str | None = None) -> int:
        """Добавляет референсное фото и возвращает его ID.

        ⚠️ ВНИМАНИЕ: Этот метод НЕ выполняет коммит транзакции.
        Для сохранения изменений необходимо явно вызвать self.conn.commit()

        Returns:
            ID добавленной записи
        """
        query = f"""
        INSERT INTO {self.__tablename__} (telegram_file_id, file_unique_id, caption)
        VALUES (?, ?, ?)
        """
        self.cursor.execute(query, (telegram_file_id, file_unique_id, caption))
        self._log('ADD_PHOTO', file_unique_id=file_unique_id)
        return self.cursor.lastrowid

    def get_photo_by_id(self, photo_id: int) -> PhotoModel | None:
        query = f'SELECT * FROM {self.__tablename__} WHERE id = ?'
        self.cursor.execute(query, (photo_id,))
        row = self.cursor.fetchone()
        if row:
            return PhotoModel(**row) if row else None
        return None
