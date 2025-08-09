from datetime import datetime
from typing import List, Tuple
import subprocess
from aiogram import Bot
from aiogram.types import FSInputFile

from DB.tables.slots import SlotsTable
from config import const


def add_slots_from_list(slots: List[Tuple[datetime, datetime]]):
    added_slots = []
    not_added_slots = []
    with SlotsTable() as db:
        for start, end in slots:
            success, result = db.add_slot(start, end)
            if success:
                added_slots.append((result, start, end))
            else:
                not_added_slots.append((result, start, end))
    result_text = ''
    if added_slots:
        result_text += "✅ *Успешно добавлены слоты:*\n"
        for slot_id, start, end in added_slots:
            result_text += (
                f"• *{start.strftime('%d.%m.%Y')}* "
                f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')} "
                f"(ID: `{slot_id}`)\n"
            )
    if not_added_slots:
        result_text += "\n🚨 *Произошла ошибка при добавлении слотов:*\n"
        for error, start, end in not_added_slots:
            result_text += (
                f"• *{start.strftime('%d.%m.%Y')}* "
                f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')} "
                f"(Ошибка: `{error}`)\n"
            )
    return result_text


async def backup_db(bot: Bot):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        backup_path = const.BASE_DIR + f"/backups/z_users_{timestamp}.sql"

        with open(backup_path, 'w') as f:
            subprocess.run(["sqlite3", "z_users.db", ".dump"], stdout=f)

        subprocess.run(["gzip", backup_path])

        f = FSInputFile(f"{backup_path}.gz")
        await bot.send_document(const.ADMIN_ID, document=f, caption="🔧 Бэкап БД", disable_notification=True)

    except Exception as e:
        await bot.send_message(const.ADMIN_ID, f"❌ Ошибка бэкапа: {e}")
