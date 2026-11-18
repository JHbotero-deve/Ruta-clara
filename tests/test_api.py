import base64
import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import get_db
from src.models import Base
from src.routes import GEOCODE_CACHE, address_number_tokens_match, clean_address_for_geocoding
from src.main import app

from sqlalchemy.pool import StaticPool

# In-memory SQLite DB for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def admin_headers():
    response = client.post("/register", json={"email": "jorgebotero190@gmail.com", "password": "Password123!"})
    assert response.status_code == 201, response.text
    token = client.post("/token", data={"username": "jorgebotero190@gmail.com", "password": "Password123!"})
    assert token.status_code == 200, token.text
    return {"Authorization": f"Bearer {token.json()['access_token']}"}


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "1.1.0"}


def test_user_registration_and_login():
    reg_payload = {
        "email": "jorgebotero190@gmail.com",
        "password": "Password123!"
    }
    res_reg = client.post("/register", json=reg_payload)
    assert res_reg.status_code == 201
    data = res_reg.json()
    assert data["email"] == "jorgebotero190@gmail.com"
    assert "id" in data

    # Login
    login_data = {
        "username": "jorgebotero190@gmail.com",
        "password": "Password123!"
    }
    res_login = client.post("/token", data=login_data)
    assert res_login.status_code == 200
    token_json = res_login.json()
    assert "access_token" in token_json
    assert token_json["token_type"] == "bearer"

    # Fetch user info
    headers = {"Authorization": f"Bearer {token_json['access_token']}"}
    res_me = client.get("/users/me", headers=headers)
    assert res_me.status_code == 200
    assert res_me.json()["email"] == "jorgebotero190@gmail.com"


def test_delivery_routes_crud():
    headers = admin_headers()
    # Create route
    res_create = client.post("/delivery-routes", json={"name": "Ruta Envigado"}, headers=headers)
    assert res_create.status_code == 201
    route_id = res_create.json()["id"]

    # List routes
    res_list = client.get("/delivery-routes", headers=headers)
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 1

    # Update route
    res_up = client.put(f"/delivery-routes/{route_id}", json={"name": "Ruta Envigado Tarde"}, headers=headers)
    assert res_up.status_code == 200
    assert res_up.json()["name"] == "Ruta Envigado Tarde"

    # Delete route
    res_del = client.delete(f"/delivery-routes/{route_id}", headers=headers)
    assert res_del.status_code == 204


def test_location_creation_does_not_require_manual_entrance_data():
    headers = admin_headers()
    response = client.post("/locations", json={
        "name": "Unidad reconocida por OCR",
        "latitude": 6.2,
        "longitude": -75.5,
        "address": "Carrera 43A #12-34",
        "municipality": "Envigado",
        "neighborhood": "San Marcos",
        "unit_number": "Torre 2 Apto 402",
        "location_source": "ocr_geocoded"
    }, headers=headers)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["name"] == "Unidad reconocida por OCR"
    assert saved["unit_number"] == "Torre 2 Apto 402"
    assert saved["entrance_name"] is None
    assert saved["entrance_confirmed"] is False


def test_locations_crud_and_optimal_route():
    headers = admin_headers()
    # Create locations
    loc1 = {
        "name": "Parque Berrio",
        "latitude": 6.2492,
        "longitude": -75.5684,
        "address": "Calle 50 # 50-00",
        "entrance_name": "Portería principal",
        "entrance_confirmed": True,
        "location_source": "manual_porteria",
        "client_id": "offline-delivery-001"
    }
    loc2 = {
        "name": "Parque Poblado",
        "latitude": 6.2089,
        "longitude": -75.5678,
        "address": "Carrera 43A # 9-00",
        "entrance_name": "Portería principal",
        "entrance_confirmed": True
    }
    r1 = client.post("/locations", json=loc1, headers=headers)
    r2 = client.post("/locations", json=loc2, headers=headers)
    assert r1.status_code == 201
    assert r1.json()["entrance_name"] == "Portería principal"
    assert r1.json()["entrance_confirmed"] is True
    assert r1.json()["location_source"] == "manual_porteria"
    assert r1.json()["client_id"] == "offline-delivery-001"
    duplicate = client.post("/locations", json=loc1, headers=headers)
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == r1.json()["id"]
    assert r2.status_code == 201

    loc1_id = r1.json()["id"]

    # Toggle delivered
    r_deliv = client.patch(f"/locations/{loc1_id}/delivered", json={"delivered": True}, headers=headers)
    assert r_deliv.status_code == 200
    assert r_deliv.json()["delivered"] is True

    # Get locations
    r_get = client.get("/locations", headers=headers)
    assert r_get.status_code == 200
    assert len(r_get.json()) == 2

    # Get optimal route
    r_opt = client.get("/optimal_route", headers=headers)
    assert r_opt.status_code == 200
    assert len(r_opt.json()) == 1
    assert r_opt.json()[0]["name"] == "Parque Poblado"

    # Delete location
    r_del = client.delete(f"/locations/{loc1_id}", headers=headers)
    assert r_del.status_code == 204


