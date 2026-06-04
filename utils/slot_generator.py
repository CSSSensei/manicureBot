import logging
from datetime import date, datetime, timedelta

from DB.models import SlotModel
from DB.tables.day_schedule import DayScheduleTable
from DB.tables.schedule_settings import ScheduleSettingsTable
from DB.tables.slots import SlotsTable

logger = logging.getLogger(__name__)


class SlotGenerator:
    def __init__(self):
        self.day_schedule_db = DayScheduleTable()
        self.slots_db = SlotsTable()
        self.settings_db = ScheduleSettingsTable()

    def generate_slots_for_month(self, month: int, year: int) -> list[SlotModel]:
        schedules = self.day_schedule_db.get_all_schedules()
        added_slots = []

        today = datetime.now().date()
        first_day = date(year, month, 1)
        last_day = (date(year, month + 1, 1) - timedelta(days=1)
                    if month < 12 else date(year + 1, 1, 1) - timedelta(days=1))

        start_day = today + timedelta(days=1) if (today.year == year and today.month == month) else first_day

        current_day = start_day
        while current_day <= last_day:
            weekday = current_day.weekday()
            day_schedule = schedules.get(weekday)

            if day_schedule and day_schedule.is_working and day_schedule.time_slots:
                for start_time, end_time in day_schedule.time_slots:
                    start_datetime = datetime.combine(current_day, start_time)
                    end_datetime = datetime.combine(current_day, end_time)

                    if start_datetime > datetime.now():
                        added_slots.append(SlotModel(
                            start_time=start_datetime,
                            end_time=end_datetime,
                            is_available=True
                        ))

            current_day += timedelta(days=1)

        return added_slots

    def generate_slots_for_future_month(self, months_ahead: int = 1) -> int:
        """
        Генерирует слоты на месяц вперед от текущего
        months_ahead: 1 - следующий месяц, 2 - через месяц и т.д.
        """
        today = datetime.now()

        target_month = today.month + months_ahead
        target_year = today.year

        while target_month > 12:
            target_month -= 12
            target_year += 1

        setting_key = f"generated_{target_year}_{target_month}"
        already_generated = self.settings_db.get_setting(setting_key)

        if already_generated:
            return 0

        slots = self.generate_slots_for_month(target_month, target_year)
        added_count = 0

        for slot in slots:
            success, _ = self.slots_db.add_slot(slot.start_time, slot.end_time)
            if success:
                added_count += 1

        if added_count > 0:
            self.settings_db.set_setting(
                setting_key,
                "true",
                f"Слоты сгенерированы {datetime.now().isoformat()}"
            )

        return added_count

    def monthly_auto_generation(self) -> int:

        generated_count = self.generate_slots_for_future_month(months_ahead=1)

        if generated_count > 0:
            logger.info(f"Автогенерация: создано {generated_count} слотов на следующий месяц")

        return generated_count

    def generate_for_month_after_next(self):
        today = datetime.now()

        generated_count = self.generate_slots_for_future_month(months_ahead=2)

        if generated_count > 0:
            logger.info(f"Автогенерация: создано {generated_count} слотов на {today.month + 2} месяц")

        return generated_count
