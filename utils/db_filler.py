from datetime import datetime
from typing import List, Tuple

from DB.tables.slots import SlotsTable


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
