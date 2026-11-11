import unicodedata

import os
import json
import csv
import time
import sqlite3
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import List

from fastapi import (
    APIRouter, Depends, HTTPException, Query, status
)
from fastapi.responses import Response, FileResponse
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
    User, Location, Reference,
    UserCreate, UserResponse,
    LocationCreate, LocationResponse,
    ReferenceCreate, ReferenceResponse,
    Token,
)
from src.route_optimizer import calculate_optimal_route


router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
MAP_FILE = STATIC_DIR / "offline" / "valle_aburra.mbtiles"
LOG_FILE = BASE_DIR / "weekly_routes_log.csv"

GEOCODE_CACHE = {}
GEOCODE_LAST_REQUEST = 0.0


# ============================================================
# MBTILES: MAPA OFFLINE DEL VALLE DE ABURRA
# ============================================================

def get_mbtiles_connection():
    if not MAP_FILE.is_file():
        raise HTTPException(
            status_code=503,
            detail="No se encuentra el mapa offline. Instala valle_aburra.mbtiles."
        )

    connection = sqlite3.connect(
        f"file:{MAP_FILE.as_posix()}?mode=ro",
        uri=True,
        timeout=10
    )
    return connection


@router.get("/tiles/{z}/{x}/{y}.png", tags=["Offline Map"])
def get_offline_tile(z: int, x: int, y: int):
    """
    Entrega mosaicos PNG desde MBTiles.
    Leaflet utiliza coordenadas XYZ; MBTiles almacena filas TMS.
    """

    if z < 0 or z > 22:
        raise HTTPException(status_code=404, detail="Zoom inválido")

    tile_count = 1 << z

    if x < 0 or y < 0 or x >= tile_count or y >= tile_count:
        raise HTTPException(status_code=404, detail="Mosaico fuera de rango")

    # Conversión XYZ -> TMS
    tms_y = tile_count - 1 - y

    connection = None

    try:
        connection = get_mbtiles_connection()

        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT tile_data
            FROM tiles
            WHERE zoom_level = ?
              AND tile_column = ?
              AND tile_row = ?
            LIMIT 1
            """,
            (z, x, tms_y)
        )

        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Mosaico no disponible en el mapa descargado"
            )

        return Response(
            content=row[0],
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=31536000, immutable"
            }
        )

    except HTTPException:
        raise
    except sqlite3.Error as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error leyendo MBTiles: {str(error)}"
        )
    finally:
        if connection:
            connection.close()


@router.get("/offline-map/status", tags=["Offline Map"])
def offline_map_status():
    """
    Informa si el mapa offline está instalado y cuántos mosaicos contiene.
    """

    if not MAP_FILE.is_file():
        return {
            "installed": False,
            "message": "Mapa offline no instalado"
        }

    connection = get_mbtiles_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("SELECT COUNT(*) FROM tiles")
        total_tiles = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT MIN(zoom_level), MAX(zoom_level)
            FROM tiles
            """
        )
        zooms = cursor.fetchone()

        cursor.execute(
            """
            SELECT name, value
            FROM metadata
            """
        )
        metadata = dict(cursor.fetchall())

        return {
            "installed": True,
            "file": MAP_FILE.name,
            "size_mb": round(MAP_FILE.stat().st_size / 1048576, 2),
            "total_tiles": total_tiles,
            "min_zoom": zooms[0],
            "max_zoom": zooms[1],
            "name": metadata.get("name", "Valle de Aburrá"),
            "format": metadata.get("format", "png")
        }
    finally:
        connection.close()