def test_parse_delivery_label():
    headers = admin_headers()
    label_text = (
        "Dirección: Carrera 43A # 1-50 Apto 402\n"
        "Distrito: El Poblado, Medellín\n"
        "Referencia: Torre 2 Apto 402\n"
        "Destinatario: Carlos Perez (TRACK123456)\n"
        "RESIDENCIAL"
    )
    res = client.post("/parse-delivery-label", json={"text": label_text}, headers=headers)
    assert res.status_code == 200
    parsed = res.json()
    assert parsed["direccion"] == "Carrera 43A #1-50"
    assert parsed["distrito"] == "El Poblado, Medellín"
    assert parsed["referencia"] == "Torre 2 Apto 402"
    assert not {"destinatario", "tracking_id", "texto_reconocido"} & parsed.keys()
    assert parsed["tipo"] == "Residencial"



def test_parser_handles_ocr_errors_and_excludes_private_fields():
    headers = admin_headers()
    label = (
        "MEDELLIN\nCOMERCIAL\n"
        "Dlreccion: Cerrera 36a40-70 apartemento 200 SN.\n"
        "Medellín\nDistrito: La Candelaria\n"
        "Destinaterio: Nombre Privado (TRACK-123)\n"
    )
    response = client.post("/parse-delivery-label", json={"text": label}, headers=headers)
    assert response.status_code == 200
    parsed = response.json()
    assert parsed["direccion"] == "Carrera 36A #40-70"
    assert parsed["referencia"].casefold() == "apartamento 200"
    assert parsed["municipio"] == "Medellín"
    assert parsed["distrito"] == "La Candelaria"
    assert parsed["tipo"] == "Comercial"
    assert not {"destinatario", "tracking_id", "texto_reconocido"} & parsed.keys()


def test_parser_keeps_only_address_reference_from_mixed_reference_line():
    headers = admin_headers()
    label = (
        "CABA\nMONSERRAT\nRESIDENCIAL\n"
        "Direccion: Calle Venezuela 50\n"
        "Referencia: Piso 11 dto 3 Rio Referencia: A nombre de Persona Privada\n"
        "Destinatario: Persona Privada (PABLO_123)\n"
    )
    parsed = client.post("/parse-delivery-label", json={"text": label}, headers=headers).json()
    assert parsed["direccion"] == "Calle Venezuela 50"
    assert parsed["referencia"] == "Piso 11 dto 3 Rio"
    assert parsed["municipio"] == "CABA"
    assert parsed["distrito"] == "Monserrat"
    assert not {"destinatario", "tracking_id", "texto_reconocido"} & parsed.keys()



def test_parser_ignores_qr_barcode_tracking_and_extracts_unit():
    headers = admin_headers()
    label = (
        "QR Code: https://tracking.example/ZXCV123456\n"
        "Código de barras: 7701234567890\n"
        "Tracking: ML-123456789\n"
        "Dirección: Carrera 43A # 12-34\n"
        "Municipio: Envigado\n"
        "Unidad: Torres del Parque 2\n"
        "Referencia: Torre 3 Apto 402\n"
        "Destinatario: Nombre Privado\n"
    )
    response = client.post("/parse-delivery-label", json={"text": label}, headers=headers)
    assert response.status_code == 200, response.text
    parsed = response.json()
    assert parsed["direccion"] == "Carrera 43A #12-34"
    assert parsed["municipio"] == "Envigado"
    assert parsed["unidad"] == "Torres del Parque 2"
    assert parsed["referencia"] == "Torre 3 Apto 402"
    assert not any(value in str(parsed) for value in ("ZXCV123456", "7701234567890", "ML-123456789", "Nombre Privado"))


