import hashlib
import logging
import secrets
import pytesseract
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
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Query, status
)
from sqlalchemy import and_, or_
from fastapi.responses import Response, FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db
from src.auth import (
    authenticate_user,
    get_current_active_user,
    get_current_admin_user,
    get_password_hash,
    oauth2_scheme,
)
from src.models import (
    User, UserSession, Location, Reference, DeliveryRoute, LocationStatusHistory,
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
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR)))
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = DATA_DIR / "weekly_routes_log.csv"

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
    if db.query(User).count() > 0:
        raise HTTPException(status_code=403, detail="La cuenta inicial ya fue creada. Inicia sesión o solicita al administrador que cree tu usuario.")
    email = (user_in.email or "").strip().lower()
    if email != "jorgebotero190@gmail.com":
        raise HTTPException(status_code=403, detail="El registro inicial está reservado al correo autorizado.")
    if len(user_in.password) < 8:
        raise HTTPException(status_code=422, detail="La contraseña debe tener al menos 8 caracteres.")
    username = (user_in.username or email).strip()
    new_user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash(user_in.password),
        disabled=False,
        role="admin"
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
            detail="Correo o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    db.add(UserSession(user_id=user.id, token_hash=token_hash))
    db.commit()

    return {
        "access_token": token,
        "token_type": "bearer"
    }


@router.post("/logout", status_code=204, tags=["Authentication"])
def logout(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    persistent_session = db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.token_hash == token_hash,
        UserSession.revoked_at.is_(None)
    ).first()
    if persistent_session:
        persistent_session.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return Response(status_code=204)


@router.get("/users/me", response_model=UserResponse)
def read_users_me(
    current_user: User = Depends(get_current_active_user)
):
    return current_user


