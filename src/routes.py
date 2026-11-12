import logging
import unicodedata

import os
import json
import csv
import time
import sqlite3
import urllib.parse
import urllib.request
from collections import OrderedDict
from pathlib import Path
from datetime import datetime
from typing import List, Optional

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
    User, Location, Reference, DeliveryRoute,
    UserCreate, UserResponse,
    LocationCreate, LocationResponse, LocationUpdateDelivered,
    ReferenceCreate, ReferenceResponse,
    DeliveryRouteCreate, DeliveryRouteUpdate, DeliveryRouteResponse,
    Token,
)
from src.route_optimizer import calculate_optimal_route

logger = logging.getLogger("ruta_clara.routes")

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
MAP_FILE = STATIC_DIR / "offline" / "valle_aburra.mbtiles"
LOG_FILE = BASE_DIR / "weekly_routes_log.csv"

GEOCODE_CACHE_MAX = 500
GEOCODE_CACHE: OrderedDict = OrderedDict()
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
# GEOCODING Y PARSER DE GUÍAS DE ENTREGA (COLOMBIA / VALLE DE ABURRÁ)
# ============================================================

def clean_address_for_geocoding(raw_text: str) -> str:
    """
    Limpia una dirección colombiana para que el geocodificador encuentre la vía exacta.
    Remueve apartamentos, interiores, oficinas, torres y SN que confunden a los mapas.
    """
    import re
    cleaned = raw_text
    # Remover patrones de unidades internas
    patterns = [
        r'\b(apartamento|apto|apt|ap)\.?\s*(\d+[a-zA-Z]*)',
        r'\b(oficina|ofc|ofi)\.?\s*(\d+[a-zA-Z]*)',
        r'\b(torre|tr)\.?\s*(\d+[a-zA-Z]*)',
        r'\b(interior|int)\.?\s*(\d+[a-zA-Z]*)',
        r'\b(local|loc)\.?\s*(\d+[a-zA-Z]*)',
        r'\b(piso|p)\.?\s*(\d+)',
        r'\bSN\b',
        r'\bS/N\b',
        r'\b(bloque|blq)\.?\s*(\d+[a-zA-Z]*)'
    ]
    for p in patterns:
        cleaned = re.sub(p, '', cleaned, flags=re.IGNORECASE)

    # Limpiar espacios repetidos y símbolos huérfanos
    cleaned = re.sub(r'[,#\s]+', ' ', cleaned).strip()
    return cleaned


def query_arcgis_geocoder(search_text: str, requested_muni: Optional[str] = None) -> List[dict]:
    """Consulta ArcGIS World Geocoding Service, optimizado para Colombia con respuesta < 0.5s."""
    results = []
    try:
        searches = []
        if requested_muni:
            searches.append(f"{search_text}, {requested_muni}, Antioquia, Colombia")
        searches.append(f"{search_text}, Valle de Aburrá, Antioquia, Colombia")
        searches.append(f"{search_text}, Colombia")

        for query_str in searches:
            params = urllib.parse.urlencode({
                "SingleLine": query_str,
                "f": "json",
                "outFields": "*",
                "maxLocations": 5,
                "outSR": 4326,
                "countryCode": "COL"
            })
            url = f"https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "RutaClara/5.0"})

            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode("utf-8"))

            for candidate in data.get("candidates", []):
                score = candidate.get("score", 0)
                if score < 70:
                    continue

                point = candidate.get("location", {})
                attrs = candidate.get("attributes", {})
                if "x" not in point or "y" not in point:
                    continue

                lat = float(point["y"])
                lon = float(point["x"])

                # Delimitar aproximadamente el Valle de Aburrá (Medellín, Envigado, etc.)
                if not (5.8 <= lat <= 6.6 and -75.9 <= lon <= -75.1):
                    continue

                municipality = attrs.get("City") or attrs.get("Subregion") or ""
                neighborhood = attrs.get("Nbrhd") or attrs.get("District") or ""

                results.append({
                    "display_name": attrs.get("LongLabel") or candidate.get("address"),
                    "latitude": lat,
                    "longitude": lon,
                    "municipality": municipality,
                    "neighborhood": neighborhood,
                    "type": attrs.get("Addr_type", "PointAddress"),
                    "class": "arcgis",
                    "score": score
                })

            if results:
                break
    except Exception as e:
        logger.warning("ArcGIS Geocoder error: %s", e)
    return results


