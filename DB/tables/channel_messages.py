from datetime import datetime, timedelta

from DB.models import ChannelMessage
from DB.tables.base import BaseTable


class ChannelMessagesTable(BaseTable):
    __tablename__ = 'channel_messages'

    def create_table(self) -> None:
        self.cursor.executescript(f"""
        CREATE TABLE IF NOT EXISTS {self.__tablename__} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id BIGINT NOT NULL,
            message_id INTEGER NOT NULL,
            message_type TEXT NOT NULL,
            last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            UNIQUE(channel_id, message_type)
        );

        CREATE INDEX IF NOT EXISTS idx_channel_messages_type ON {self.__tablename__}(message_type);
        CREATE INDEX IF NOT EXISTS idx_channel_messages_channel ON {self.__tablename__}(channel_id);
        """)
        self.conn.commit()
        self._log('CREATE_TABLE')

    def save_or_update_message(
            self,
            channel_id: int,
            message_id: int,
            message_type: str
    ) -> bool:
        try:
            query = f"""
            INSERT INTO {self.__tablename__} (channel_id, message_id, message_type)
            VALUES (?, ?, ?)
            ON CONFLICT(channel_id, message_type)
            DO UPDATE SET
                message_id = excluded.message_id,
                last_update = CURRENT_TIMESTAMP,
                is_active = TRUE
            """
            self.cursor.execute(query, (channel_id, message_id, message_type))
            self.conn.commit()
            return True
        except Exception as e:
            self._log('SAVE_CHANNEL_MESSAGE_ERROR', error=str(e))
            return False

    def get_message_info(
            self,
            channel_id: int,
            message_type: str
    ) -> ChannelMessage | None:
        query = f"""
        SELECT * FROM {self.__tablename__}
        WHERE channel_id = ? AND message_type = ? AND is_active = TRUE
        """
        self.cursor.execute(query, (channel_id, message_type))
        row = self.cursor.fetchone()

        if row:
            return ChannelMessage(
                id=row['id'],
                channel_id=row['channel_id'],
                message_id=row['message_id'],
                message_type=row['message_type'],
                last_update=datetime.fromisoformat(row['last_update']) + timedelta(hours=3),
                is_active=bool(row['is_active'])
            )
        return None

    def deactivate_message(
            self,
            channel_id: int,
            message_type: str
    ) -> bool:
        try:
            query = f"""
            UPDATE {self.__tablename__}
            SET is_active = FALSE
            WHERE channel_id = ? AND message_type = ?
            """
            self.cursor.execute(query, (channel_id, message_type))
            self.conn.commit()
            self._log('DEACTIVATE_CHANNEL_MESSAGE',
                      channel_id=channel_id,
                      message_type=message_type)
            return True
        except Exception as e:
            self._log('DEACTIVATE_CHANNEL_MESSAGE_ERROR', error=str(e))
            return False
