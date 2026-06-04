import subprocess
from collections import defaultdict
from datetime import datetime

from aiogram import Bot
from aiogram.types import FSInputFile

from bot.scheduler import SlotNotifierBot
from config import const
from DB import models
from DB.tables.slots import SlotsTable
from phrases import PHRASES_RU


async def add_slots_from_list(slots: list[tuple[datetime, datetime]]):
    added_slots = []
    not_added_slots = []
    with SlotsTable() as db:
        for start, end in slots:
            success, result = db.add_slot(start, end)
            if success:
                added_slots.append((result, start, end))
            else:
                not_added_slots.append((result, start, end))

    await SlotNotifierBot().update_channel_slots()
    result_text = ''
    if added_slots:
        added_by_date = defaultdict(list)
        for _slot_id, start, end in added_slots:
            date_key = start.date()
            added_by_date[date_key].append((start, end))

        sorted_dates = sorted(added_by_date.keys())

        result_text += "✅ <b>Успешно добавлены слоты:</b>\n\n"
        for date in sorted_dates:
            date_str = models.format_date(date)
            result_text += f"{date_str}\n"

            time_slots = sorted(added_by_date[date], key=lambda x: x[1])
            for start, end in time_slots:
                result_text += PHRASES_RU.replace('template.master.slot_time_range', start=start.strftime('%H:%M'), end=end.strftime('%H:%M'))

            result_text += "\n"

    if not_added_slots:
        not_added_by_date = defaultdict(list)
        for error, start, end in not_added_slots:
            date_key = start.date()
            not_added_by_date[date_key].append((error, start, end))

        sorted_dates = sorted(not_added_by_date.keys())

        result_text += "\n🚨 <b>Произошла ошибка при добавлении слотов:</b>\n\n"
        for date in sorted_dates:
            date_str = models.format_date(date)

            result_text += f"{date_str}\n"
            time_slots = sorted(not_added_by_date[date], key=lambda x: x[1])
            for error, start, end in time_slots:
                result_text += PHRASES_RU.replace('template.master.slot_time_range_with_error', start=start.strftime('%H:%M'), end=end.strftime('%H:%M'), error=error)

            result_text += "\n"

    return result_text


async def backup_db(bot: Bot):
    try:
        backups_dir = const.BASE_DIR / "backups"
        backups_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        backup_path = backups_dir / f"z_users_{timestamp}.sql"
        db_path = const.BASE_DIR / "DB/tables/z_users.db"

        if not db_path.exists():
            raise FileNotFoundError(f"Database file not found: {db_path}")

        integrity_check = subprocess.run(
            ["sqlite3", str(db_path), "PRAGMA integrity_check;"],
            capture_output=True, text=True
        )
        if "ok" not in integrity_check.stdout.lower():
            raise ValueError(f"Database integrity check failed: {integrity_check.stdout}")

        with open(backup_path, 'w') as f:
            subprocess.run(["sqlite3", str(db_path), ".dump"], stdout=f, check=True)

        subprocess.run(["gzip", str(backup_path)], check=True)
        if backup_path.exists():
            backup_path.unlink()

        await bot.send_document(
            const.ADMIN_ID,
            document=FSInputFile(f"{backup_path}.gz"),
            caption="🔧 Бэкап БД",
            disable_notification=True
        )

    except Exception as e:
        await bot.send_message(const.ADMIN_ID, f"❌ Ошибка бэкапа: {str(e)}")