def test_address_number_tokens_match_normalizes_leading_zeroes():
    assert address_number_tokens_match("Carrera 45A #32 Sur-04", "Carrera 45A 32 SUR 4, Envigado")
    assert not address_number_tokens_match("Carrera 45A #32 Sur-04", "Carrera 45A 32 SUR 40, Envigado")


def test_geocode_five_distinct_addresses(monkeypatch):
    addresses = [
        ("Calle 30 Sur 48-170, Envigado", "Envigado"),
        ("Carrera 42b #25 A-sur 41, Envigado", "Envigado"),
        ("Carrera 45a #32 sur-04, Envigado", "Envigado"),
        ("Carrera 42 14-74, Medellín", "Medellín"),
        ("Calle 50 # 50-00, Medellín", "Medellín")
    ]

    def fake_arcgis(search_text, requested_muni=None):
        return [{
            "display_name": search_text,
            "latitude": 6.2,
            "longitude": -75.5,
            "municipality": requested_muni or "",
            "neighborhood": "",
            "type": "PointAddress",
            "class": "arcgis",
            "score": 95
        }]

    monkeypatch.setattr("src.routes.query_arcgis_geocoder", fake_arcgis)
    GEOCODE_CACHE.clear()
    for address, municipality in addresses:
        response = client.get("/geocode", params={"query": address})
        assert response.status_code == 200, response.text
        data = response.json()
        assert data and data[0]["municipality"] == municipality
        assert 5.8 <= data[0]["latitude"] <= 6.6
        assert -75.9 <= data[0]["longitude"] <= -75.1


def test_ocr_delivery_label_scanner_with_eight_addresses():
    headers = admin_headers()
    from PIL import ImageDraw, ImageFont

    labels = [
        ("Envigado", "San Marcos", "Carrera 45A #32 Sur-04", "Enrique Aguirre", "Residencial"),
        ("Envigado", "Las Vegas", "Calle 30 Sur 48-170", "Manuela Gonzalez Lanzas", "Ref 1414"),
        ("Envigado", "Pontevedra", "Carrera 42B #25 A-Sur 41", "Angela Barrientos", "Unidad Ponte Vedra Apto 202"),
        ("Medellin", "El Poblado", "Calle 15 Sur #48-74", "Wilmer Alexi Pacheco Jimenez", "Primer piso TELESENTINEL"),
        ("Medellin", "El Poblado", "Calle 11 Sur #29E-115", "Nicolas Bonilla", "Saint Michel T2 1806 Torre 2"),
        ("Medellin", "El Poblado El Tesoro", "Calle 7 Sur #23-91", "Diana Ochoa", "Ed Cibeles Transversal Superior por ISAGEN"),
        ("Medellin", "El Poblado", "Calle 5 Sur #32-311", "Claudia Natalia Restrepo", "Apto 102"),
        ("Medellin", "El Poblado Vizcaya", "Carrera 32B 10-110", "Lucrecia Ines Vasquez Garces", "Vizcaya Real 2 - 419"),
    ]
    font = ImageFont.load_default(size=64)

    for municipality, neighborhood, address, recipient, reference in labels:
        image = Image.new("RGB", (2400, 760), "white")
        draw = ImageDraw.Draw(image)
        lines = [
            f"Direccion: {address}",
            f"Municipio: {municipality}",
            f"Barrio: {neighborhood}",
            f"Destinatario: {recipient}",
            f"Referencia: {reference}",
        ]
        for index, line in enumerate(lines):
            draw.text((70, 55 + index * 130), line, fill="black", font=font)

        image_buffer = io.BytesIO()
        image.save(image_buffer, format="PNG")
        encoded_image = base64.b64encode(image_buffer.getvalue()).decode("ascii")
        response = client.post("/ocr-delivery-label", json={"image": encoded_image}, headers=headers)

        assert response.status_code == 200, response.text
        parsed = response.json()
        assert parsed["direccion"].casefold().startswith(("calle", "carrera"))
        assert parsed["municipio"].casefold() == municipality.casefold()
        assert parsed["distrito"]
        assert not {"destinatario", "tracking_id", "texto_reconocido"} & parsed.keys()