@router.get("/geocode", tags=["Geocoding"])
def search_address(query: str = Query(..., min_length=3)):
    """
    Busca direcciones colombianas ultra-rápido (< 0.5s) con prioridad ArcGIS
    y normalización inteligente para nomenclatura del Valle de Aburrá.
    """
    global GEOCODE_LAST_REQUEST

    raw_query = " ".join(query.strip().split())
    if not raw_query:
        raise HTTPException(status_code=400, detail="Dirección vacía")

    cache_key = raw_query.casefold()
    if cache_key in GEOCODE_CACHE:
        return GEOCODE_CACHE[cache_key]

    # Detectar municipio solicitado en la consulta
    municipalities = [
        "Medellín", "Envigado", "Sabaneta", "Itagüí",
        "La Estrella", "Caldas", "Bello",
        "Copacabana", "Girardota", "Barbosa"
    ]
    normalized_q = raw_query.casefold()
    requested_muni = next((m for m in municipalities if m.casefold() in normalized_q), None)

    # 1. Limpieza de dirección (quitar apto 200, SN, oficina, etc. para geocodificar)
    cleaned_q = clean_address_for_geocoding(raw_query)

    # 2. Prioridad 1: ArcGIS (rápido, oficial para Colombia)
    results = query_arcgis_geocoder(cleaned_q, requested_muni)
    if not results and cleaned_q != raw_query:
        results = query_arcgis_geocoder(raw_query, requested_muni)

    # 3. Prioridad 2 (Fallback): Nominatim si ArcGIS no encontró
    if not results:
        try:
            elapsed = time.monotonic() - GEOCODE_LAST_REQUEST
            if elapsed < 1.0:
                time.sleep(1.0 - elapsed)

            params = urllib.parse.urlencode({
                "q": f"{cleaned_q}, Antioquia, Colombia",
                "format": "jsonv2",
                "limit": 3,
                "addressdetails": 1,
                "countrycodes": "co",
                "accept-language": "es"
            })
            url = f"https://nominatim.openstreetmap.org/search?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "RutaClaraDeliveryApp/5.0"})

            GEOCODE_LAST_REQUEST = time.monotonic()
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode("utf-8"))

            for item in data:
                if item.get("lat") and item.get("lon"):
                    addr = item.get("address", {})
                    results.append({
                        "display_name": item.get("display_name", ""),
                        "latitude": float(item["lat"]),
                        "longitude": float(item["lon"]),
                        "municipality": addr.get("city") or addr.get("town") or addr.get("municipality") or "",
                        "neighborhood": addr.get("suburb") or addr.get("neighbourhood") or "",
                        "type": item.get("type", ""),
                        "class": "nominatim"
                    })
        except Exception as e:
            logger.warning("Nominatim fallback error: %s", e)

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No se encontró la dirección. Intente verificar la nomenclatura o barrio."
        )

    # Guardar en cache LRU
    while len(GEOCODE_CACHE) >= GEOCODE_CACHE_MAX:
        GEOCODE_CACHE.popitem(last=False)
    GEOCODE_CACHE[cache_key] = results

    return results


