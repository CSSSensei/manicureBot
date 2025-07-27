import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional

from DB.tables.base import BaseTable
from DB.models import UserModel, Pagination


class UsersTable(BaseTable):
    __tablename__ = 'users'

    def create_table(self):
        """Создание таблицы users"""
        self.cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {self.__tablename__} (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            is_admin BOOLEAN NOT NULL DEFAULT 0,
            is_banned BOOLEAN NOT NULL DEFAULT 0,
            phone_number TEXT,
            registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        self.conn.commit()
        self._log('CREATE_TABLE')

    def add_user(self, user: UserModel) -> UserModel:
        """Добавляет или обновляет пользователя"""
        existing_user = self.get_user(user.user_id)

        if existing_user:
            needs_update = (
                (existing_user.username != user.username and user.username)
                or (existing_user.first_name != user.first_name and user.first_name)
                or (existing_user.last_name != user.last_name and user.last_name)
            )

            if needs_update:
                self.cursor.execute(f'''
                    UPDATE {self.__tablename__} 
                    SET username = ?, first_name = ?, last_name = ?
                    WHERE user_id = ?''',
                                    (user.username, user.first_name, user.last_name, user.user_id))
                self.conn.commit()
                self._log('UPDATE_USER', user_id=user.user_id)
        else:
            self.cursor.execute(f'''
                INSERT INTO {self.__tablename__} (user_id, username, first_name, last_name, is_admin)
                VALUES (?, ?, ?, ?, ?)''',
                                (user.user_id, user.username, user.first_name, user.last_name, int(user.is_admin)))
            self.conn.commit()
            self._log('ADD_USER', user_id=user.user_id)

        return self.get_user(user.user_id)

    def is_exists(self, user_id: int) -> bool:
        self.cursor.execute(f'SELECT COUNT(*) FROM {self.__tablename__} WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone()[0] > 0

    def get_user(self, user_id: int) -> Optional[UserModel]:
        """Получение пользователя по ID"""
        self.cursor.execute(f'SELECT * FROM {self.__tablename__} WHERE user_id = ?', (user_id,))
        row = self.cursor.fetchone()
        if row:
            return UserModel(
                user_id=row['user_id'],
                username=row['username'],
                first_name=row['first_name'],
                last_name=row['last_name'],
                is_admin=bool(row['is_admin']),
                is_banned=bool(row['is_banned']),
                registration_date=(
                    datetime.fromisoformat(row['registration_date']) + timedelta(hours=3)
                    if row['registration_date']
                    else None
                ),
                phone_number=row['phone_number']
            )
        return None

    def update_user(self, user: UserModel) -> Optional[UserModel]:
        """Обновление информации о пользователе"""
        self.cursor.execute(f'''
        UPDATE {self.__tablename__} 
        SET username = ?, first_name = ?, last_name = ?, is_admin = ?
        WHERE user_id = ?''',
                            (user.username, user.first_name, user.last_name, int(user.is_admin), user.user_id))
        self.conn.commit()
        self._log('UPDATE_USER', user_id=user.user_id)
        return self.get_user(user.user_id)

    def delete_user(self, user_id: int) -> bool:
        """Удаление пользователя"""
        self.cursor.execute(f'DELETE FROM {self.__tablename__} WHERE user_id = ?', (user_id,))
        self.cursor.execute('DELETE FROM queries WHERE user_id = ?', (user_id,))
        self.conn.commit()
        deleted = self.cursor.rowcount > 0
        if deleted:
            self._log('DELETE_USER', user_id=user_id)
        return deleted

    def get_all_users(self, page: int = 1, per_page: int = 10) -> tuple[List[UserModel], Pagination]:
        """Получение пользователей с постраничной навигацией"""

        pagination = Pagination(
            page=page,
            per_page=per_page,
            total_items=0,  # Будет обновлено после запроса
            total_pages=0   # -//-
        )

        self.cursor.execute('''
            SELECT 
                u.user_id, u.username, u.first_name, u.last_name, 
                u.is_admin, u.is_banned, u.registration_date, u.phone_number,
                COUNT(q.query_id) as query_count
            FROM users u
            LEFT JOIN queries q ON u.user_id = q.user_id
            GROUP BY u.user_id
            ORDER BY u.registration_date DESC
            LIMIT ? OFFSET ?
        ''', (pagination.per_page, pagination.offset))

        users = [UserModel(
            user_id=row['user_id'],
            username=row['username'],
            first_name=row['first_name'],
            last_name=row['last_name'],
            is_admin=bool(row['is_admin']),
            is_banned=bool(row['is_banned']),
            registration_date=(
                datetime.fromisoformat(row['registration_date']) + timedelta(hours=3)
                if row['registration_date']
                else None),
            phone_number=row['phone_number'],
            query_count=row['query_count']
        ) for row in self.cursor]

        self.cursor.execute('SELECT COUNT(*) as total FROM users')
        total_users = self.cursor.fetchone()['total']

        pagination.total_items = total_users
        pagination.total_pages = (total_users + per_page - 1) // per_page

        return users, pagination

    def get_admins(self) -> List[UserModel]:
        """Получение администраторов"""
        self.cursor.execute(f'''
        SELECT * FROM {self.__tablename__} WHERE is_admin = 1''')
        return [UserModel(
            user_id=row['user_id'],
            username=row['username'],
            first_name=row['first_name'],
            last_name=row['last_name'],
            is_admin=True,
            is_banned=bool(row['is_banned']),
            registration_date=(
                datetime.fromisoformat(row['registration_date']) + timedelta(hours=3)
                if row['registration_date']
                else None
            ),
            phone_number=row['phone_number']
        ) for row in self.cursor]

    def set_admin(self, user_id: int, set_by: int, is_admin: bool = True) -> bool:
        """Установка прав администратора"""
        try:
            self.cursor.execute(f'SELECT 1 FROM {self.__tablename__} WHERE user_id = ?', (user_id,))
            if not self.cursor.fetchone():
                return False

            self.cursor.execute(
                f'UPDATE {self.__tablename__} SET is_admin = ? WHERE user_id = ?',
                (int(is_admin), user_id)
            )
            self.conn.commit()
            self._log('SET_ADMIN', user_id=user_id, is_admin=is_admin, set_by=set_by)
            return True
        except sqlite3.Error as e:
            self.conn.rollback()
            self._log('ERROR', error=str(e), action='SET_ADMIN')
            return False

    def set_ban_status(self, user_id: int, banned_by: int, ban: bool = True) -> bool:
        """
        Устанавливает или снимает блокировку пользователя

        :param user_id: ID пользователя
        :param banned_by: Кем заблокирован
        :param ban: True - заблокировать, False - разблокировать

        :return: True если операция успешна, False если пользователь не найден
        """
        try:
            self.cursor.execute(f'SELECT 1 FROM {self.__tablename__} WHERE user_id = ?', (user_id,))
            if not self.cursor.fetchone():
                return False

            self.cursor.execute(
                f'UPDATE {self.__tablename__} SET is_banned = ? WHERE user_id = ?',
                (int(ban), user_id)
            )
            self.conn.commit()

            action = 'BAN' if ban else 'UNBAN'
            log_details = {'user_id': user_id, 'status': ban, 'banned_by': banned_by}
            self._log(action, **log_details)

            return True

        except sqlite3.Error as e:
            self.conn.rollback()
            self._log('ERROR', error=str(e), action='SET_BAN_STATUS', user_id=user_id)
            return False

    def update_phone(self, user_id: int, phone: str) -> None:
        """Обновляет номер телефона клиента"""
        query = f"UPDATE {self.__tablename__} SET phone_number = ? WHERE user_id = ?"
        self.cursor.execute(query, (phone, user_id))
        self._log('UPDATE_CLIENT_PHONE', user_id=user_id, phone_number=phone)


if __name__ == '__main__':
    with UsersTable() as users_db:
        users_db.add_user(UserModel(1, 'fasdf', 'cvnbn', 'rqwerq'))
        users_row, info = users_db.get_all_users(1, 100)
        for user_unit in users_row:
            print(user_unit.__dict__)
        print(info.__dict__)