def test_operator_scope_and_status_audit():
    admin = admin_headers()
    created = client.post("/admin/users", json={"username":"operador1","email":"operador@example.com","password":"Password123!"}, headers=admin)
    assert created.status_code == 201, created.text
    operator_login = client.post("/token", data={"username":"operador1","password":"Password123!"})
    operator = {"Authorization": f"Bearer {operator_login.json()['access_token']}"}
    own = client.post("/locations", json={"name":"Pedido propio","latitude":6.2,"longitude":-75.5,"address":"Calle 10 # 20-30","entrance_name":"Acceso principal","entrance_confirmed":True}, headers=operator)
    other = client.post("/locations", json={"name":"Pedido admin","latitude":6.21,"longitude":-75.51,"address":"Carrera 40 # 10-20","entrance_name":"Portería","entrance_confirmed":True}, headers=admin)
    assert own.status_code == 201 and other.status_code == 201
    assert own.json()["created_by_username"] == "operador1"
    assert own.json()["status"] == "pending"
    visible = client.get("/locations", headers=operator).json()
    assert [item["id"] for item in visible] == [own.json()["id"]]
    assert client.get(f"/locations/{other.json()['id']}/history", headers=operator).status_code == 403
    changed = client.patch(f"/locations/{own.json()['id']}/status", json={"status":"in_transit"}, headers=operator)
    assert changed.status_code == 200
    assert changed.json()["status"] == "in_transit"
    history = client.get(f"/locations/{own.json()['id']}/history", headers=admin)
    assert history.status_code == 200
    assert history.json()[0]["new_status"] == "in_transit"
    assert history.json()[0]["changed_by"] == "operador1"
    assert client.get("/admin/users", headers=operator).status_code == 403
    assert len(client.get("/locations", headers=admin).json()) == 2


def test_location_requires_confirmed_entrance():
    headers = admin_headers()
    response = client.post("/locations", json={"name":"Sin portería","latitude":6.2,"longitude":-75.5,"address":"Calle 10 # 20-30"}, headers=headers)
    assert response.status_code == 422
    assert "portería" in response.json()["detail"].lower()


def test_admin_can_create_all_three_roles_and_login_with_email():
    headers = admin_headers()
    for role, email in [("admin", "admin2@example.com"), ("operator", "operator2@example.com"), ("driver", "driver2@example.com")]:
        created = client.post("/admin/users", json={"email": email, "password": "ClaveFacil123", "role": role}, headers=headers)
        assert created.status_code == 201, created.text
        assert created.json()["role"] == role
        login = client.post("/token", data={"username": email, "password": "ClaveFacil123"})
        assert login.status_code == 200, login.text


