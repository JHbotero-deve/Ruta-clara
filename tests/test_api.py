import base64
import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import get_db
from src.models import Base
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


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "1.1.0"}


def test_user_registration_and_login():
    reg_payload = {
        "username": "testdriver",
        "email": "driver@example.com",
        "password": "Password123!"
    }
    res_reg = client.post("/register", json=reg_payload)
    assert res_reg.status_code == 201
    data = res_reg.json()
    assert data["username"] == "testdriver"
    assert "id" in data

    # Login
    login_data = {
        "username": "testdriver",
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
    assert res_me.json()["username"] == "testdriver"


def test_delivery_routes_crud():
    # Create route
    res_create = client.post("/delivery-routes", json={"name": "Ruta Envigado"})
    assert res_create.status_code == 201
    route_id = res_create.json()["id"]

    # List routes
    res_list = client.get("/delivery-routes")
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 1

    # Update route
    res_up = client.put(f"/delivery-routes/{route_id}", json={"name": "Ruta Envigado Tarde"})
    assert res_up.status_code == 200
    assert res_up.json()["name"] == "Ruta Envigado Tarde"

    # Delete route
    res_del = client.delete(f"/delivery-routes/{route_id}")
    assert res_del.status_code == 204


def test_locations_crud_and_optimal_route():
    # Create locations
    loc1 = {
        "name": "Parque Berrio",
        "latitude": 6.2492,
        "longitude": -75.5684,
        "address": "Calle 50 # 50-00"
    }
    loc2 = {
        "name": "Parque Poblado",
        "latitude": 6.2089,
        "longitude": -75.5678,
        "address": "Carrera 43A # 9-00"
    }
    r1 = client.post("/locations", json=loc1)
    r2 = client.post("/locations", json=loc2)
    assert r1.status_code == 201
    assert r2.status_code == 201

    loc1_id = r1.json()["id"]

    # Toggle delivered
    r_deliv = client.patch(f"/locations/{loc1_id}/delivered", json={"delivered": True})
    assert r_deliv.status_code == 200
    assert r_deliv.json()["delivered"] is True

    # Get locations
    r_get = client.get("/locations")
    assert r_get.status_code == 200
    assert len(r_get.json()) == 2

    # Get optimal route
    r_opt = client.get("/optimal_route")
    assert r_opt.status_code == 200
    assert len(r_opt.json()) == 2

    # Delete location
    r_del = client.delete(f"/locations/{loc1_id}")
    assert r_del.status_code == 204


def test_parse_delivery_label():
    label_text = (
        "Dirección: Carrera 43A # 1-50 Apto 402\n"
        "Distrito: El Poblado, Medellín\n"
        "Referencia: Torre 2 Apto 402\n"
        "Destinatario: Carlos Perez (TRACK123456)\n"
        "RESIDENCIAL"
    )
    res = client.post("/parse-delivery-label", json={"text": label_text})
    assert res.status_code == 200
    parsed = res.json()
    assert parsed["direccion"] == "Carrera 43A # 1-50 Apto 402"
    assert parsed["distrito"] == "El Poblado, Medellín"
    assert parsed["destinatario"] == "Carlos Perez"
    assert parsed["tracking_id"] == "TRACK123456"
    assert parsed["tipo"] == "Residencial"


def test_parse_delivery_label_without_optional_fields_or_accents():
    label_text = (
        "Direccion de entrega: Carrera 32B 10-110, Medellín\n"
        "Referencia: Vizcaya Real 2, 419\n"
        "Nombre del cliente: Lucrecia Inés Vasquez"
    )
    response = client.post("/parse-delivery-label", json={"text": label_text})
    assert response.status_code == 200
    parsed = response.json()
    assert parsed["direccion"] == "Carrera 32B 10-110, Medellín"
    assert parsed["distrito"] == ""
    assert parsed["referencia"] == "Vizcaya Real 2, 419"
    assert parsed["destinatario"] == "Lucrecia Inés Vasquez"


def test_parse_delivery_label_rejects_text_without_address():
    response = client.post(
        "/parse-delivery-label",
        json={"text": "Destinatario: Cliente de prueba\nReferencia: Torre 2"}
    )
    assert response.status_code == 422
    assert "dirección" in response.json()["detail"].lower()



def test_ocr_delivery_label_extracts_fields(monkeypatch):
    from src import routes
    monkeypatch.setattr(
        routes.pytesseract,
        "image_to_string",
        lambda image, lang, config: "DIRECCION: Carrera 43A # 1-50\nDESTINATARIO: Ana Perez\nBARRIO: El Poblado"
    )
    image = Image.new("RGB", (40, 40), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    response = client.post("/ocr-delivery-label", json={"image": "data:image/png;base64," + encoded})
    assert response.status_code == 200
    parsed = response.json()
    assert parsed["direccion"] == "Carrera 43A # 1-50"
    assert parsed["destinatario"] == "Ana Perez"
    assert parsed["distrito"] == "El Poblado"
    assert "texto_reconocido" in parsed


def test_address_number_tokens_must_match_exact_house_number():
    from src.routes import address_number_tokens_match
    query = "Carrera 66 #56A-98, El Paraíso, Bello"
    assert address_number_tokens_match(query, "Carrera 66 #56A-98, Bello")
    assert not address_number_tokens_match(query, "Carrera 66 #56A-97, Bello")
    assert not address_number_tokens_match(query, "Carrera 66, El Paraíso, Bello")


def test_clean_address_for_geocoding_preserves_colombian_nomenclature():
    from src.routes import clean_address_for_geocoding
    assert clean_address_for_geocoding("cra66#56a-98") == "Carrera 66 # 56a-98"


def test_parse_delivery_label_extracts_municipality_and_neighborhood():
    response = client.post(
        "/parse-delivery-label",
        json={"text": "Dirección: cra66#56A-98\nBarrio: El Paraíso\nCiudad: Bello"}
    )
    assert response.status_code == 200
    parsed = response.json()
    assert parsed["direccion"] == "cra66#56A-98"
    assert parsed["distrito"] == "El Paraíso"
    assert parsed["municipio"] == "Bello"


def test_arcgis_geocoder_rejects_candidates_from_other_municipalities(monkeypatch):
    import json
    from src import routes

    payload = {
        "candidates": [
            {
                "score": 99,
                "address": "Carrera 66, Envigado",
                "location": {"x": -75.57, "y": 6.17},
                "attributes": {"City": "Envigado", "Nbrhd": "El Paraíso", "Addr_type": "PointAddress"}
            },
            {
                "score": 98,
                "address": "Carrera 66 #56A-97, Bello",
                "location": {"x": -75.565, "y": 6.331},
                "attributes": {"City": "Bello", "Nbrhd": "El Paraíso", "Addr_type": "PointAddress", "LongLabel": "Carrera 66 #56A-97, El Paraíso, Bello"}
            },
            {
                "score": 95,
                "address": "Carrera 66 #56A-98, Bello",
                "location": {"x": -75.56, "y": 6.33},
                "attributes": {"City": "Bello", "Nbrhd": "El Paraíso", "Addr_type": "PointAddress", "LongLabel": "Carrera 66 #56A-98, El Paraíso, Bello"}
            }
        ]
    }

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def read(self):
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr(routes.urllib.request, "urlopen", lambda *args, **kwargs: FakeResponse())
    results = routes.query_arcgis_geocoder("Carrera 66 # 56A-98, El Paraíso", "Bello")
    assert len(results) == 1
    assert results[0]["municipality"] == "Bello"
    assert results[0]["neighborhood"] == "El Paraíso"
    assert results[0]["display_name"] == "Carrera 66 #56A-98, El Paraíso, Bello"
    assert results[0]["latitude"] == 6.33


def test_ocr_delivery_label_rejects_invalid_image():
    response = client.post("/ocr-delivery-label", json={"image": "not-base64"})
    assert response.status_code == 400


def test_road_route_returns_osrm_geometry_and_real_leg_distances(monkeypatch):
    import json
    from src import routes
    for name, lat, lon in [("Barbosa", 6.438, -75.331), ("Girardota", 6.377, -75.447)]:
        response = client.post("/locations", json={"name": name, "latitude": lat, "longitude": lon})
        assert response.status_code == 201
    payload = {"code": "Ok", "routes": [{"distance": 18400, "duration": 2100, "geometry": {"coordinates": [[-75.331, 6.438], [-75.39, 6.41], [-75.447, 6.377]]}, "legs": [{"distance": 18400, "duration": 2100}]}]}
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self): return json.dumps(payload).encode("utf-8")
    monkeypatch.setattr(routes.urllib.request, "urlopen", lambda *args, **kwargs: FakeResponse())
    response = client.get("/road_route")
    assert response.status_code == 200
    result = response.json()
    assert result["distance_m"] == 18400
    assert result["duration_s"] == 2100
    assert len(result["geometry"]) == 3
    assert len(result["legs"]) == 1
    assert len(result["stop_ids"]) == 2


def test_road_route_reports_unavailable_when_osrm_fails(monkeypatch):
    from src import routes
    for name, lat, lon in [("Punto 1", 6.2, -75.5), ("Punto 2", 6.3, -75.6)]:
        client.post("/locations", json={"name": name, "latitude": lat, "longitude": lon})
    def fail_request(*args, **kwargs):
        raise TimeoutError("OSRM timeout")
    monkeypatch.setattr(routes.urllib.request, "urlopen", fail_request)
    response = client.get("/road_route")
    assert response.status_code == 502
    assert "ruta vial" in response.json()["detail"].lower()
