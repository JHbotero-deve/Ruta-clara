# Ruta Clara

API y aplicación web para registrar ubicaciones, gestionar referencias y ordenar paradas de reparto con FastAPI, SQLAlchemy y Leaflet.

## Requisitos

- Docker Engine y Docker Compose v2.
- Git para clonar el repositorio.

## Inicio rápido

```bash
git clone https://github.com/JHbotero-deve/Ruta-clara.git
cd Ruta-clara
cp .env.example .env
```

Genera una clave segura y reemplaza `SECRET_KEY` dentro de `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

En Windows PowerShell también puedes ejecutar el mismo comando si tienes Python instalado. Luego inicia el contenedor de producción:

```bash
docker compose up -d --build
```

Abre:

- Aplicación: http://localhost:8004/map
- API: http://localhost:8004/docs
- Estado: http://localhost:8004/health

## Desarrollo con recarga automática

Para trabajar en el código, usa el archivo de desarrollo adicional. Monta el proyecto dentro del contenedor y activa Uvicorn `--reload`; los cambios en Python, HTML, JavaScript, CSS, JSON y SVG reinician o actualizan el servidor automáticamente.

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f web
```

Para detener el entorno de desarrollo:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
```

Para volver al modo de producción:

```bash
docker compose up -d --build
```

## Operación diaria

Reconstruir y reiniciar después de cambios en dependencias o Docker:

```bash
docker compose up -d --build
```

Ver logs:

```bash
docker compose logs -f web
```

Reiniciar sin reconstruir:

```bash
docker compose restart web
```

Comprobar estado:

```bash
docker compose ps
```

La base SQLite se conserva en el volumen Docker `ruta-clara-data`. `docker compose down` no elimina ese volumen. **No ejecutes `docker compose down -v`** salvo que quieras borrar también la base de datos persistida.

## Variables de entorno

Configura estas variables en `.env`:

| Variable | Uso |
|---|---|
| `SECRET_KEY` | Clave privada para firmar tokens. Debe ser única y segura. |
| `ALLOWED_ORIGINS` | Orígenes CORS permitidos, separados por coma. |
| `DATABASE_URL` | La composición Docker define SQLite persistente en `/app/data/app.db`. |

## Mapa y funcionamiento sin conexión

Leaflet y sus archivos estáticos se sirven desde el propio proyecto. Esto no significa que el mapa base ni la geocodificación funcionen completamente sin Internet: el paquete de teselas MBTiles del Valle de Aburrá no está incluido en el repositorio y debe instalarse por separado. El endpoint `/offline-map/status` permite comprobar si el archivo está disponible. Sin ese paquete, no se debe considerar listo el mapa geográfico offline.

## Endpoints principales

- `GET /health`: estado de la API.
- `GET /geocode?query=...`: búsqueda de direcciones.
- `GET /locations` y `POST /locations`: gestión de ubicaciones.
- `GET /optimal_route`: cálculo del orden de paradas.
- `GET /offline-map/status`: estado del paquete MBTiles.
- `GET /docs`: documentación interactiva OpenAPI.

## Notas

- El puerto público de Docker es `8004`; el puerto interno del contenedor es `8000`.
- No publiques el archivo `.env` ni compartas la clave `SECRET_KEY`.
- El modo de desarrollo con `--reload` no debe utilizarse como configuración de producción.