@router.get("/admin/users", response_model=List[UserResponse], tags=["Administration"])
def admin_list_users(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    return db.query(User).order_by(User.username.asc()).all()


@router.get("/admin/users/activity", tags=["Administration"])
def admin_users_activity(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    local_tz = ZoneInfo("America/Bogota")
    today = datetime.now(local_tz).date()
    week_start = datetime.combine(today - timedelta(days=6), datetime.min.time(), tzinfo=local_tz).astimezone(timezone.utc).replace(tzinfo=None)
    drivers = db.query(User).filter(User.role == "driver").order_by(User.username.asc()).all()
    activity = []
    for user in drivers:
        orders = db.query(Location).filter(or_(Location.assigned_to_id == user.id, and_(Location.assigned_to_id.is_(None), Location.created_by_id == user.id))).all()
        pending = sum(1 for order in orders if order.status in {"pending", "assigned", "in_transit"} and not order.delivered)
        in_transit = sum(1 for order in orders if order.status == "in_transit")
        delivered = db.query(LocationStatusHistory.location_id).filter(LocationStatusHistory.changed_by_id == user.id, LocationStatusHistory.new_status == "delivered").distinct().count()
        events = db.query(LocationStatusHistory).filter(LocationStatusHistory.changed_by_id == user.id, LocationStatusHistory.new_status == "delivered", LocationStatusHistory.changed_at >= week_start).order_by(LocationStatusHistory.changed_at.desc()).all()
        daily = { (today - timedelta(days=6-offset)).isoformat(): 0 for offset in range(7) }
        for event in events:
            changed_at = event.changed_at
            if changed_at.tzinfo is None:
                changed_at = changed_at.replace(tzinfo=timezone.utc)
            key = changed_at.astimezone(local_tz).date().isoformat()
            if key in daily: daily[key] += 1
        activity.append({"id":user.id,"username":user.username,"email":user.email,"disabled":user.disabled,"status":"Inactivo" if user.disabled else ("En recorrido" if in_transit else ("Con pedidos asignados" if pending else "Disponible")),"delivered":delivered,"pending":pending,"pending_orders":[{"id":order.id,"address":order.address or order.name,"status":order.status} for order in orders if order.status in {"pending","assigned","in_transit"} and not order.delivered],"in_transit":in_transit,"delivered_today":daily.get(today.isoformat(),0),"deliveries_by_day":daily})
    return {"users":activity,"total_drivers":len(drivers),"drivers_on_route":sum(1 for user in activity if user["in_transit"]>0),"deliveries_today":sum(user["delivered_today"] for user in activity)}


@router.post("/admin/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["Administration"])
def admin_create_user(user_in: UserCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    email = (user_in.email or "").strip().lower()
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=422, detail="Ingresa un correo electrónico válido.")
    if len(user_in.password) < 8:
        raise HTTPException(status_code=422, detail="La contraseña debe tener al menos 8 caracteres.")
    role = user_in.role or "operator"
    if role not in {"admin", "operator", "driver"}:
        raise HTTPException(status_code=422, detail="Rol no válido.")
    username = (user_in.username or email).strip()
    if db.query(User).filter((User.username == username) | (User.email == email)).first():
        raise HTTPException(status_code=409, detail="El correo ya está registrado.")
    user = User(username=username, email=email, hashed_password=get_password_hash(user_in.password), disabled=False, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/admin/users/{user_id}/disabled", response_model=UserResponse, tags=["Administration"])
def admin_set_user_disabled(user_id: int, payload: dict, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="No puedes desactivar tu propia cuenta.")
    disabled = payload.get("disabled")
    if not isinstance(disabled, bool):
        raise HTTPException(status_code=422, detail="El campo disabled debe ser booleano.")
    if disabled and user.role == "admin":
        active_admins = db.query(User).filter(User.role == "admin", User.disabled == False).count()
        if active_admins <= 1:
            raise HTTPException(status_code=400, detail="Debe existir al menos un administrador activo.")
    user.disabled = disabled
    db.commit()
    db.refresh(user)
    return user


@router.get("/admin/summary", tags=["Administration"])
def admin_summary(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    total = db.query(Location).count()
    counts = {key: db.query(Location).filter(Location.status == key).count() for key in ("pending", "assigned", "in_transit", "delivered", "issue", "cancelled")}
    return {"total": total, "by_status": counts, "users": db.query(User).count()}


@router.get("/locations/{location_id}/history", tags=["Locations"])
def location_status_history(location_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")
    if current_user.role == "driver" and location.assigned_to_id != current_user.id:
        raise HTTPException(status_code=403, detail="Solo puedes consultar el historial de pedidos asignados a ti.")
    if current_user.role == "operator" and location.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este pedido.")
    events = db.query(LocationStatusHistory).filter(LocationStatusHistory.location_id == location_id).order_by(LocationStatusHistory.changed_at.desc(), LocationStatusHistory.id.desc()).all()
    return [{"id": event.id, "old_status": event.old_status, "new_status": event.new_status, "notes": event.notes, "changed_by": event.changed_by_username, "changed_at": event.changed_at} for event in events]


# ============================================================
# GEOCODING Y PARSER DE GUÍAS DE ENTREGA (COLOMBIA / VALLE DE ABURRÁ)
# ============================================================

def normalize_geocode_value(value: str) -> str:
    import re
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", normalized.casefold()).strip()


def address_number_tokens_match(query: str, candidate_address: str) -> bool:
    import re
    def normalize_number(token: str) -> str:
        suffix = token[-1] if token[-1].isalpha() else ""
        number = token[:-1] if suffix else token
        return f"{int(number)}{suffix}"
    expected = [normalize_number(token) for token in re.findall(r"\d+[a-z]?", normalize_geocode_value(query))]
    actual = [normalize_number(token) for token in re.findall(r"\d+[a-z]?", normalize_geocode_value(candidate_address))]
    return bool(expected) and all(token in actual for token in expected)


def clean_address_for_geocoding(raw_text: str) -> str:
    """Normaliza abreviaturas colombianas y conserva la nomenclatura (# y guion)."""
    import re
    cleaned = unicodedata.normalize("NFKC", raw_text).strip()
    cleaned = re.sub(r"\b(?:cra|cr|carrera)\.?\s*(?=\d)", "Carrera ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:cll|cl|calle)\.?\s*(?=\d)", "Calle ", cleaned, flags=re.IGNORECASE)
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
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*#\s*", " # ", cleaned)
    cleaned = re.sub(r"\s*,\s*", ", ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip(" ,")


def query_arcgis_geocoder(search_text: str, requested_muni: Optional[str] = None) -> List[dict]:
    """Consulta ArcGIS y descarta resultados de otro municipio o ubicaciones genéricas."""
    import re
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
                lat, lon = float(point["y"]), float(point["x"])
                if not (5.8 <= lat <= 6.6 and -75.9 <= lon <= -75.1):
                    continue

                municipality = attrs.get("City") or attrs.get("Municipality") or attrs.get("Subregion") or ""
                neighborhood = attrs.get("Nbrhd") or attrs.get("District") or ""
                if requested_muni and normalize_geocode_value(municipality) != normalize_geocode_value(requested_muni):
                    continue

                address_type = attrs.get("Addr_type", "")
                display_name = attrs.get("LongLabel") or candidate.get("address") or ""
                if re.search(r"\d", search_text):
                    if address_type.casefold() not in {"pointaddress", "subaddress"}:
                        continue
                    if not address_number_tokens_match(search_text, display_name):
                        continue

                results.append({
                    "display_name": display_name,
                    "latitude": lat,
                    "longitude": lon,
                    "municipality": municipality,
                    "neighborhood": neighborhood,
                    "type": address_type or "PointAddress",
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
    import re
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
    normalized_q = normalize_geocode_value(raw_query)
    padded_query = f" {normalized_q} "
    requested_muni = next((m for m in municipalities if f" {normalize_geocode_value(m)} " in padded_query), None)

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
                    municipality = addr.get("city") or addr.get("town") or addr.get("municipality") or addr.get("county") or ""
                    if requested_muni and normalize_geocode_value(municipality) != normalize_geocode_value(requested_muni):
                        continue
                    item_type = (item.get("type") or "").casefold()
                    display_name = item.get("display_name", "")
                    if re.search(r"\d", cleaned_q):
                        if item_type in {"city", "town", "suburb", "neighbourhood", "administrative", "road", "residential"}:
                            continue
                        if not address_number_tokens_match(cleaned_q, display_name):
                            continue
                    results.append({
                        "display_name": display_name,
                        "latitude": float(item["lat"]),
                        "longitude": float(item["lon"]),
                        "municipality": municipality,
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


@router.get("/reverse-geocode", tags=["Geocoding"])
def reverse_geocode(latitude: float = Query(..., ge=-90, le=90), longitude: float = Query(..., ge=-180, le=180)):
    """Convierte el punto seleccionado en el mapa a una dirección legible."""
    global GEOCODE_LAST_REQUEST
    try:
        elapsed = time.monotonic() - GEOCODE_LAST_REQUEST
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        params = urllib.parse.urlencode({
            "lat": latitude,
            "lon": longitude,
            "format": "jsonv2",
            "addressdetails": 1,
            "zoom": 18,
            "accept-language": "es"
        })
        request = urllib.request.Request(
            f"https://nominatim.openstreetmap.org/reverse?{params}",
            headers={"User-Agent": "RutaClaraDeliveryApp/5.0"}
        )
        GEOCODE_LAST_REQUEST = time.monotonic()
        with urllib.request.urlopen(request, timeout=6) as response:
            data = json.loads(response.read().decode("utf-8"))
        if not data.get("display_name"):
            raise ValueError("El proveedor no devolvió una dirección")
        details = data.get("address", {})
        municipality = details.get("city") or details.get("town") or details.get("municipality") or details.get("county") or ""
        neighborhood = details.get("neighbourhood") or details.get("suburb") or details.get("quarter") or ""
        return {
            "display_name": data["display_name"],
            "municipality": municipality,
            "neighborhood": neighborhood
        }
    except Exception as error:
        logger.warning("Error de geocodificación inversa: %s", error)
        raise HTTPException(status_code=502, detail="No fue posible obtener la dirección del punto seleccionado.")


@router.post("/ocr-delivery-label", tags=["Geocoding"])
def ocr_delivery_label_endpoint(payload: dict, current_user: User = Depends(get_current_active_user)):
    """Recibe una foto de cámara, aplica OCR en español y analiza la etiqueta."""
    import base64
    import binascii
    import io
    import re
    from PIL import Image, ImageOps, ImageEnhance

    image_data = payload.get("image", "")
    if not isinstance(image_data, str) or not image_data:
        raise HTTPException(status_code=400, detail="No se recibió una imagen.")
    image_data = re.sub(r"^data:image/[a-zA-Z0-9.+-]+;base64,", "", image_data)
    try:
        raw_image = base64.b64decode(image_data, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="La imagen enviada no es válida.")
    if len(raw_image) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="La imagen supera el límite de 8 MB.")
    try:
        image = Image.open(io.BytesIO(raw_image))
        if image.width * image.height > 20_000_000:
            raise HTTPException(status_code=413, detail="La imagen supera el límite de 20 megapíxeles.")
        image = ImageOps.exif_transpose(image).convert("L")
        image = ImageEnhance.Contrast(image).enhance(1.7)
        recognized_text = pytesseract.image_to_string(image, lang="spa+eng", config="--psm 6")
    except HTTPException:
        raise
    except pytesseract.TesseractNotFoundError:
        logger.exception("Tesseract OCR no está instalado")
        raise HTTPException(status_code=503, detail="El lector OCR no está instalado en el servidor.")
    except Exception as error:
        logger.exception("No se pudo procesar la imagen de la guía")
        raise HTTPException(status_code=422, detail="No se pudo leer la imagen. Enfoca la guía e inténtalo de nuevo.")
    if not recognized_text.strip():
        raise HTTPException(status_code=422, detail="No se detectó texto. Acerca la cámara, mejora la iluminación y captura de nuevo.")
    parsed = parse_delivery_label_endpoint({"text": recognized_text})
    return parsed


def sanitize_label_ocr_text(raw_text: str) -> str:
    """Descarta QR, códigos de barras, enlaces y códigos de seguimiento del OCR."""
    import re
    safe_lines = []
    for line in unicodedata.normalize("NFKC", raw_text).splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"^\s*(?:qr(?:\s*code)?|barcode|c[oó]digo\s+de\s+barras|tracking|seguimiento|awb|waybill|n[uú]mero\s+de\s+gu[ií]a)\b", line, re.IGNORECASE):
            continue
        line = re.sub(r"https?://\S+|www\.\S+", " ", line, flags=re.IGNORECASE)
        line = re.sub(r"\b(?:qr(?:\s*code)?|barcode|c[oó]digo\s+de\s+barras)\s*[:#-]?\s*\S*", " ", line, flags=re.IGNORECASE)
        line = re.sub(r"\b(?:tracking|seguimiento|awb|waybill|n[uú]mero\s+de\s+gu[ií]a)\b.*$", "", line, flags=re.IGNORECASE)
        line = re.sub(r"\b(?=[A-Z0-9_-]{9,}\b)(?=(?:[A-Z0-9_-]*[A-Z]){2,})(?=(?:[A-Z0-9_-]*\d){4,})[A-Z0-9_-]+\b", " ", line, flags=re.IGNORECASE)
        line = re.sub(r"\b\d{12,}\b", " ", line)
        if re.fullmatch(r"[\W_]*\d{8,}[\W_]*", line) or re.fullmatch(r"[\W_]*(?=[A-Z0-9_-]{9,}[\W_]*$)(?=(?:[A-Z0-9_-]*[A-Z]){2,})(?=(?:[A-Z0-9_-]*\d){4,})[A-Z0-9_-]{9,}[\W_]*", line, re.IGNORECASE):
            continue
        line = re.sub(r"\s+", " ", line).strip(" \t-•")
        if line:
            safe_lines.append(line)
    return "\n".join(safe_lines)


@router.post("/parse-delivery-label", tags=["Geocoding"])
def parse_delivery_label_endpoint(payload: dict, current_user: User = Depends(get_current_active_user)):
    """Extrae solo datos de ubicación; nunca devuelve nombres ni códigos de seguimiento."""
    import re

    raw_text = payload.get("text", "")
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise HTTPException(status_code=400, detail="Texto vacío")

    text = sanitize_label_ocr_text(raw_text).replace("\u00a0", " ")
    text = re.sub(r"\bDlrecci[oó0]n\b", "Dirección", text, flags=re.IGNORECASE)
    text = re.sub(r"\bCerrera\b", "Carrera", text, flags=re.IGNORECASE)
    text = re.sub(r"\bapartemento\b", "apartamento", text, flags=re.IGNORECASE)

    def extract_field(label_pattern: str) -> str:
        match = re.search(
            rf"^[ \t]*(?:{label_pattern})[ \t]*[:：-][ \t]*([^\r\n]+)",
            text,
            re.IGNORECASE | re.MULTILINE
        )
        return match.group(1).strip(" \t-•") if match else ""

    destination_type = "Comercial" if re.search(r"\bCOMERCIAL\b", text, re.IGNORECASE) else "Residencial"
    direccion = extract_field(r"d[i1l]recci[oó0]n(?:[ \t]+(?:exacta|principal|de[ \t]+entrega|de[ \t]+env[ií]o))?|domicilio|address")
    distrito = extract_field(r"distrito|barrio|sector|comuna")
    municipio = extract_field(r"municipio|ciudad|localidad")
    unidad = extract_field(r"unidad|conjunto|edificio|urbanizaci[oó]n|condominio|establecimiento")
    referencia = extract_field(r"referencia|indicaci[oó]n(?:es)?|apartamento|apto|torre|interior|local|bloque")

    if not municipio:
        municipalities = ["Medellín", "Envigado", "Sabaneta", "Itagüí", "La Estrella", "Caldas", "Bello", "Copacabana", "Girardota", "Barbosa", "CABA", "Buenos Aires"]
        normalized_text = f" {normalize_geocode_value(text)} "
        municipio = next((name for name in municipalities if f" {normalize_geocode_value(name)} " in normalized_text), "")
    if not distrito and municipio:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for position, line in enumerate(lines):
            if normalize_geocode_value(line) == normalize_geocode_value(municipio):
                candidate = next((item for item in lines[position + 1:position + 3] if item.isupper() and item.casefold() not in {"residencial", "comercial"}), "")
                if candidate:
                    distrito = candidate.title()
                break

    if not direccion:
        address_line = re.search(
            r"^[ \t]*((?:calle|cl\.?|carrera|cra\.?|carr\.?|cerrera|avenida|av\.?|diagonal|diag\.?|transversal|transv\.?|circular)\b[^\r\n]{3,})",
            text,
            re.IGNORECASE | re.MULTILINE
        )
        direccion = address_line.group(1).strip() if address_line else ""

    if not direccion:
        raise HTTPException(status_code=422, detail="No se encontró una dirección en la guía.")

    direccion = re.sub(r"\bCerrera\b", "Carrera", direccion, flags=re.IGNORECASE)
    direccion = re.sub(r"\b(?:cra|cr|carrera)\.?\s*(?=\d)", "Carrera ", direccion, flags=re.IGNORECASE)
    direccion = re.sub(r"\b(?:cll|cl|calle)\.?\s*(?=\d)", "Calle ", direccion, flags=re.IGNORECASE)
    unit_match = re.search(r"\b(apartamento|apartemento|apto\.?|apt\.?|piso|oficina|ofc\.?|torre|interior|int\.?|local|bloque|blq\.?)\s*[\w-]+", direccion, re.IGNORECASE)
    if unit_match and not referencia:
        referencia = unit_match.group(0).strip()
    if unit_match:
        direccion = direccion[:unit_match.start()] + direccion[unit_match.end():]
    direccion = re.sub(r"\bS?/?N\b", "", direccion, flags=re.IGNORECASE)
    direccion = direccion.strip(" ,.-")
    compact = re.match(r"^(Carrera|Calle)\s*(\d+)([a-z]?)\s*(?:#\s*)?(\d{1,3})\s*-\s*(\d{1,3})$", direccion, re.IGNORECASE)
    if compact:
        direccion = f"{compact.group(1).title()} {compact.group(2)}{compact.group(3).upper()} #{compact.group(4)}-{compact.group(5)}"
    direccion = re.sub(r"\s*#\s*", " #", direccion)
    direccion = re.sub(r"\s+", " ", direccion).strip(" ,.-")

    referencia = re.sub(r"(?i)\breferencia\s*[:：].*$", "", referencia).strip(" ,;:-")
    referencia = re.split(r"(?i)\b(?:a nombre de|destinatario|destinaterio|recibe|cliente)\b", referencia)[0].strip(" ,;:-")

    return {
        "tipo": destination_type,
        "direccion": direccion,
        "distrito": distrito,
        "municipio": municipio,
        "unidad": unidad,
        "referencia": referencia
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
def list_delivery_routes(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Lista todas las rutas de entrega con la cantidad de paradas asignadas."""
    route_query = db.query(DeliveryRoute)
    if current_user.role == "driver":
        route_query = route_query.filter(DeliveryRoute.id.in_(db.query(Location.route_id).filter(Location.assigned_to_id == current_user.id)))
    elif current_user.role == "operator":
        route_query = route_query.filter(DeliveryRoute.id.in_(db.query(Location.route_id).filter(Location.created_by_id == current_user.id)))
    routes = route_query.order_by(DeliveryRoute.created_at.desc()).all()
    result = []
    for r in routes:
        stops_query = db.query(Location).filter(Location.route_id == r.id)
        if current_user.role == "driver":
            stops_query = stops_query.filter(Location.assigned_to_id == current_user.id)
        elif current_user.role == "operator":
            stops_query = stops_query.filter(Location.created_by_id == current_user.id)
        stops_count = stops_query.count()
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
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
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
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
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
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """Elimina la ruta sin borrar las entregas que contiene."""
    route = db.query(DeliveryRoute).filter(DeliveryRoute.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    replacement = db.query(DeliveryRoute).filter(DeliveryRoute.id != route_id, DeliveryRoute.is_active == True).first()
    if not replacement:
        replacement = DeliveryRoute(name="Ruta Principal", is_active=True)
        db.add(replacement)
        db.flush()
    db.query(Location).filter(Location.route_id == route_id).update({Location.route_id: replacement.id}, synchronize_session=False)
    db.delete(route)
    db.commit()
    return None


# ============================================================
# LOCATIONS
# ============================================================

@router.patch("/locations/{location_id}/assign", response_model=LocationResponse, tags=["Administration"])
def assign_location(location_id: int, payload: dict, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location: raise HTTPException(status_code=404, detail="Pedido no encontrado.")
    if location.status in {"delivered", "cancelled"}:
        raise HTTPException(status_code=409, detail="No puedes reasignar una entrega finalizada o cancelada.")
    assigned_to_id = payload.get("assigned_to_id")
    assignee = None
    if assigned_to_id is not None:
        if type(assigned_to_id) is not int: raise HTTPException(status_code=422, detail="El domiciliario seleccionado no es válido.")
        assignee = db.query(User).filter(User.id == assigned_to_id, User.role == "driver", User.disabled == False).first()
        if not assignee: raise HTTPException(status_code=422, detail="Selecciona un domiciliario activo.")
    old_status = location.status
    old_assignee_id = location.assigned_to_id
    location.assigned_to_id = assignee.id if assignee else None
    new_status = "assigned" if assignee else "pending"
    if old_status != new_status or old_assignee_id != location.assigned_to_id:
        assignment_note = f"Asignado a {assignee.username}" if assignee else "Se retiró la asignación."
        db.add(LocationStatusHistory(location_id=location.id, old_status=old_status, new_status=new_status, notes=assignment_note, changed_by_id=admin.id))
        location.status = new_status
        location.issue_note = None
        location.delivered = False
        location.status_updated_by_id = admin.id
    db.commit(); db.refresh(location)
    return location


@router.get(
    "/locations",
    response_model=List[LocationResponse]
)
def read_locations(
    route_id: Optional[int] = Query(None, description="Filtrar por ID de ruta"),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(Location)
    if current_user.role == "driver": query = query.filter(Location.assigned_to_id == current_user.id)
    elif current_user.role != "admin": query = query.filter(Location.created_by_id == current_user.id)
    if route_id is not None: query = query.filter(Location.route_id == route_id)
    if status_filter: query = query.filter(Location.status == status_filter)
    return query.order_by(Location.created_at.desc()).all()


@router.post(
    "/locations",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED
)
def create_location(
    location: LocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role == "driver":
        raise HTTPException(status_code=403, detail="El repartidor solo puede gestionar pedidos asignados por el administrador.")
    if location.delivered:
        raise HTTPException(status_code=422, detail="Una entrega nueva debe registrarse como pendiente.")
    if not location.entrance_confirmed or not (location.entrance_name or "").strip():
        raise HTTPException(status_code=422, detail="La portería debe estar indicada y confirmada en el mapa.")
    if location.client_id:
        existing = db.query(Location).filter(Location.client_id == location.client_id).first()
        if existing:
            if existing.created_by_id != current_user.id:
                raise HTTPException(status_code=409, detail="La clave de sincronización ya pertenece a otro usuario.")
            return existing
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
        entrance_name=location.entrance_name,
        entrance_confirmed=location.entrance_confirmed,
        location_source=location.location_source,
        client_id=location.client_id,
        route_id=target_route_id,
        delivered=False,
        status="pending",
        created_by_id=current_user.id,
        assigned_to_id=current_user.id if current_user.role == "driver" else None,
        status_updated_by_id=current_user.id,
    )

    db.add(db_location)
    db.flush()
    db.add(LocationStatusHistory(location_id=db_location.id, old_status=None, new_status=db_location.status, changed_by_id=current_user.id))
    db.commit()
    db.refresh(db_location)

    log_location_to_file(
        location.name,
        location.address or "",
        location.latitude,
        location.longitude
    )

    return db_location


@router.patch("/locations/{location_id}", response_model=LocationResponse, tags=["Locations"])
def update_location_details(location_id: int, payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Parada no encontrada.")
    if current_user.role == "driver" or (current_user.role == "operator" and location.created_by_id != current_user.id):
        raise HTTPException(status_code=403, detail="Solo el administrador o el operador que registró el pedido puede editar sus datos.")
    address = payload.get("address")
    name = payload.get("name")
    reference = payload.get("unit_number")
    if not isinstance(address, str) or not address.strip():
        raise HTTPException(status_code=422, detail="La dirección es obligatoria.")
    if not isinstance(name, str) or not name.strip():
        raise HTTPException(status_code=422, detail="El nombre del usuario es obligatorio.")
    location.address = address.strip()
    location.name = name.strip()
    location.unit_number = reference.strip() if isinstance(reference, str) and reference.strip() else None
    db.commit()
    db.refresh(location)
    return location


@router.patch(
    "/locations/{location_id}/delivered",
    response_model=LocationResponse,
    tags=["Locations"]
)
def toggle_location_delivered(
    location_id: int,
    payload: LocationUpdateDelivered,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Confirma una entrega; solo el administrador puede reabrir una finalizada."""
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Parada no encontrada")
    if current_user.role == "driver" and loc.assigned_to_id != current_user.id:
        raise HTTPException(status_code=403, detail="Solo puedes confirmar pedidos asignados a ti.")
    if current_user.role == "operator" and loc.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para modificar este pedido.")
    if not payload.delivered and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo el administrador puede reabrir una entrega confirmada.")
    if loc.status == "cancelled":
        raise HTTPException(status_code=409, detail="Un pedido cancelado no puede marcarse como entregado.")
    if current_user.role == "driver" and loc.status not in {"assigned", "in_transit", "delivered"}:
        raise HTTPException(status_code=409, detail="El pedido debe estar asignado o en camino antes de confirmarlo.")
    if payload.delivered and loc.status != "delivered":
        db.add(LocationStatusHistory(location_id=loc.id, old_status=loc.status, new_status="delivered", changed_by_id=current_user.id))
        loc.status = "delivered"
        loc.delivered = True
        loc.issue_note = None
        loc.status_updated_by_id = current_user.id
    elif not payload.delivered and loc.status == "delivered":
        reopened_status = "assigned" if loc.assigned_to_id else "pending"
        db.add(LocationStatusHistory(location_id=loc.id, old_status="delivered", new_status=reopened_status, notes="Entrega reabierta por administrador.", changed_by_id=current_user.id))
        loc.status = reopened_status
        loc.delivered = False
        loc.status_updated_by_id = current_user.id
    db.commit()
    db.refresh(loc)
    return loc


@router.patch("/locations/{location_id}/status", response_model=LocationResponse, tags=["Locations"])
def update_location_status(location_id: int, payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    allowed = {"pending", "assigned", "in_transit", "delivered", "issue", "cancelled"}
    new_status = payload.get("status")
    notes = str(payload.get("notes") or payload.get("issue_note") or "").strip()
    if new_status not in allowed:
        raise HTTPException(status_code=422, detail="Estado no válido.")
    if len(notes) > 1000:
        raise HTTPException(status_code=422, detail="La novedad no puede superar 1000 caracteres.")
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")
    if current_user.role == "driver" and loc.assigned_to_id != current_user.id:
        raise HTTPException(status_code=403, detail="Solo puedes actualizar pedidos asignados a ti.")
    if current_user.role == "operator" and loc.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Solo puedes gestionar pedidos que registraste.")
    if current_user.role == "driver" and new_status not in {"in_transit", "delivered", "issue"}:
        raise HTTPException(status_code=403, detail="El repartidor solo puede marcar En camino, Entregado o Novedad.")
    if current_user.role != "admin" and new_status == "assigned":
        raise HTTPException(status_code=403, detail="La asignación de pedidos corresponde al administrador.")
    if new_status == "assigned" and not loc.assigned_to_id:
        raise HTTPException(status_code=422, detail="Asigna el pedido a un domiciliario antes de marcarlo como asignado.")
    if loc.status == "delivered" and new_status != "delivered" and current_user.role != "admin":
        raise HTTPException(status_code=409, detail="Una entrega confirmada solo puede reabrirla el administrador.")
    if loc.status == "cancelled" and new_status != "cancelled" and current_user.role != "admin":
        raise HTTPException(status_code=409, detail="Un pedido cancelado solo puede reactivarlo el administrador.")
    if new_status == "issue" and len(notes) < 5:
        raise HTTPException(status_code=422, detail="Describe la novedad con al menos 5 caracteres.")
    if new_status == "delivered" and loc.status == "cancelled":
        raise HTTPException(status_code=409, detail="Un pedido cancelado no puede marcarse como entregado.")
    if loc.status != new_status or (new_status == "issue" and notes != loc.issue_note):
        db.add(LocationStatusHistory(location_id=loc.id, old_status=loc.status, new_status=new_status, notes=notes or None, changed_by_id=current_user.id))
        loc.status = new_status
        loc.delivered = new_status == "delivered"
        loc.issue_note = notes if new_status == "issue" else None
        loc.status_updated_by_id = current_user.id
        db.commit()
        db.refresh(loc)
    return loc


@router.delete(
    "/locations/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_location(
    location_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    location = (
        db.query(Location)
        .filter(Location.id == location_id)
        .first()
    )

    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    if current_user.role == "driver" or (current_user.role == "operator" and location.created_by_id != current_user.id):
        raise HTTPException(status_code=403, detail="Solo el administrador o el operador que registró el pedido puede cancelarlo.")
    if location.status == "delivered":
        raise HTTPException(status_code=409, detail="No se puede eliminar una entrega completada; conserva su historial.")
    if location.status != "cancelled":
        db.add(LocationStatusHistory(location_id=location.id, old_status=location.status, new_status="cancelled", notes="Pedido cancelado desde la gestión de paradas.", changed_by_id=current_user.id))
        location.status = "cancelled"
        location.delivered = False
        location.issue_note = None
        location.status_updated_by_id = current_user.id
        db.commit()
    return None


@router.delete(
    "/locations",
    status_code=status.HTTP_204_NO_CONTENT
)
def clear_all_locations(
    route_id: Optional[int] = Query(None, description="Cancelar paradas activas solo de esta ruta"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    query = db.query(Location).filter(Location.status.notin_(["delivered", "cancelled"]))
    if route_id is not None:
        query = query.filter(Location.route_id == route_id)
    for location in query.all():
        db.add(LocationStatusHistory(location_id=location.id, old_status=location.status, new_status="cancelled", notes="Pedido cancelado al vaciar la ruta.", changed_by_id=admin.id))
        location.status = "cancelled"
        location.delivered = False
        location.issue_note = None
        location.status_updated_by_id = admin.id
    db.commit()
    return None



# ============================================================
# REPORTE PROFESIONAL DE RECORRIDOS (PDF)
# ============================================================

@router.get("/export/delivery-route.pdf", tags=["Reports"])
def export_delivery_route_pdf(
    route_id: Optional[int] = Query(None, description="Ruta específica; si se omite, se genera el reporte de los últimos siete días"),
    driver_id: Optional[int] = Query(None, description="Solo administradores: domiciliario del reporte"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Genera un PDF compacto de una ruta o de la actividad reciente de un domiciliario."""
    from io import BytesIO
    from zoneinfo import ZoneInfo
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    if current_user.role not in {"admin", "driver"}:
        raise HTTPException(status_code=403, detail="No tienes permiso para exportar recorridos.")

    target_driver = None
    if current_user.role == "driver":
        if driver_id is not None and driver_id != current_user.id:
            raise HTTPException(status_code=403, detail="Solo puedes exportar tus propios recorridos.")
        target_driver = current_user
    elif driver_id is not None:
        target_driver = db.query(User).filter(User.id == driver_id, User.role == "driver").first()
        if not target_driver:
            raise HTTPException(status_code=404, detail="No se encontró el domiciliario solicitado.")
    elif route_id is None:
        raise HTTPException(status_code=422, detail="Selecciona un domiciliario o una ruta para generar el informe.")

    query = db.query(Location)
    if route_id is not None:
        query = query.filter(Location.route_id == route_id)
    if target_driver:
        query = query.filter(Location.assigned_to_id == target_driver.id)
    if route_id is None:
        query = query.filter(Location.updated_at >= datetime.now(timezone.utc) - timedelta(days=7))

    locations = query.order_by(Location.route_id.asc(), Location.created_at.asc(), Location.id.asc()).all()
    if not locations:
        raise HTTPException(status_code=404, detail="No hay paradas para incluir en el periodo o ruta seleccionada.")

    location_ids = [item.id for item in locations]
    events = db.query(LocationStatusHistory).filter(
        LocationStatusHistory.location_id.in_(location_ids)
    ).order_by(LocationStatusHistory.changed_at.desc(), LocationStatusHistory.id.desc()).all()
    latest_events = {}
    for event in events:
        latest_events.setdefault(event.location_id, event)

    try:
        local_tz = ZoneInfo("America/Bogota")
    except Exception:
        local_tz = timezone.utc

    def local_datetime(value):
        if not value:
            return "—"
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(local_tz).strftime("%d/%m/%Y %H:%M")

    status_labels = {
        "pending": "Pendiente",
        "assigned": "Asignado",
        "in_transit": "En camino",
        "delivered": "Entregado",
        "issue": "Novedad",
        "cancelled": "Cancelado"
    }
    status_colors = {
        "delivered": "#176b63",
        "issue": "#a16207",
        "cancelled": "#64748b",
        "in_transit": "#245b83",
        "assigned": "#475569",
        "pending": "#475569"
    }
    delivered_count = sum(1 for item in locations if item.status == "delivered" or item.delivered)
    issue_count = sum(1 for item in locations if item.status == "issue")
    pending_count = sum(1 for item in locations if item.status in {"pending", "assigned", "in_transit"})
    generated_at = datetime.now(timezone.utc)
    period_label = "Ruta seleccionada" if route_id is not None else "Actividad de los últimos 7 días"
    driver_label = target_driver.username if target_driver else "Equipo asignado"

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=14 * mm, leftMargin=14 * mm,
        topMargin=15 * mm, bottomMargin=25 * mm,
        title="Reporte de recorridos - Ruta Clara",
        author="Ruta Clara"
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="RouteTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=18, leading=22, textColor=colors.HexColor("#14232d"),
        alignment=TA_LEFT, spaceAfter=3 * mm
    ))
    styles.add(ParagraphStyle(
        name="RouteMeta", parent=styles["Normal"], fontName="Helvetica",
        fontSize=8.5, leading=12, textColor=colors.HexColor("#687887")
    ))
    styles.add(ParagraphStyle(
        name="CellSmall", parent=styles["Normal"], fontName="Helvetica",
        fontSize=7.4, leading=10, textColor=colors.HexColor("#263746")
    ))
    styles.add(ParagraphStyle(
        name="CellMuted", parent=styles["Normal"], fontName="Helvetica",
        fontSize=6.7, leading=9, textColor=colors.HexColor("#687887")
    ))
    styles.add(ParagraphStyle(
        name="CellHeader", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=7, leading=9, textColor=colors.white
    ))
    styles.add(ParagraphStyle(
        name="SummaryCell", parent=styles["Normal"], fontName="Helvetica",
        fontSize=7, leading=17, alignment=1, textColor=colors.HexColor("#14232d")
    ))

    story = [
        Paragraph("REPORTE DE RECORRIDO", styles["RouteTitle"]),
        Paragraph(
            f"<b>Responsable:</b> {escape(driver_label)}"
            f" &nbsp;&nbsp; <b>Periodo:</b> {escape(period_label)}"
            f" &nbsp;&nbsp; <b>Generado:</b> {local_datetime(generated_at)}",
            styles["RouteMeta"]
        ),
        Spacer(1, 5 * mm)
    ]
    summary = []
    for number, label in [
        (len(locations), "PARADAS"),
        (delivered_count, "ENTREGADAS"),
        (pending_count, "PENDIENTES"),
        (issue_count, "NOVEDADES")
    ]:
        summary.append(Paragraph(
            f"<font size='15'><b>{number}</b></font><br/><font size='6.5' color='#687887'>{label}</font>",
            styles["SummaryCell"]
        ))
    summary_table = Table([summary], colWidths=[(A4[0] - 28 * mm) / 4] * 4)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f6f7")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dfe7e9")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dfe7e9")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7)
    ]))
    story.extend([summary_table, Spacer(1, 6 * mm)])

    rows = [[
        Paragraph("#", styles["CellHeader"]),
        Paragraph("RUTA Y DIRECCIÓN", styles["CellHeader"]),
        Paragraph("REFERENCIA / ACCESO", styles["CellHeader"]),
        Paragraph("ESTADO", styles["CellHeader"]),
        Paragraph("ACTUALIZACIÓN", styles["CellHeader"])
    ]]
    row_styles = []
    for index, item in enumerate(locations, start=1):
        route_name = item.route.name if item.route else f"Ruta {item.route_id or 'sin asignar'}"
        address = item.address or item.name or "Dirección no registrada"
        area = " · ".join(value for value in [item.municipality, item.neighborhood] if value)
        route_address = f"<b>{escape(route_name)}</b><br/>{escape(address)}"
        if area:
            route_address += f"<br/><font color='#687887'>{escape(area)}</font>"
        references = " · ".join(value for value in [item.unit_number, item.entrance_name] if value) or "—"
        state = item.status or ("delivered" if item.delivered else "pending")
        if item.delivered:
            state = "delivered"
        event = latest_events.get(item.id)
        updated = event.changed_at if event else (item.updated_at or item.created_at)
        rows.append([
            Paragraph(str(index), styles["CellSmall"]),
            Paragraph(route_address, styles["CellSmall"]),
            Paragraph(escape(references), styles["CellSmall"]),
            Paragraph(f"<font color='{status_colors.get(state, '#475569')}'><b>{escape(status_labels.get(state, state.title()))}</b></font>", styles["CellSmall"]),
            Paragraph(local_datetime(updated), styles["CellMuted"])
        ])
        if index % 2 == 0:
            row_styles.append(("BACKGROUND", (0, index), (-1, index), colors.HexColor("#f7f9fa")))

    table = Table(
        rows,
        colWidths=[9 * mm, 67 * mm, 39 * mm, 25 * mm, 29 * mm],
        repeatRows=1,
        hAlign="LEFT"
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#182832")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, colors.HexColor("#182832")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.35, colors.HexColor("#e1e7ea")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6)
    ] + row_styles))
    story.append(table)

    def draw_footer(canvas, doc):
        canvas.saveState()
        page_width, _ = A4
        canvas.setStrokeColor(colors.HexColor("#dfe5e9"))
        canvas.setLineWidth(0.6)
        canvas.line(14 * mm, 19 * mm, page_width - 14 * mm, 19 * mm)
        canvas.setFillColor(colors.HexColor("#182832"))
        canvas.circle(19 * mm, 10.5 * mm, 4.2 * mm, fill=1, stroke=0)
        canvas.setStrokeColor(colors.HexColor("#75c1b1"))
        canvas.setLineWidth(1.2)
        canvas.line(16.8 * mm, 9 * mm, 19 * mm, 12.5 * mm)
        canvas.line(19 * mm, 12.5 * mm, 21.4 * mm, 9.5 * mm)
        canvas.setFillColor(colors.HexColor("#75c1b1"))
        canvas.circle(16.8 * mm, 9 * mm, 0.8 * mm, fill=1, stroke=0)
        canvas.circle(19 * mm, 12.5 * mm, 0.8 * mm, fill=1, stroke=0)
        canvas.circle(21.4 * mm, 9.5 * mm, 0.8 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#182832"))
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.drawString(26 * mm, 11 * mm, "RUTA CLARA")
        canvas.setFillColor(colors.HexColor("#687887"))
        canvas.setFont("Helvetica", 6)
        canvas.drawString(26 * mm, 7.5 * mm, "GESTIÓN LOGÍSTICA")
        canvas.drawRightString(page_width - 14 * mm, 9 * mm, f"Documento interno · Página {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    pdf = buffer.getvalue()
    slug_source = target_driver.username if target_driver else f"ruta-{route_id}"
    import re
    filename_slug = re.sub(r"[^a-z0-9]+", "-", slug_source.casefold()).strip("-") or "recorrido"
    filename = f"ruta-clara-{filename_slug}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
    )



@router.get("/export/delivery-route.xlsx", tags=["Reports"])
def export_delivery_route_xlsx(
    route_id: Optional[int] = Query(None),
    driver_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Genera una hoja de cálculo editable con resumen, paradas y marca Ruta Clara."""
    from io import BytesIO
    from zoneinfo import ZoneInfo
    from PIL import Image as PILImage, ImageDraw, ImageFont
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
    from openpyxl.drawing.image import Image as ExcelImage
    from openpyxl.utils import get_column_letter
    import re

    if current_user.role not in {"admin", "driver"}:
        raise HTTPException(status_code=403, detail="No tienes permiso para exportar recorridos.")
    target_driver = None
    if current_user.role == "driver":
        if driver_id is not None and driver_id != current_user.id:
            raise HTTPException(status_code=403, detail="Solo puedes exportar tus propios recorridos.")
        target_driver = current_user
    elif driver_id is not None:
        target_driver = db.query(User).filter(User.id == driver_id, User.role == "driver").first()
        if not target_driver:
            raise HTTPException(status_code=404, detail="No se encontró el domiciliario solicitado.")
    elif route_id is None:
        raise HTTPException(status_code=422, detail="Selecciona un domiciliario o una ruta para generar el informe.")

    query = db.query(Location)
    if route_id is not None:
        query = query.filter(Location.route_id == route_id)
    if target_driver:
        query = query.filter(Location.assigned_to_id == target_driver.id)
    if route_id is None:
        query = query.filter(Location.updated_at >= datetime.now(timezone.utc) - timedelta(days=7))
    locations = query.order_by(Location.route_id.asc(), Location.created_at.asc(), Location.id.asc()).all()
    if not locations:
        raise HTTPException(status_code=404, detail="No hay paradas para incluir en el periodo o ruta seleccionada.")

    ids = [item.id for item in locations]
    events = db.query(LocationStatusHistory).filter(
        LocationStatusHistory.location_id.in_(ids)
    ).order_by(LocationStatusHistory.changed_at.desc(), LocationStatusHistory.id.desc()).all()
    latest_events = {}
    for event in events:
        latest_events.setdefault(event.location_id, event)
    try:
        local_tz = ZoneInfo("America/Bogota")
    except Exception:
        local_tz = timezone.utc

    def local_datetime(value):
        if not value:
            return "—"
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(local_tz).strftime("%d/%m/%Y %H:%M")

    labels = {"pending":"Pendiente","assigned":"Asignado","in_transit":"En camino","delivered":"Entregado","issue":"Novedad","cancelled":"Cancelado"}
    generated_at = datetime.now(timezone.utc)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Recorrido"
    sheet.sheet_view.showGridLines = False
    sheet.merge_cells("A1:G1")
    sheet["A1"] = "REPORTE DE RECORRIDO"
    sheet["A1"].font = Font(name="Arial", size=18, bold=True, color="14232D")
    sheet["A1"].alignment = Alignment(vertical="center")
    sheet.row_dimensions[1].height = 32
    sheet.merge_cells("A2:G2")
    sheet["A2"] = f"Responsable: {target_driver.username if target_driver else 'Equipo asignado'}  |  Periodo: {'Ruta seleccionada' if route_id else 'Últimos 7 días'}  |  Generado: {local_datetime(generated_at)}"
    sheet["A2"].font = Font(name="Arial", size=9, color="687887")
    sheet["A2"].alignment = Alignment(wrap_text=True, vertical="center")
    sheet.row_dimensions[2].height = 25

    delivered = sum(1 for item in locations if item.status == "delivered" or item.delivered)
    pending = sum(1 for item in locations if item.status in {"pending","assigned","in_transit"})
    issues = sum(1 for item in locations if item.status == "issue")
    summary = [
        ("PARADAS", len(locations)),
        ("ENTREGADAS", delivered),
        ("PENDIENTES", pending),
        ("NOVEDADES", issues)
    ]
    for index, (label, value) in enumerate(summary):
        start = index * 2 + 1
        end = start + 1
        sheet.merge_cells(start_row=4, start_column=start, end_row=4, end_column=end)
        cell = sheet.cell(4, start, f"{label}: {value}")
        cell.font = Font(name="Arial", size=10, bold=True, color="14232D")
        cell.fill = PatternFill("solid", fgColor="F2F6F7")
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = Border(bottom=Side(style="thin", color="DFE7E9"))
    sheet.row_dimensions[4].height = 26

    headers = ["N.º", "Ruta", "Dirección", "Municipio / Barrio", "Referencia / Acceso", "Estado", "Última actualización"]
    header_row = 7
    for col, value in enumerate(headers, start=1):
        cell = sheet.cell(header_row, col, value)
        cell.font = Font(name="Arial", size=9, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="182832")
        cell.alignment = Alignment(horizontal="left", vertical="center")
    sheet.row_dimensions[header_row].height = 24

    thin_border = Border(bottom=Side(style="hair", color="DFE5E9"))
    for row_index, item in enumerate(locations, start=header_row + 1):
        state = "delivered" if item.delivered else (item.status or "pending")
        route_name = item.route.name if item.route else f"Ruta {item.route_id or 'sin asignar'}"
        area = " · ".join(value for value in [item.municipality, item.neighborhood] if value) or "—"
        reference = " · ".join(value for value in [item.unit_number, item.entrance_name] if value) or "—"
        event = latest_events.get(item.id)
        values = [row_index - header_row, route_name, item.address or item.name or "Dirección no registrada", area, reference, labels.get(state, state.title()), local_datetime(event.changed_at if event else (item.updated_at or item.created_at))]
        for col, value in enumerate(values, start=1):
            cell = sheet.cell(row_index, col, value)
            cell.font = Font(name="Arial", size=9, color="263746")
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = thin_border
            if row_index % 2 == 0:
                cell.fill = PatternFill("solid", fgColor="F7F9FA")
        state_cell = sheet.cell(row_index, 6)
        state_cell.font = Font(name="Arial", size=9, bold=True, color="176B63" if state == "delivered" else ("A16207" if state == "issue" else "475569"))
        sheet.row_dimensions[row_index].height = 32

    widths = [7, 22, 38, 24, 28, 16, 22]
    for col, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(col)].width = width
    sheet.freeze_panes = "A8"
    sheet.auto_filter.ref = f"A{header_row}:G{header_row + len(locations)}"
    footer_row = header_row + len(locations) + 3

    logo_image = PILImage.new("RGBA", (360, 76), (255, 255, 255, 0))
    draw = ImageDraw.Draw(logo_image)
    draw.ellipse((4, 5, 66, 67), fill="#182832")
    draw.line((22, 46, 36, 23, 52, 44), fill="#75C1B1", width=4)
    for point in [(22,46),(36,23),(52,44)]:
        draw.ellipse((point[0]-4, point[1]-4, point[0]+4, point[1]+4), fill="#75C1B1")
    try:
        bold_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 21)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except OSError:
        bold_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    draw.text((82, 13), "RUTA CLARA", fill="#182832", font=bold_font)
    draw.text((84, 43), "GESTION LOGISTICA", fill="#687887", font=small_font)
    image_buffer = BytesIO()
    logo_image.save(image_buffer, format="PNG")
    image_buffer.seek(0)
    logo = ExcelImage(image_buffer)
    logo.width = 230
    logo.height = 49
    sheet.add_image(logo, f"A{footer_row}")
    sheet.merge_cells(start_row=footer_row + 1, start_column=1, end_row=footer_row + 1, end_column=7)
    footer = sheet.cell(footer_row + 1, 1, "Documento interno · Ruta Clara")
    footer.font = Font(name="Arial", size=8, color="687887", italic=True)
    footer.alignment = Alignment(vertical="center")
    sheet.row_dimensions[footer_row + 1].height = 18
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.print_title_rows = "1:7"
    sheet.print_area = f"A1:G{footer_row + 1}"
    sheet.oddFooter.center.text = "RUTA CLARA · GESTIÓN LOGÍSTICA  |  Página &[Page] de &[Pages]"
    sheet.oddFooter.center.size = 8
    sheet.oddFooter.center.font = "Arial,Regular"

    output = BytesIO()
    workbook.save(output)
    filename_slug = re.sub(r"[^a-z0-9]+", "-", (target_driver.username if target_driver else f"ruta-{route_id}").casefold()).strip("-") or "recorrido"
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="ruta-clara-{filename_slug}.xlsx"', "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
    )


# ============================================================
# WEEKLY EXPORT
# ============================================================

@router.get("/export/weekly_routes")
def export_weekly_routes(admin: User = Depends(get_current_admin_user)):

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
def read_references(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    query = db.query(Reference).join(Location, Reference.location_id == Location.id)
    if current_user.role == "driver":
        query = query.filter(or_(Location.assigned_to_id == current_user.id, and_(Location.assigned_to_id.is_(None), Location.created_by_id == current_user.id)))
    elif current_user.role != "admin":
        query = query.filter(Location.created_by_id == current_user.id)
    return query.all()


@router.post(
    "/references",
    response_model=ReferenceResponse,
    status_code=status.HTTP_201_CREATED
)
def create_reference(
    reference: ReferenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    location = (
        db.query(Location)
        .filter(Location.id == reference.location_id)
        .first()
    )

    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    if current_user.role != "admin" and location.created_by_id != current_user.id and location.assigned_to_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para este pedido.")

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

@router.get("/road_route", tags=["Routing"])
def get_road_route(
    route_id: Optional[int] = Query(None),
    start_lat: Optional[float] = Query(None, ge=-90, le=90),
    start_lon: Optional[float] = Query(None, ge=-180, le=180),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Calcula recorrido vial desde el GPS del repartidor y ordena las paradas."""
    if (start_lat is None) != (start_lon is None):
        raise HTTPException(status_code=400, detail="Debes enviar latitud y longitud GPS.")
    query = db.query(Location)
    if current_user.role == "driver": query = query.filter(or_(Location.assigned_to_id == current_user.id, and_(Location.assigned_to_id.is_(None), Location.created_by_id == current_user.id)))
    elif current_user.role != "admin": query = query.filter(Location.created_by_id == current_user.id)
    query = query.filter(Location.status.in_(["pending", "assigned", "in_transit"]), Location.delivered == False)
    if route_id is not None: query = query.filter(Location.route_id == route_id)
    start = (start_lat, start_lon) if start_lat is not None else None
    locations = calculate_optimal_route(query.all(), start=start)
    if not locations:
        return {"distance_m": 0, "duration_s": 0, "geometry": [], "legs": [], "stop_ids": []}
    coordinates = []
    if start is not None:
        coordinates.append(f"{start_lon:.6f},{start_lat:.6f}")
    coordinates.extend(f"{loc.longitude:.6f},{loc.latitude:.6f}" for loc in locations)
    if len(coordinates) < 2:
        return {"distance_m": 0, "duration_s": 0, "geometry": [], "legs": [], "stop_ids": [loc.id for loc in locations], "origin_included": start is not None}
    base_url = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org").rstrip("/")
    route = None
    optimization = "nearest_neighbor"
    if start is not None:
        trip_url = f"{base_url}/trip/v1/driving/{';'.join(coordinates)}?roundtrip=false&source=first&destination=any&overview=full&geometries=geojson&steps=false"
        try:
            trip_request = urllib.request.Request(trip_url, headers={"User-Agent": "RutaClara/1.0"})
            with urllib.request.urlopen(trip_request, timeout=20) as response:
                trip_payload = json.loads(response.read().decode("utf-8"))
            waypoints = trip_payload.get("waypoints", [])
            if trip_payload.get("code") == "Ok" and trip_payload.get("trips") and len(waypoints) == len(coordinates):
                waypoint_order = sorted(range(len(waypoints)), key=lambda index: waypoints[index].get("waypoint_index", index))
                stop_order = [index - 1 for index in waypoint_order if index != 0]
                if len(stop_order) == len(locations) and set(stop_order) == set(range(len(locations))):
                    locations = [locations[index] for index in stop_order]
                    route = trip_payload["trips"][0]
                    optimization = "road_duration"
        except Exception as trip_error:
            logger.warning("OSRM trip no disponible; se usa orden aproximado: %s", trip_error)
    try:
        if route is None:
            url = f"{base_url}/route/v1/driving/{';'.join(coordinates)}?overview=full&geometries=geojson&steps=false"
            request = urllib.request.Request(url, headers={"User-Agent": "RutaClara/1.0"})
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("code") != "Ok" or not payload.get("routes"):
                raise ValueError(payload.get("message") or "OSRM no encontró un recorrido")
            route = payload["routes"][0]
        geometry = route.get("geometry", {}).get("coordinates", [])
        legs = route.get("legs", [])
        expected_legs = len(locations) if start is not None else len(locations) - 1
        if len(geometry) < 2 or len(legs) != expected_legs:
            raise ValueError("OSRM devolvió una ruta incompleta")
        return {
            "distance_m": route["distance"],
            "duration_s": route["duration"],
            "geometry": geometry,
            "legs": [{"distance_m": leg["distance"], "duration_s": leg["duration"]} for leg in legs],
            "stop_ids": [loc.id for loc in locations],
            "origin_included": start is not None,
            "optimization": optimization
        }
    except Exception as error:
        logger.exception("Error calculando recorrido vial con OSRM")
        raise HTTPException(status_code=502, detail=f"No fue posible calcular la ruta vial: {error}")


@router.get(
    "/optimal_route",
    response_model=List[LocationResponse]
)
def get_optimal_route(
    route_id: Optional[int] = Query(None, description="Optimizar paradas de una ruta específica"),
    start_lat: Optional[float] = Query(None, ge=-90, le=90),
    start_lon: Optional[float] = Query(None, ge=-180, le=180),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if (start_lat is None) != (start_lon is None):
        raise HTTPException(status_code=400, detail="Debes enviar latitud y longitud GPS.")
    query = db.query(Location)
    if current_user.role == "driver": query = query.filter(or_(Location.assigned_to_id == current_user.id, and_(Location.assigned_to_id.is_(None), Location.created_by_id == current_user.id)))
    elif current_user.role != "admin": query = query.filter(Location.created_by_id == current_user.id)
    query = query.filter(Location.status.in_(["pending", "assigned", "in_transit"]), Location.delivered == False)
    if route_id is not None: query = query.filter(Location.route_id == route_id)
    locations = query.all()

    if not locations:
        return []

    start = (start_lat, start_lon) if start_lat is not None else None
    return calculate_optimal_route(locations, start=start)