# ============================================================
# AUTHENTICATION
# ============================================================

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):

    existing_user = (
        db.query(User)
        .filter(User.username == user_in.username)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username already registered"
        )

    new_user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        disabled=user_in.disabled or False
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
    user = authenticate_user(
        db,
        form_data.username,
        form_data.password
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = create_access_token(data={"sub": user.username})

    return {
        "access_token": token,
        "token_type": "bearer"
    }


@router.get("/users/me", response_model=UserResponse)
def read_users_me(
    current_user: User = Depends(get_current_active_user)
):
    return current_user


# ============================================================
# GEOCODING ONLINE
# ============================================================

@router.get("/geocode", tags=["Geocoding"])
def search_address(query: str = Query(..., min_length=3)):
    """Busca direcciones colombianas usando Nominatim y Photon."""

    global GEOCODE_LAST_REQUEST

    raw_query = " ".join(query.strip().split())

    if not raw_query:
        raise HTTPException(status_code=400, detail="Dirección vacía")

    cache_key = raw_query.casefold()

    if cache_key in GEOCODE_CACHE:
        return GEOCODE_CACHE[cache_key]

    def normalize_result(item):
        address = item.get("address", {})

        municipality = (
            address.get("city")
            or address.get("town")
            or address.get("municipality")
            or address.get("county")
            or ""
        )

        neighborhood = (
            address.get("suburb")
            or address.get("neighbourhood")
            or address.get("quarter")
            or ""
        )

        return {
            "display_name": item.get("display_name", ""),
            "latitude": float(item["lat"]),
            "longitude": float(item["lon"]),
            "municipality": municipality,
            "neighborhood": neighborhood,
            "type": item.get("type", ""),
            "class": item.get("class", "")
        }

    def normalize_photon(feature):
        properties = feature.get("properties", {})
        coordinates = feature.get("geometry", {}).get("coordinates", [])

        if len(coordinates) < 2:
            return None

        municipality = (
            properties.get("city")
            or properties.get("town")
            or properties.get("county")
            or properties.get("locality")
            or ""
        )

        neighborhood = (
            properties.get("district")
            or properties.get("suburb")
            or properties.get("neighbourhood")
            or ""
        )

        name = properties.get("name", "")
        street = properties.get("street", "")
        number = properties.get("housenumber", "")
        postcode = properties.get("postcode", "")
        state = properties.get("state", "")
        country = properties.get("country", "Colombia")

        display = ", ".join(
            str(value) for value in [
                name, street, number, neighborhood,
                municipality, state, postcode, country
            ] if value
        )

        return {
            "display_name": display,
            "latitude": float(coordinates[1]),
            "longitude": float(coordinates[0]),
            "municipality": municipality,
            "neighborhood": neighborhood,
            "type": properties.get("type", ""),
            "class": "photon"
        }

    # Variantes de búsqueda para direcciones del Valle de Aburrá.
    attempts = [
        raw_query,
        f"{raw_query}, Medellín, Antioquia, Colombia",
        f"{raw_query}, Antioquia, Colombia",
        f"{raw_query}, Colombia"
    ]

    attempts = list(dict.fromkeys(attempts))
    results = []

    # Primera fuente: Nominatim.
    for search in attempts:
        elapsed = time.monotonic() - GEOCODE_LAST_REQUEST

        if elapsed < 1.1:
            time.sleep(1.1 - elapsed)

        params = urllib.parse.urlencode({
            "q": search,
            "format": "jsonv2",
            "limit": 5,
            "addressdetails": 1,
            "countrycodes": "co",
            "accept-language": "es"
        })

        url = "https://nominatim.openstreetmap.org/search?" + params

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "RutaClaraDeliveryApp/3.1"
            }
        )

        try:
            GEOCODE_LAST_REQUEST = time.monotonic()

            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))

            if data:
                results = [
                    normalize_result(item)
                    for item in data
                    if item.get("lat") and item.get("lon")
                ]

            if results:
                break

        except Exception:
            continue

    # Segunda fuente: Photon, si Nominatim no encuentra resultados.
    if not results:
        photon_query = raw_query

        if "colombia" not in photon_query.casefold():
            photon_query += ", Medellín, Antioquia, Colombia"

        params = urllib.parse.urlencode({
            "q": photon_query,
            "limit": 5,
            "lang": "es"
        })

        url = "https://photon.komoot.io/api/?" + params

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "RutaClaraDeliveryApp/3.1"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))

            for feature in data.get("features", []):
                result = normalize_photon(feature)

                if result:
                    results.append(result)

        except Exception:
            pass



    # ARCGIS FALLBACK RUTA CLARA
    # Priorizar el municipio solicitado y evitar resultados lejanos.
    if not results:
        try:
            import re

            municipalities = [
                "Medellín", "Envigado", "Sabaneta", "Itagüí",
                "La Estrella", "Caldas", "Bello",
                "Copacabana", "Girardota", "Barbosa"
            ]

            normalized = raw_query.casefold()
            requested = next(
                (m for m in municipalities if m.casefold() in normalized),
                None
            )

            searches = []

            if requested:
                searches.append(f"{raw_query}, {requested}, Antioquia, Colombia")
            else:
                searches.append(f"{raw_query}, Valle de Aburrá, Antioquia, Colombia")

            for search_text in searches:
                params = urllib.parse.urlencode({
                    "SingleLine": search_text,
                    "f": "json",
                    "outFields": "*",
                    "maxLocations": 5,
                    "outSR": 4326,
                    "countryCode": "COL"
                })

                url = (
                    "https://geocode.arcgis.com/arcgis/rest/services/"
                    "World/GeocodeServer/findAddressCandidates?"
                    + params
                )

                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "RutaClaraDeliveryApp/4.1"}
                )

                with urllib.request.urlopen(req, timeout=8) as response:
                    data = json.loads(response.read().decode("utf-8"))

                for candidate in data.get("candidates", []):
                    if candidate.get("score", 0) < 75:
                        continue

                    point = candidate.get("location", {})
                    attrs = candidate.get("attributes", {})

                    if "x" not in point or "y" not in point:
                        continue

                    municipality = (
                        attrs.get("City")
                        or attrs.get("Subregion")
                        or ""
                    )

                    # Validar municipio cuando el usuario lo especifica.
                    if requested:
                        def normalize_name(value):
                            value = unicodedata.normalize(
                                "NFKD", str(value or "").casefold().strip()
                            )
                            return "".join(
                                char for char in value
                                if not unicodedata.combining(char)
                            )

                        if normalize_name(municipality) != normalize_name(requested):
                            continue

                    lat = float(point["y"])
                    lon = float(point["x"])

                    # Delimitar aproximadamente el Valle de Aburrá.
                    if not (6.0 <= lat <= 6.55 and -75.75 <= lon <= -75.25):
                        continue

                    results.append({
                        "display_name": (
                            attrs.get("LongLabel")
                            or candidate.get("address")
                        ),
                        "latitude": lat,
                        "longitude": lon,
                        "municipality": municipality,
                        "neighborhood": (
                            attrs.get("Nbrhd")
                            or attrs.get("District")
                            or ""
                        ),
                        "type": attrs.get("Addr_type", ""),
                        "class": "arcgis",
                        "score": candidate.get("score")
                    })

                if results:
                    break

        except Exception as error:
            print(f"Error de ArcGIS: {error}")

    if not results:
        raise HTTPException(
            status_code=404,
            detail=(
                "No se encontró la dirección. "
                "Intente agregar barrio, municipio y departamento."
            )
        )

    if len(GEOCODE_CACHE) > 500:
        GEOCODE_CACHE.clear()

    GEOCODE_CACHE[cache_key] = results

    return results




