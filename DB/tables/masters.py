import sqlite3
from typing import List, Optional

from DB.models import Master
from DB.tables.base import BaseTable


class MastersTable(BaseTable):
    __tablename__ = 'masters'

    def create_table(self):
        """Создание таблицы masters"""
        self.cursor.executescript(f'''
        CREATE TABLE IF NOT EXISTS {self.__tablename__} (
            id INTEGER PRIMARY KEY,
            name TEXT,
            specialization TEXT,
            is_master BOOLEAN DEFAULT TRUE,
            message_id INTEGER,
            FOREIGN KEY (id) REFERENCES users(user_id) ON DELETE CASCADE
        )''')
        self.conn.commit()
        self._log('CREATE_TABLE')

    def set_master_status(self, user_id: int, is_master: bool = True) -> bool:
        """Устанавливает статус мастера для пользователя.

        Args:
            user_id: ID пользователя
            is_master: Флаг, является ли пользователь мастером маникюра

        Returns:
            True если статус успешно установлен, False если пользователь не существует
        """
        # Проверяем существование пользователя
        if not self._check_record_exists('users', 'user_id', user_id):
            self._log('SET_MASTER_FAILED', reason="User not found", user_id=user_id)
            return False

        try:
            query = '''
            INSERT OR REPLACE INTO masters (id, is_master)
            VALUES (?, ?)
            '''
            self.cursor.execute(query, (user_id, is_master))
            self.conn.commit()
            self._log('SET_MASTER_SUCCESS', user_id=user_id, is_master=is_master)
            return True
        except sqlite3.Error as e:
            self._log('SET_MASTER_ERROR', error=str(e), user_id=user_id)
            self.conn.rollback()
            return False

    def get_all_masters(self) -> List[Master]:
        query = f'''
        SELECT id, name, is_master
        FROM {self.__tablename__}
        WHERE is_master = TRUE
        '''

        try:
            self.cursor.execute(query)
            rows = self.cursor.fetchall()

            masters = []
            for row in rows:
                master = Master(
                    id=row['id'],
                    name=row['name'],
                    is_master=bool(row['is_master']))
                masters.append(master)
            return masters

        except sqlite3.Error as e:
            self._log('GET_ALL_MASTERS_ERROR', error=str(e))
            return []

    def get_message_id(self, master_id: int) -> Optional[int]:
        """Получает message_id для указанного мастера.

        Args:
            master_id: ID мастера

        Returns:
            int: message_id если найден, иначе None
        """
        query = f"""
            SELECT message_id FROM {self.__tablename__}
            WHERE id = ? AND is_master = TRUE
        """
        self.cursor.execute(query, (master_id,))
        row = self.cursor.fetchone()

        if row and row['message_id'] is not None:
            return row['message_id']
        return None

    def update_message_id(self, master_id: int, message_id: int) -> bool:
        """Обновляет message_id для указанного мастера.

        Args:
            master_id: ID мастера
            message_id: Новый message_id для установки

        Returns:
            bool: True если обновление прошло успешно, False если мастер не найден
        """
        # Проверяем существование мастера
        if not self._check_record_exists(self.__tablename__, 'id', master_id):
            self._log('UPDATE_MESSAGE_ID_FAILED', reason="Master not found", master_id=master_id)
            return False

        try:
            query = f"""
                UPDATE {self.__tablename__}
                SET message_id = ?
                WHERE id = ?
            """
            self.cursor.execute(query, (message_id, master_id))
            self.conn.commit()
            self._log('UPDATE_MESSAGE_ID_SUCCESS', master_id=master_id, message_id=message_id)
            return True
        except sqlite3.Error as e:
            self._log('UPDATE_MESSAGE_ID_ERROR', error=str(e), master_id=master_id)
            self.conn.rollback()
            return False


if __name__ == '__main__':
    with MastersTable() as masters_db:
        print(masters_db.get_all_masters())