def test_admin_assignment_driver_scope_and_dynamic_pending_route():
    admin = admin_headers()
    driver = client.post("/admin/users", json={"email":"repartidor@example.com","password":"Password123!","role":"driver"}, headers=admin)
    assert driver.status_code == 201, driver.text
    login = client.post("/token", data={"username":"repartidor@example.com","password":"Password123!"})
    driver_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    other_driver = client.post("/admin/users", json={"email":"otro@example.com","password":"Password123!","role":"driver"}, headers=admin)
    other_login = client.post("/token", data={"username":"otro@example.com","password":"Password123!"})
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
    payload = {"name":"Pedido asignado","latitude":6.2,"longitude":-75.5,"address":"Calle 10 #20-30","entrance_name":"Portería","entrance_confirmed":True}
    created = client.post("/locations", json=payload, headers=admin)
    assert created.status_code == 201, created.text
    assigned = client.patch(f"/locations/{created.json()['id']}/assign", json={"assigned_to_id":driver.json()["id"]}, headers=admin)
    assert assigned.status_code == 200
    assert assigned.json()["assigned_to_id"] == driver.json()["id"]
    assert len(client.get("/optimal_route", headers=driver_headers).json()) == 1
    assert client.get("/locations", headers=other_headers).json() == []
    assert client.get("/optimal_route", headers=other_headers).json() == []
    before_delivery = client.get("/admin/users/activity", headers=admin).json()
    driver_before = next(user for user in before_delivery["users"] if user["id"] == driver.json()["id"])
    assert driver_before["pending"] == 1
    assert driver_before["pending_orders"][0]["address"] == payload["address"]
    delivered = client.patch(f"/locations/{created.json()['id']}/delivered", json={"delivered":True}, headers=driver_headers)
    assert delivered.status_code == 200
    assert client.get("/optimal_route", headers=driver_headers).json() == []
    completed = client.get("/locations?status=delivered", headers=driver_headers)
    assert completed.status_code == 200 and len(completed.json()) == 1
    activity = client.get("/admin/users/activity", headers=admin)
    assert activity.status_code == 200
    driver_activity = next(user for user in activity.json()["users"] if user["id"] == driver.json()["id"])
    assert driver_activity["delivered"] == 1
    assert driver_activity["pending"] == 0


def test_public_registration_is_closed_after_first_account():
    headers = admin_headers()
    response = client.post("/register", json={"username":"intruso","password":"Password123!"})
    assert response.status_code == 403
    assert client.get("/admin/summary", headers=headers).status_code == 200


def test_ocr_delivery_label_rejects_invalid_image():
    headers = admin_headers()
    response = client.post("/ocr-delivery-label", json={"image": "not-base64"}, headers=headers)
    assert response.status_code == 400


def test_persistent_session_survives_requests_and_logout_revokes_it():
    registration = client.post("/register", json={"email": "jorgebotero190@gmail.com", "password": "Password123!"})
    assert registration.status_code == 201
    login = client.post("/token", data={"username": "jorgebotero190@gmail.com", "password": "Password123!"})
    second_login = client.post("/token", data={"username": "jorgebotero190@gmail.com", "password": "Password123!"})
    assert login.status_code == second_login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second_login.json()['access_token']}"}
    assert client.get("/users/me", headers=headers).status_code == 200
    assert client.get("/users/me", headers=headers).status_code == 200
    assert client.get("/users/me", headers=second_headers).status_code == 200
    logout = client.post("/logout", headers=headers)
    assert logout.status_code == 204
    assert client.get("/users/me", headers=headers).status_code == 401
    assert client.get("/users/me", headers=second_headers).status_code == 200