# ============================================================
# WEEKLY CSV HISTORY
# ============================================================

def log_location_to_file(
    name: str,
    address: str,
    lat: float,
    lng: float
):
    file_exists = LOG_FILE.is_file()

    try:
        with open(
            LOG_FILE,
            mode="a",
            encoding="utf-8-sig",
            newline=""
        ) as file:

            writer = csv.writer(file)

            if not file_exists:
                writer.writerow([
                    "Fecha/Hora",
                    "Nombre/Referencia",
                    "Dirección",
                    "Latitud",
                    "Longitud"
                ])

            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                name,
                address,
                lat,
                lng
            ])

    except OSError as error:
        print("Error CSV:", error)


# ============================================================
# LOCATIONS
# ============================================================

@router.get(
    "/locations",
    response_model=List[LocationResponse]
)
def read_locations(db: Session = Depends(get_db)):
    return db.query(Location).all()


@router.post(
    "/locations",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED
)
def create_location(
    location: LocationCreate,
    db: Session = Depends(get_db)
):
    if not (-90 <= location.latitude <= 90):
        raise HTTPException(status_code=400, detail="Latitud inválida")

    if not (-180 <= location.longitude <= 180):
        raise HTTPException(status_code=400, detail="Longitud inválida")

    db_location = Location(
        name=location.name,
        latitude=location.latitude,
        longitude=location.longitude,
        address=location.address
    )

    db.add(db_location)
    db.commit()
    db.refresh(db_location)

    log_location_to_file(
        location.name,
        location.address or "",
        location.latitude,
        location.longitude
    )

    return db_location


@router.delete(
    "/locations/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_location(
    location_id: int,
    db: Session = Depends(get_db)
):
    location = (
        db.query(Location)
        .filter(Location.id == location_id)
        .first()
    )

    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    db.delete(location)
    db.commit()

    return None


@router.delete(
    "/locations",
    status_code=status.HTTP_204_NO_CONTENT
)
def clear_all_locations(db: Session = Depends(get_db)):
    db.query(Location).delete()
    db.commit()
    return None


# ============================================================
# WEEKLY EXPORT
# ============================================================

@router.get("/export/weekly_routes")
def export_weekly_routes():

    if not LOG_FILE.is_file():
        with open(
            LOG_FILE,
            mode="w",
            encoding="utf-8-sig",
            newline=""
        ) as file:

            writer = csv.writer(file)
            writer.writerow([
                "Fecha/Hora",
                "Nombre/Referencia",
                "Dirección",
                "Latitud",
                "Longitud"
            ])

    return FileResponse(
        path=str(LOG_FILE),
        filename="rutas_semana_registros.csv",
        media_type="text/csv"
    )


# ============================================================
# REFERENCES
# ============================================================

@router.get(
    "/references",
    response_model=List[ReferenceResponse]
)
def read_references(db: Session = Depends(get_db)):
    return db.query(Reference).all()


@router.post(
    "/references",
    response_model=ReferenceResponse,
    status_code=status.HTTP_201_CREATED
)
def create_reference(
    reference: ReferenceCreate,
    db: Session = Depends(get_db)
):
    location = (
        db.query(Location)
        .filter(Location.id == reference.location_id)
        .first()
    )

    if not location:
        raise HTTPException(
            status_code=404,
            detail="Location not found"
        )

    db_reference = Reference(
        description=reference.description,
        location_id=reference.location_id
    )

    db.add(db_reference)
    db.commit()
    db.refresh(db_reference)

    return db_reference


# ============================================================
# OPTIMAL ROUTE
# ============================================================

@router.get(
    "/optimal_route",
    response_model=List[LocationResponse]
)
def get_optimal_route(db: Session = Depends(get_db)):

    locations = db.query(Location).all()

    if not locations:
        return []

    return calculate_optimal_route(locations)