@router.post("/parse-delivery-label", tags=["Geocoding"])
def parse_delivery_label_endpoint(payload: dict):
    """
    Parsea automáticamente el texto o OCR de una guía de entrega (Mercado Libre / Flex / transportadora):
    - Tipo: RESIDENCIAL / COMERCIAL
    - Dirección: Carrera/Calle ...
    - Distrito: Barrio/Comuna
    - Referencia: Apto / Torre / Indicaciones
    - Destinatario: Nombre (ID)
    """
    import re
    text = payload.get("text", "")
    if not text.strip():
        raise HTTPException(status_code=400, detail="Texto vacío")

    # 1. Tipo
    is_comercial = bool(re.search(r'\bCOMERCIAL\b', text, re.IGNORECASE))
    is_residencial = bool(re.search(r'\bRESIDENCIAL\b', text, re.IGNORECASE))
    destination_type = "Comercial" if is_comercial else ("Residencial" if is_residencial else "Residencial")

    # 2. Dirección
    dir_match = re.search(r'Direcci[oó]n:[ \t]*([^\n\r]+)', text, re.IGNORECASE)
    direccion = dir_match.group(1).strip() if dir_match else ""

    # 3. Distrito
    dist_match = re.search(r'Distrito:[ \t]*([^\n\r]+)', text, re.IGNORECASE)
    distrito = dist_match.group(1).strip() if dist_match else ""

    # 4. Referencia
    ref_match = re.search(r'Referencia:[ \t]*([^\n\r]*)', text, re.IGNORECASE)
    referencia = ref_match.group(1).strip() if ref_match else ""

    # 5. Destinatario y Tracking
    dest_match = re.search(r'Destinatario:[ \t]*([^\n\r]*)', text, re.IGNORECASE)
    dest_raw = dest_match.group(1).strip() if dest_match else ""
    tracking_id = ""
    id_m = re.search(r'\(([^)]+)\)', dest_raw)
    if id_m:
        tracking_id = id_m.group(1).strip()
        destinatario = re.sub(r'\([^)]+\)', '', dest_raw).strip()
    else:
        destinatario = dest_raw

    # Si la referencia está vacía pero la dirección tiene apartamento/oficina, extraerlo
    if not referencia and direccion:
        match_unit = re.search(r'(apartamento|apto|oficina|ofc|torre|interior|local|sn)\s*[\w\d\s]*', direccion, re.IGNORECASE)
        if match_unit:
            referencia = match_unit.group(0).strip()

    return {
        "tipo": destination_type,
        "direccion": direccion,
        "distrito": distrito,
        "referencia": referencia,
        "destinatario": destinatario,
        "tracking_id": tracking_id
    }


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
        logger.error("Error escribiendo CSV de historial: %s", error)


# ============================================================
# RUTAS DE ENTREGA (DELIVERY ROUTES)
# ============================================================

def get_or_create_default_route(db: Session) -> DeliveryRoute:
    route = db.query(DeliveryRoute).filter(DeliveryRoute.is_active == True).first()
    if not route:
        route = db.query(DeliveryRoute).first()
    if not route:
        route = DeliveryRoute(name="Ruta Principal 1", is_active=True)
        db.add(route)
        db.commit()
        db.refresh(route)
    return route


@router.get(
    "/delivery-routes",
    response_model=List[DeliveryRouteResponse],
    tags=["Delivery Routes"]
)
def list_delivery_routes(db: Session = Depends(get_db)):
    """Lista todas las rutas de entrega con la cantidad de paradas asignadas."""
    routes = db.query(DeliveryRoute).order_by(DeliveryRoute.created_at.desc()).all()
    result = []
    for r in routes:
        stops_count = db.query(Location).filter(Location.route_id == r.id).count()
        result.append(DeliveryRouteResponse(
            id=r.id,
            name=r.name,
            created_at=r.created_at,
            is_active=r.is_active,
            stops_count=stops_count
        ))
    return result


@router.post(
    "/delivery-routes",
    response_model=DeliveryRouteResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Delivery Routes"]
)
def create_delivery_route(
    route_in: DeliveryRouteCreate,
    db: Session = Depends(get_db)
):
    """Crea una nueva ruta de entrega independiente."""
    new_route = DeliveryRoute(name=route_in.name.strip(), is_active=True)
    db.add(new_route)
    db.commit()
    db.refresh(new_route)
    return DeliveryRouteResponse(
        id=new_route.id,
        name=new_route.name,
        created_at=new_route.created_at,
        is_active=new_route.is_active,
        stops_count=0
    )


