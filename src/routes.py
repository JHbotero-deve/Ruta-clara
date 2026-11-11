import json
import csv
import os
from datetime import datetime
import urllib.parse
import urllib.request
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db
from src.auth import (
    authenticate_user,
    create_access_token,
    get_current_active_user,
    get_password_hash,
)
from src.models import (
    User,
    Location,
    Reference,
    UserCreate,
    UserResponse,
    LocationCreate,
    LocationResponse,
    ReferenceCreate,
    ReferenceResponse,
    Token,
)
from src.route_optimizer import calculate_optimal_route

router = APIRouter()

# =====================================================================
# Authentication & User Endpoints (Opcionales)
# =====================================================================

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.username == user_in.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    hashed_pw = get_password_hash(user_in.password)
    new_user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hashed_pw,
        disabled=user_in.disabled or False,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user


# =====================================================================
# Geocoding & Address / Building Scanner Endpoint
# =====================================================================

@router.get("/geocode", tags=["Geocoding"])
def search_address(query: str = Query(..., description="Dirección o nombre del edificio a buscar")):
    """Escanea y busca la latitud, longitud y dirección exacta de un edificio o calle."""
    query = query.strip()

    # 0. Reverse Geocoding si se reciben coordenadas "lat, lng"
    if "," in query:
        parts = [p.strip() for p in query.split(",")]
        if len(parts) == 2:
            try:
                lat_val = float(parts[0])
                lng_val = float(parts[1])
                url = f"https://nominatim.openstreetmap.org/reverse?lat={lat_val}&lon={lng_val}&format=json"
                req = urllib.request.Request(url, headers={"User-Agent": "RutaClaraDeliveryApp/2.0"})
                with urllib.request.urlopen(req, timeout=4) as response:
                    res_data = json.loads(response.read().decode())
                    if res_data and "display_name" in res_data:
                        return [{
                            "display_name": res_data.get("display_name"),
                            "latitude": lat_val,
                            "longitude": lng_val,
                            "type": "building",
                            "class": "place"
                        }]
            except Exception:
                pass

    def query_nominatim(q):
        try:
            encoded_query = urllib.parse.quote(q)
            url = f"https://nominatim.openstreetmap.org/search?q={encoded_query}&format=json&limit=5&addressdetails=1&countrycodes=co"
            req = urllib.request.Request(url, headers={"User-Agent": "RutaClaraDeliveryApp/2.0"})
            with urllib.request.urlopen(req, timeout=4) as response:
                return json.loads(response.read().decode())
        except Exception:
            return []

    # 1. Limpieza de caracteres y formato colombiano
    cleaned = query.replace("#", " ").replace("°", " ").replace("N°", " ").replace("No.", " ")
    cleaned = cleaned.replace("—", " ").replace("-", " ")
    cleaned = " ".join(cleaned.split())

    # 2. Búsquedas jerárquicas
    attempts = [
        f"{cleaned}, Colombia",
        f"{cleaned}, Medellín, Antioquia, Colombia",
        f"{cleaned}, Envigado, Antioquia, Colombia",
        f"{query}, Colombia"
    ]

    data = []
    for attempt in attempts:
        data = query_nominatim(attempt)
        if data:
            break

    if data:
        results = []
        for item in data:
            results.append({
                "display_name": item.get("display_name"),
                "latitude": float(item.get("lat")),
                "longitude": float(item.get("lon")),
                "type": item.get("type"),
                "class": item.get("class")
            })
        return results

    # 3. Fallback solo si no se encontró en OSM
    query_hash = sum(ord(c) for c in query) % 100
    lat_offset = (query_hash - 50) * 0.0001
    lng_offset = ((query_hash * 3) % 100 - 50) * 0.0001

    return [{
        "display_name": f"Dirección registrada: {query}",
        "latitude": 6.2442 + lat_offset,
        "longitude": -75.5812 + lng_offset,
        "type": "building",
        "class": "place"
    }]


LOG_FILE = "weekly_routes_log.csv"

def log_location_to_file(name: str, address: str, lat: float, lng: float):
    file_exists = os.path.isfile(LOG_FILE)
    try:
        with open(LOG_FILE, mode="a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Fecha/Hora", "Nombre/Referencia", "Dirección", "Latitud", "Longitud"])
            writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), name, address, lat, lng])
    except Exception as e:
        print("Error logging location to file:", e)


# =====================================================================
# Location Endpoints (Acceso Libre Sin Bloqueo de Token)
# =====================================================================

@router.get("/locations", response_model=List[LocationResponse])
def read_locations(db: Session = Depends(get_db)):
    locations = db.query(Location).all()
    return locations


@router.post("/locations", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
def create_location(
    location: LocationCreate,
    db: Session = Depends(get_db)
):
    db_location = Location(
        name=location.name,
        latitude=location.latitude,
        longitude=location.longitude,
        address=location.address,
    )
    db.add(db_location)
    db.commit()
    db.refresh(db_location)

    # Registrar automáticamente en archivo CSV para historial semanal
    log_location_to_file(location.name, location.address or "", location.latitude, location.longitude)

    return db_location


@router.delete("/locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_location(location_id: int, db: Session = Depends(get_db)):
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    db.delete(loc)
    db.commit()
    return None


@router.delete("/locations", status_code=status.HTTP_204_NO_CONTENT)
def clear_all_locations(db: Session = Depends(get_db)):
    db.query(Location).delete()
    db.commit()
    return None


@router.get("/export/weekly_routes")
def export_weekly_routes():
    if not os.path.isfile(LOG_FILE):
        with open(LOG_FILE, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Fecha/Hora", "Nombre/Referencia", "Dirección", "Latitud", "Longitud"])
    return FileResponse(path=LOG_FILE, filename="rutas_semana_registros.csv", media_type="text/csv")


# =====================================================================
# Reference Endpoints (Acceso Libre Sin Bloqueo de Token)
# =====================================================================

@router.get("/references", response_model=List[ReferenceResponse])
def read_references(db: Session = Depends(get_db)):
    references = db.query(Reference).all()
    return references


@router.post("/references", response_model=ReferenceResponse, status_code=status.HTTP_201_CREATED)
def create_reference(
    reference: ReferenceCreate,
    db: Session = Depends(get_db)
):
    # Verify location exists
    loc = db.query(Location).filter(Location.id == reference.location_id).first()
    if not loc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with id {reference.location_id} not found"
        )
    db_reference = Reference(
        description=reference.description,
        location_id=reference.location_id,
    )
    db.add(db_reference)
    db.commit()
    db.refresh(db_reference)
    return db_reference


# =====================================================================
# Route Optimization Endpoint (Acceso Libre Sin Bloqueo de Token)
# =====================================================================

@router.get("/optimal_route", response_model=List[LocationResponse])
def get_optimal_route(db: Session = Depends(get_db)):
    locations = db.query(Location).all()
    if not locations:
        return []
    optimal_route_list = calculate_optimal_route(locations)
    return optimal_route_list
