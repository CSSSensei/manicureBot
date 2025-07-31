import pytest
from datetime import datetime, timedelta

from DB.models import ServiceModel, PhotoModel
from DB.tables.slots import SlotsTable
from DB.tables.services import ServicesTable
from DB.tables.photos import PhotosTable
from DB.tables.appointments import AppointmentsTable
from DB.tables.appointment_photos import AppointmentPhotosTable

# 📌 Тестовые данные
NOW = datetime.now()
START = NOW + timedelta(days=1)
END = START + timedelta(minutes=30)


@pytest.fixture(scope="module")
def dbs():
    with (
        SlotsTable() as slots_db,
        ServicesTable() as services_db,
        PhotosTable() as photos_db,
        AppointmentsTable() as appointments_db,
        AppointmentPhotosTable() as appointment_photos_db
    ):
        yield {
            'slots': slots_db,
            'services': services_db,
            'photos': photos_db,
            'appointments': appointments_db,
            'appointment_photos': appointment_photos_db
        }


def test_slots_table(dbs):
    slot_id = dbs['slots'].add_slot(START, END)
    assert isinstance(slot_id, int)

    available = dbs['slots'].get_available_slots()
    assert any(s.id == slot_id for s in available)

    dbs['slots'].set_slot_availability(slot_id)
    assert all(not s.is_available for s in dbs['slots'].get_available_slots())


def test_services_table(dbs):
    service = ServiceModel(name='Test Service', description='Desc', duration=30, price=100.0)
    service_id = dbs['services'].add_service(service)
    assert isinstance(service_id, int)

    active_services = dbs['services'].get_active_services()
    assert any(s.id == service_id for s in active_services)

    dbs['services'].toggle_service_active(service_id, False)
    active_services = dbs['services'].get_active_services()
    assert all(s.id != service_id for s in active_services)

    dbs['services'].toggle_service_active(service_id, True)
    active_services = dbs['services'].get_active_services()
    assert any(s.id == service_id for s in active_services)


def test_photos_table(dbs):
    photo_id = dbs['photos'].add_photo("tg_file_id_123", "unique_id_123", "Some caption")
    assert isinstance(photo_id, int)

    photo = dbs['photos'].get_photo_by_id(photo_id)
    assert isinstance(photo, PhotoModel)
    assert photo.telegram_file_id == "tg_file_id_123"


def test_appointments_and_photos_link(dbs):
    # Предполагается, что ID клиента уже есть в таблице users с user_id = 1
    # Если нет — добавить фиктивную запись в таблицу users вручную или мокнуть проверку _check_record_exists

    client_id = 1  # 🔁 заменить на существующего клиента в БД
    slot_id = dbs['slots'].add_slot(START + timedelta(hours=1), END + timedelta(hours=1))
    service = ServiceModel(name='Another', description='', duration=15, price=50.0)
    service_id = dbs['services'].add_service(service)

    appointment_id = dbs['appointments'].create_appointment(client_id, slot_id, service_id)
    assert isinstance(appointment_id, int)

    appointments = dbs['appointments'].get_client_appointments(client_id)
    assert any(a.id == appointment_id for a in appointments)

    dbs['appointments'].update_appointment_status(appointment_id, 'confirmed')
    updated = dbs['appointments'].get_client_appointments(client_id)
    updated_appt = next((a for a in updated if a.id == appointment_id), None)
    assert updated_appt.status == 'confirmed'

    # 📸 Добавление фото к записи
    photo_id = dbs['photos'].add_photo("tg_file_id_456", "unique_id_456", "Caption #2")
    added = dbs['appointment_photos'].add_photo_to_appointment(appointment_id, photo_id)
    assert added

    # Проверка фото, привязанных к записи
    photos = dbs['appointment_photos'].get_appointment_photos(appointment_id)
    assert any(p.id == photo_id for p in photos)
