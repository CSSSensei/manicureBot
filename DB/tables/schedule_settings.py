from DB.tables.base import BaseTable


class ScheduleSettingsTable(BaseTable):
    __tablename__ = 'schedule_settings'

    def create_table(self):
        self.cursor.executescript(f"""
        CREATE TABLE IF NOT EXISTS {self.__tablename__} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_name TEXT UNIQUE NOT NULL,
            setting_value TEXT NOT NULL,
            description TEXT
        );
        """)
        self.conn.commit()

    def get_setting(self, name: str, default: str = None) -> str:
        query = f"SELECT setting_value FROM {self.__tablename__} WHERE setting_name = ?"
        self.cursor.execute(query, (name,))
        row = self.cursor.fetchone()
        return row['setting_value'] if row else default

    def set_setting(self, name: str, value: str, description: str = None):
        query = f"""
        INSERT OR REPLACE INTO {self.__tablename__} 
        (setting_name, setting_value, description)
        VALUES (?, ?, ?)
        """
        self.cursor.execute(query, (name, value, description))
        self.conn.commit()
