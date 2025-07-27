import inspect
import logging
import sys
from typing import List, Type, TypeVar, Set

from DB.tables.appointment_photos import AppointmentPhotosTable
from DB.tables.appointments import AppointmentsTable
from DB.tables.base import BaseTable
from DB.tables.photos import PhotosTable
from DB.tables.queries import QueriesTable
from DB.tables.services import ServicesTable
from DB.tables.slots import SlotsTable
from DB.tables.users import UsersTable
from DB.tables.masters import MastersTable


# logger = logging.getLogger(__name__)
#
# T = TypeVar('T', bound=BaseTable)
#
#
# def get_all_subclasses(cls: Type[T]) -> List[Type[T]]:
#     all_subclasses: Set[Type[T]] = set()
#
#     for module in list(sys.modules.values()):
#         if module is None:
#             continue
#         try:
#             for _, obj in inspect.getmembers(module):
#                 if (inspect.isclass(obj)
#                         and issubclass(obj, cls)
#                         and obj is not cls):
#                     all_subclasses.add(obj)
#         except Exception as e:
#             logger.debug(f"Ошибка при проверке модуля {module.__name__}: {e}")
#             continue
#     print(all_subclasses)
#     return list(all_subclasses)
#
#
# async def init_database():
#     for subclass in get_all_subclasses(BaseTable):
#         try:
#             with subclass() as table_instance:
#                 table_instance.create_table()
#         except Exception as e:
#             logger.error(f"Ошибка при создании таблицы {subclass.__name__}: {str(e)}")
#             raise


def init_database():
    with (UsersTable() as users_db,
          QueriesTable() as queries_db,
          SlotsTable() as slots_db,
          ServicesTable() as services_db,
          PhotosTable() as photos_db,
          AppointmentsTable() as appointments_db,
          AppointmentPhotosTable() as appointments_photos_db,
          MastersTable() as masters_db):
        users_db.create_table()
        queries_db.create_table()
        slots_db.create_table()
        services_db.create_table()
        photos_db.create_table()
        appointments_db.create_table()
        appointments_photos_db.create_table()
        masters_db.create_table()