def test_delivery_route_pdf_export_and_driver_permissions():
    admin = admin_headers()
    driver_response = client.post("/admin/users", json={
        "username": "domiciliario_pdf",
        "email": "domiciliario_pdf@example.com",
        "password": "Password123!",
        "role": "driver"
    }, headers=admin)
    assert driver_response.status_code == 201, driver_response.text
    driver_id = driver_response.json()["id"]

    route_response = client.post("/delivery-routes", json={"name": "Ruta PDF Envigado"}, headers=admin)
    assert route_response.status_code == 201, route_response.text
    route_id = route_response.json()["id"]

    location_response = client.post("/locations", json={
        "name": "Unidad de prueba",
        "address": "Carrera 43A # 12-34",
        "municipality": "Envigado",
        "neighborhood": "El Dorado",
        "unit_number": "Torre 2 Apto 301",
        "entrance_name": "Portería principal",
        "entrance_confirmed": True,
        "latitude": 6.1700,
        "longitude": -75.5800,
        "route_id": route_id
    }, headers=admin)
    assert location_response.status_code == 201, location_response.text
    location_id = location_response.json()["id"]
    assigned = client.patch(f"/locations/{location_id}/assign", json={"assigned_to_id": driver_id}, headers=admin)
    assert assigned.status_code == 200, assigned.text

    admin_report = client.get(f"/export/delivery-route.pdf?route_id={route_id}&driver_id={driver_id}", headers=admin)
    assert admin_report.status_code == 200
    assert admin_report.headers["content-type"].startswith("application/pdf")
    assert admin_report.content.startswith(b"%PDF")
    admin_sheet = client.get(f"/export/delivery-route.xlsx?route_id={route_id}&driver_id={driver_id}", headers=admin)
    assert admin_sheet.status_code == 200
    assert admin_sheet.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert admin_sheet.content.startswith(b"PK")
    from openpyxl import load_workbook
    workbook = load_workbook(io.BytesIO(admin_sheet.content))
    sheet = workbook["Recorrido"]
    assert sheet["A1"].value == "REPORTE DE RECORRIDO"
    assert sheet["A7"].value == "N.º"
    assert sheet["C8"].value == "Carrera 43A # 12-34"
    assert len(sheet._images) == 1

    login = client.post("/token", data={"username": "domiciliario_pdf@example.com", "password": "Password123!"})
    assert login.status_code == 200
    driver_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    driver_report = client.get(f"/export/delivery-route.pdf?route_id={route_id}", headers=driver_headers)
    assert driver_report.status_code == 200
    assert driver_report.content.startswith(b"%PDF")
    driver_sheet = client.get(f"/export/delivery-route.xlsx?route_id={route_id}", headers=driver_headers)
    assert driver_sheet.status_code == 200
    assert driver_sheet.content.startswith(b"PK")

    forbidden = client.get(f"/export/delivery-route.pdf?route_id={route_id}&driver_id={driver_id + 100}", headers=driver_headers)
    assert forbidden.status_code == 403
    forbidden_sheet = client.get(f"/export/delivery-route.xlsx?route_id={route_id}&driver_id={driver_id + 100}", headers=driver_headers)
    assert forbidden_sheet.status_code == 403


def test_map_taps_cannot_create_delivery_stops():
    from pathlib import Path
    html = Path("index.html").read_text(encoding="utf-8")
    map_start = html.index("function initMap()")
    map_end = html.index("function loadDeliveryRoutes()", map_start)
    map_initialization = html[map_start:map_end]
    assert "map.on('click'" not in map_initialization
    assert "map.on(\"click\"" not in map_initialization
    assert "doubleClickZoom: false" in map_initialization
    assert "saveLocationAutomatically" not in map_initialization
    assert "captureContinuousStop" not in html




def test_colombian_street_abbreviations_are_normalized():
    assert clean_address_for_geocoding("CRA 45 # 20-15").startswith("Carrera 45")
    assert clean_address_for_geocoding("Carrera 45 # 20-15").startswith("Carrera 45")
    assert clean_address_for_geocoding("CL 30 # 10-25").startswith("Calle 30")
    assert clean_address_for_geocoding("Calle 30 # 10-25").startswith("Calle 30")


def test_driver_loses_access_after_reassignment_and_cannot_delete_or_cancel():
    admin = admin_headers()
    first = client.post("/admin/users", json={"email":"first-driver@example.com","password":"Password123!","role":"driver"}, headers=admin)
    second = client.post("/admin/users", json={"email":"second-driver@example.com","password":"Password123!","role":"driver"}, headers=admin)
    first_login = client.post("/token", data={"username":"first-driver@example.com","password":"Password123!"})
    first_headers = {"Authorization": f"Bearer {first_login.json()['access_token']}"}
    payload = {"name":"Pedido de prueba","latitude":6.2,"longitude":-75.5,"address":"Calle 10 #20-30","entrance_name":"Portería","entrance_confirmed":True,"client_id":"driver-sync-reassigned"}
    created = client.post("/locations", json=payload, headers=first_headers)
    assert created.status_code == 201, created.text
    location_id = created.json()["id"]
    reassigned = client.patch(f"/locations/{location_id}/assign", json={"assigned_to_id":second.json()["id"]}, headers=admin)
    assert reassigned.status_code == 200
    assert client.get("/locations", headers=first_headers).json() == []
    assert client.post("/locations", json=payload, headers=first_headers).status_code == 403
    assert client.get(f"/locations/{location_id}/history", headers=first_headers).status_code == 403
    assert client.patch(f"/locations/{location_id}", json={"name":"Cambio indebido","address":"Otra dirección"}, headers=first_headers).status_code == 403
    assert client.patch(f"/locations/{location_id}/status", json={"status":"cancelled"}, headers=first_headers).status_code == 403
    assert client.delete(f"/locations/{location_id}", headers=first_headers).status_code == 403
    assert client.delete("/locations", headers=first_headers).status_code == 403