@router.put(
    "/delivery-routes/{route_id}",
    response_model=DeliveryRouteResponse,
    tags=["Delivery Routes"]
)
def update_delivery_route(
    route_id: int,
    route_update: DeliveryRouteUpdate,
    db: Session = Depends(get_db)
):
    """Actualiza el nombre o estado de una ruta."""
    route = db.query(DeliveryRoute).filter(DeliveryRoute.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")

    if route_update.name is not None:
        route.name = route_update.name.strip()
    if route_update.is_active is not None:
        route.is_active = route_update.is_active

    db.commit()
    db.refresh(route)
    stops_count = db.query(Location).filter(Location.route_id == route.id).count()
    return DeliveryRouteResponse(
        id=route.id,
        name=route.name,
        created_at=route.created_at,
        is_active=route.is_active,
        stops_count=stops_count
    )


@router.delete(
    "/delivery-routes/{route_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Delivery Routes"]
)
def delete_delivery_route(
    route_id: int,
    db: Session = Depends(get_db)
):
    """Elimina una ruta completa y todas sus paradas asociadas."""
    route = db.query(DeliveryRoute).filter(DeliveryRoute.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")

    db.delete(route)
    db.commit()

    # Si no quedan rutas, crear una por defecto
    remaining = db.query(DeliveryRoute).count()
    if remaining == 0:
        get_or_create_default_route(db)

    return None


# ============================================================
# LOCATIONS
# ============================================================

@router.get(
    "/locations",
    response_model=List[LocationResponse]
)
def read_locations(
    route_id: Optional[int] = Query(None, description="Filtrar por ID de ruta"),
    db: Session = Depends(get_db)
):
    query = db.query(Location)
    if route_id is not None:
        query = query.filter(Location.route_id == route_id)
    return query.all()


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

    # Si no se especifica ruta, asignar a la ruta activa o por defecto
    target_route_id = location.route_id
    if target_route_id is None:
        default_route = get_or_create_default_route(db)
        target_route_id = default_route.id
    else:
        # Validar que exista la ruta
        route_exists = db.query(DeliveryRoute).filter(DeliveryRoute.id == target_route_id).first()
        if not route_exists:
            default_route = get_or_create_default_route(db)
            target_route_id = default_route.id

    db_location = Location(
        name=location.name,
        latitude=location.latitude,
        longitude=location.longitude,
        address=location.address,
        municipality=location.municipality,
        neighborhood=location.neighborhood,
        unit_number=location.unit_number,
        route_id=target_route_id,
        delivered=location.delivered or False,
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


@router.patch(
    "/locations/{location_id}/delivered",
    response_model=LocationResponse,
    tags=["Locations"]
)
def toggle_location_delivered(
    location_id: int,
    payload: LocationUpdateDelivered,
    db: Session = Depends(get_db)
):
    """Marca una parada como entregada o pendiente."""
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Parada no encontrada")

    loc.delivered = payload.delivered
    db.commit()
    db.refresh(loc)
    return loc


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
def clear_all_locations(
    route_id: Optional[int] = Query(None, description="Borrar paradas solo de esta ruta"),
    db: Session = Depends(get_db)
):
    query = db.query(Location)
    if route_id is not None:
        query = query.filter(Location.route_id == route_id)
    query.delete(synchronize_session=False)
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
def get_optimal_route(
    route_id: Optional[int] = Query(None, description="Optimizar paradas de una ruta específica"),
    db: Session = Depends(get_db)
):
    query = db.query(Location)
    if route_id is not None:
        query = query.filter(Location.route_id == route_id)

    locations = query.all()

    if not locations:
        return []

    return calculate_optimal_route(locations)
