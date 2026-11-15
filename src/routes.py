import logging
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
    get_current_admin_user,
    get_password_hash,
)
from src.models import (
    User, Location, Reference, DeliveryRoute, LocationStatusHistory,
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
        raise HTTPException(status_code=403, detail="El registro público está deshabilitado. Solicita acceso al administrador.")
    if len(user_in.password) < 8:
        raise HTTPException(status_code=422, detail="La contraseña debe tener al menos 8 caracteres.")
    new_user = User(
        username=user_in.username.strip(),
        email=user_in.email,
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


@router.get("/admin/users", response_model=List[UserResponse], tags=["Administration"])
def admin_list_users(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    return db.query(User).order_by(User.username.asc()).all()


@router.post("/admin/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["Administration"])
def admin_create_user(user_in: UserCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    if len(user_in.password) < 8:
        raise HTTPException(status_code=422, detail="La contraseña debe tener al menos 8 caracteres.")
    if db.query(User).filter(User.username == user_in.username.strip()).first():
        raise HTTPException(status_code=409, detail="El usuario ya existe.")
    if user_in.email and db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=409, detail="El correo ya está registrado.")
    user = User(username=user_in.username.strip(), email=user_in.email, hashed_password=get_password_hash(user_in.password), disabled=False, role="operator")
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
    if current_user.role != "admin" and location.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este pedido.")
    events = db.query(LocationStatusHistory).filter(LocationStatusHistory.location_id == location_id).order_by(LocationStatusHistory.changed_at.desc(), LocationStatusHistory.id.desc()).all()
    return [{"id": event.id, "old_status": event.old_status, "new_status": event.new_status, "changed_by": event.changed_by_username, "changed_at": event.changed_at} for event in events]


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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(Location)
    if current_user.role != "admin":
        query = query.filter(Location.created_by_id == current_user.id)
    if route_id is not None:
        query = query.filter(Location.route_id == route_id)
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
        delivered=location.delivered or False,
        status="delivered" if location.delivered else "pending",
        created_by_id=current_user.id,
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
    """Marca una parada como entregada o pendiente."""
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Parada no encontrada")

    if current_user.role != "admin" and loc.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para modificar este pedido.")
    new_status = "delivered" if payload.delivered else "pending"
    if loc.status != new_status:
        db.add(LocationStatusHistory(location_id=loc.id, old_status=loc.status, new_status=new_status, changed_by_id=current_user.id))
        loc.status = new_status
        loc.status_updated_by_id = current_user.id
    loc.delivered = payload.delivered
    db.commit()
    db.refresh(loc)
    return loc


@router.patch("/locations/{location_id}/status", response_model=LocationResponse, tags=["Locations"])
def update_location_status(location_id: int, payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    allowed = {"pending", "assigned", "in_transit", "delivered", "issue", "cancelled"}
    new_status = payload.get("status")
    if new_status not in allowed:
        raise HTTPException(status_code=422, detail="Estado no válido.")
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")
    if current_user.role != "admin" and loc.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para modificar este pedido.")
    if loc.status != new_status:
        db.add(LocationStatusHistory(location_id=loc.id, old_status=loc.status, new_status=new_status, changed_by_id=current_user.id))
        loc.status = new_status
        loc.delivered = new_status == "delivered"
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
    if current_user.role != "admin" and location.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para eliminar este pedido.")

    db.delete(location)
    db.commit()

    return None


@router.delete(
    "/locations",
    status_code=status.HTTP_204_NO_CONTENT
)
def clear_all_locations(
    route_id: Optional[int] = Query(None, description="Borrar paradas solo de esta ruta"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(Location)
    if current_user.role != "admin":
        query = query.filter(Location.created_by_id == current_user.id)
    if route_id is not None:
        query = query.filter(Location.route_id == route_id)
    query.delete(synchronize_session=False)
    db.commit()
    return None


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
    if current_user.role != "admin":
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
    if current_user.role != "admin" and location.created_by_id != current_user.id:
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
    if current_user.role != "admin":
        query = query.filter(Location.created_by_id == current_user.id)
    if route_id is not None:
        query = query.filter(Location.route_id == route_id)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(Location)
    if current_user.role != "admin":
        query = query.filter(Location.created_by_id == current_user.id)
    if route_id is not None:
        query = query.filter(Location.route_id == route_id)

    locations = query.all()

    if not locations:
        return []

    return calculate_optimal_route(locations)