def test_driver_cannot_reopen_or_change_final_delivery():
    admin = admin_headers()
    driver = client.post("/admin/users", json={"email":"delivery-driver@example.com","password":"Password123!","role":"driver"}, headers=admin)
    login = client.post("/token", data={"username":"delivery-driver@example.com","password":"Password123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    payload = {"name":"Entrega finalizada","latitude":6.2,"longitude":-75.5,"address":"Carrera 40 #10-20","entrance_name":"Acceso","entrance_confirmed":True}
    assert client.post("/locations", json={**payload,"delivered":True}, headers=admin).status_code == 422
    created = client.post("/locations", json=payload, headers=admin)
    assigned = client.patch(f"/locations/{created.json()['id']}/assign", json={"assigned_to_id":driver.json()["id"]}, headers=admin)
    location_id = assigned.json()["id"]
    delivered = client.patch(f"/locations/{location_id}/delivered", json={"delivered":True}, headers=headers)
    assert delivered.status_code == 200
    assert client.patch(f"/locations/{location_id}/assign", json={"assigned_to_id":driver.json()["id"]}, headers=admin).status_code == 409
    assert client.patch(f"/locations/{location_id}/delivered", json={"delivered":False}, headers=headers).status_code == 403
    assert client.patch(f"/locations/{location_id}/status", json={"status":"issue"}, headers=headers).status_code == 409


def test_driver_cannot_mark_cancelled_order_as_delivered():
    admin = admin_headers()
    driver = client.post("/admin/users", json={"email":"cancelled-driver@example.com","password":"Password123!","role":"driver"}, headers=admin)
    login = client.post("/token", data={"username":"cancelled-driver@example.com","password":"Password123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    payload = {"name":"Pedido cancelado","latitude":6.2,"longitude":-75.5,"address":"Calle 20 #30-40","entrance_name":"Acceso","entrance_confirmed":True}
    created = client.post("/locations", json=payload, headers=admin)
    location_id = created.json()["id"]
    assert client.patch(f"/locations/{location_id}/assign", json={"assigned_to_id":driver.json()["id"]}, headers=admin).status_code == 200
    assert client.patch(f"/locations/{location_id}/status", json={"status":"cancelled"}, headers=admin).status_code == 200
    assert client.patch(f"/locations/{location_id}/delivered", json={"delivered":True}, headers=headers).status_code == 409


def test_parser_selects_recipient_address_instead_of_sender_address():
    headers = admin_headers()
    label = (
        "REMITENTE\n"
        "Nombre: Empresa de origen\n"
        "Dirección: Calle 10 #20-30\n"
        "Municipio: Bello\n"
        "DESTINATARIO\n"
        "Nombre: Persona privada\n"
        "Dirección: Carrera 45A #32 Sur-04\n"
        "Municipio: Envigado\n"
        "Barrio: San Marcos\n"
        "Referencia: Torre 2 Apto 402\n"
    )
    response = client.post("/parse-delivery-label", json={"text":label}, headers=headers)
    assert response.status_code == 200, response.text
    parsed = response.json()
    assert parsed["direccion"] == "Carrera 45A #32 Sur-04"
    assert parsed["municipio"] == "Envigado"
    assert parsed["distrito"] == "San Marcos"
    assert parsed["referencia"] == "Torre 2 Apto 402"
    assert "Bello" not in str(parsed)
    assert "Persona privada" not in str(parsed)


def test_parser_does_not_use_sender_address_when_recipient_is_missing():
    headers = admin_headers()
    label = "REMITENTE\nNombre: Empresa\nDirección: Calle 10 #20-30\nMunicipio: Bello"
    response = client.post("/parse-delivery-label", json={"text":label}, headers=headers)
    assert response.status_code == 422
