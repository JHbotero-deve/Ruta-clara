# Ruta Clara 🚚🗺️

**Ruta Clara** es una API RESTful profesional desarrollada con **FastAPI**, **SQLAlchemy** y **Pydantic** diseñada para la gestión de ubicaciones, referencias y la optimización inteligente de rutas utilizando el algoritmo **Haversine** y resolución óptima del Problema del Viajante (TSP).

---

## 📋 Tabla de Contenidos

1. [Características Principales](#-características-principales)
2. [Arquitectura del Proyecto](#-arquitectura-del-proyecto)
3. [Requisitos Previos](#-requisitos-previos)
4. [Instalación y Configuración](#-instalación-y-configuración)
5. [Variables de Entorno](#-variables-de-entorno)
6. [Ejecución con Docker](#-ejecución-con-docker)
7. [Documentación de la API (Endpoints)](#-documentación-de-la-api-endpoints)
8. [Visualizador Frontend](#-visualizador-frontend)
9. [Seguridad y Producción](#-seguridad-y-producción)

---

## 🚀 Características Principales

- **Mapa Interno Integrado (Sin API Keys)**: Motor de mapas interactivo basado en **Leaflet.js** y **OpenStreetMap** servido directamente por la aplicación en `/map` sin depender de Google Maps ni claves externas.
- **Cálculo y Optimización de Rutas**: Algoritmo `Haversine` para distancias esféricas reales en la Tierra y motor híbrido de optimización de rutas (Fuerza Bruta exacta para $N \le 8$ y *Nearest Neighbor* con refinamiento *2-Opt* para conjuntos mayores).
- **Gestión de Ubicaciones y Referencias**: Modelado ORM completo con SQLAlchemy y validación estricta de datos de entrada/salida mediante esquemas Pydantic v2.
- **Pruebas Automatizadas y Auditoría**: Suite de pruebas unitarias e integración con Pytest y script de verificación de dependencias de producción.
- **Preparado para Producción**: Configuración flexible con variables de entorno (`DATABASE_URL`, `SECRET_KEY`, `ALLOWED_ORIGINS`), middleware CORS, usuario sin privilegios en Dockerfile y `docker-compose.yml`.
- **Documentación OpenAPI Automática**: Swagger UI interactivo disponible nativamente en `/docs` y Redoc en `/redoc`.

---

## 🏗️ Arquitectura del Proyecto

```text
ruta clara/
├── database.py              # Configuración de SQLAlchemy y gestión de la sesión get_db
├── index.html               # Visualizador web interactivo de rutas y mapas
├── audit_dependencies.py    # Script de auditoría y verificación de dependencias
├── requirements.txt         # Dependencias de producción
├── Dockerfile               # Imagen Docker de producción (appuser sin root)
├── docker-compose.yml       # Orquestación de servicios con volumen persistente
├── run.bat                  # Script de inicio rápido para Windows
├── .env.example             # Plantilla de variables de entorno
├── .gitignore               # Exclusiones para control de versiones
├── README.md                # Documentación del proyecto
├── src/
│   ├── __init__.py
│   ├── main.py              # Punto de entrada FastAPI, CORS y middleware
│   ├── models.py            # Modelos ORM (SQLAlchemy) y Esquemas DTO (Pydantic)
│   ├── auth.py              # Lógica de seguridad, JWT y hashing de contraseñas
│   ├── routes.py            # Enrutador principal de endpoints RESTful
│   └── route_optimizer.py   # Algoritmo Haversine y optimizador TSP (2-Opt)
└── tests/
    ├── __init__.py
    ├── test_api.py          # Pruebas de integración HTTP de la API
    ├── test_auth.py         # Pruebas unitarias de seguridad y tokens JWT
    └── test_route_optimizer.py # Pruebas unitarias de algoritmos de optimización
```

---

## 🛠️ Requisitos Previos

- **Python**: 3.10 o superior.
- **Docker y Docker Compose** (Opcional, para despliegue en contenedores).

---

## 💻 Instalación y Configuración

### 1. Clonar el Repositorio
```bash
git clone https://github.com/tu-usuario/ruta-clara.git
cd "ruta clara"
```

### 2. Crear y Activar Entorno Virtual
```bash
# Linux/macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Instalar Dependencias
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configurar Variables de Entorno
Copia la plantilla `.env.example` a un archivo `.env`:
```bash
cp .env.example .env
```

---

## 🔑 Variables de Entorno

| Variable | Descripción | Valor por Defecto |
| :--- | :--- | :--- |
| `SECRET_KEY` | Clave secreta para firmar tokens JWT | *Cadena generada para desarrollo* |
| `ALGORITHM` | Algoritmo de firma JWT | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Tiempo de expiración del token (en minutos) | `30` |
| `DATABASE_URL` | String de conexión a base de datos (SQLite, PostgreSQL, MySQL) | `sqlite:///./app.db` |
| `ALLOWED_ORIGINS` | Orígenes permitidos para CORS (separados por coma) | `*` |

---

## 🐳 Ejecución con Docker

### Con Docker Compose (Recomendado)
```bash
docker-compose up --build -d
```
La API estará disponible inmediatamente en `http://localhost:8000`.

### Con Docker CLI
```bash
docker build -t ruta-clara-api .
docker run -d -p 8000:8000 --name ruta-clara-app ruta-clara-api
```

---

## 🧪 Pruebas Automatizadas y Auditoría

### 1. Auditoría de Dependencias
Verifica que todas las dependencias requeridas en `requirements.txt` están correctamente instaladas:
```bash
python audit_dependencies.py
```

### 2. Ejecutar la Suite de Pruebas (Pytest)
Ejecuta las pruebas unitarias y de integración para validar la API, la seguridad y los algoritmos de optimización:
```bash
python -m pytest -v
```

---

## 📖 Documentación de la API (Endpoints)

Una vez iniciada la aplicación, explora la documentación interactiva Swagger en **`http://localhost:8000/docs`**.

### Resumen de Endpoints Principales

#### 🔐 Autenticación y Usuarios
- `POST /register`: Registro de un nuevo usuario.
- `POST /token`: Autenticación y obtención de Token JWT (`OAuth2PasswordRequestForm`).
- `GET /users/me`: Información del usuario actual autenticado.

#### 📍 Ubicaciones (`/locations`)
- `GET /locations`: Obtiene todas las ubicaciones almacenadas.
- `POST /locations`: Registra una nueva ubicación con nombre, latitud y longitud.

#### 🔖 Referencias (`/references`)
- `GET /references`: Lista todas las referencias asociadas a ubicaciones.
- `POST /references`: Asocia una nueva referencia descriptiva a una ubicación existente.

#### 🛣️ Ruta Óptima (`/optimal_route`)
- `GET /optimal_route`: Calcula y devuelve la secuencia ordenada de ubicaciones que minimiza la distancia total recorrida.

---

## 🗺️ Visualizador Frontend (Mapa Interno Integrado)

El proyecto incluye un visualizador de mapa interno integrado servido directamente en **`http://localhost:8000/map`** utilizando **Leaflet.js** y **OpenStreetMap** (100% gratuito, autónomo y sin cuotas ni claves de Google Maps).

1. Abre tu navegador e ingresa a **`http://localhost:8000/map`**.
2. Introduce tu **Token JWT de acceso** generado en `/token`.
3. Haz clic en **Cargar Ruta Óptima** para visualizar la secuencia ordenada de paradas, números en cada punto, detalles en popups y la línea trazada de navegación.

---

## 🛡️ Seguridad y Producción

- **Generación de SECRET_KEY**: En entornos de producción, genera una clave segura ejecutando:
  ```bash
  openssl rand -hex 32
  ```
- **Base de Datos en Producción**: Cambia `DATABASE_URL` en `.env` a una instancia manejada como PostgreSQL o MySQL:
  ```env
  DATABASE_URL=postgresql://usuario:contraseña@localhost:5432/ruta_clara_db
  ```
- **Ejecución del Servidor**: Para despliegues en servidores de producción, utiliza Uvicorn supervisado por Gunicorn:
  ```bash
  gunicorn src.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
  ```

---

## 📄 Licencia

Este proyecto está distribuido bajo la licencia MIT.


---

## Requisitos funcionales y hoja de ruta (actualizado: 15-11-2026)

Esta sección conserva las decisiones funcionales del producto para retomar el trabajo sin perder contexto.

### Roles y responsabilidades

- **Administrador:** administra usuarios y roles, asigna pedidos a domiciliarios y supervisa el trabajo del equipo. Su panel principal muestra personas y actividad, no un contador global de pedidos.
- **Operador:** registra y gestiona los pedidos que le corresponden según sus permisos.
- **Repartidor / domiciliario:** consulta y actualiza sus pedidos asignados, ejecuta su recorrido y registra entregas o novedades.

### Panel del administrador

- Mostrar domiciliarios, cuántos tienen pedidos en recorrido y las entregas realizadas durante el día.
- Mostrar por domiciliario: entregas realizadas, pendientes, entregas del día e historial diario de los últimos siete días.
- Permitir asignar y retirar pedidos de un domiciliario activo.
- Consultar el historial de cambios de cada pedido.
- Calcular métricas desde los pedidos y su historial persistido; no mantener contadores duplicados.

### Aplicación del domiciliario y ruta dinámica

- La ruta activa contiene únicamente pedidos pendientes, asignados o en camino. Los entregados, cancelados o reportados como novedad no aparecen en navegación.
- Al confirmar **Entregado**, guardar estado, hora y usuario; retirar el domicilio de la lista pendiente y pasarlo al apartado de entregados.
- Después de cada entrega, recalcular el orden desde la ubicación GPS actual y presentar la siguiente parada pendiente.
- Sin conexión, reordenar localmente las paradas pendientes por distancia desde el GPS actual; el trazado vial detallado requiere los datos de calles offline o conectividad.
- No borrar pedidos entregados: conservarlos en el historial y permitir consultarlos por fecha.
- Si un pedido no pudo entregarse, registrar una novedad; no marcarlo como entregado.
- Sin conexión, conservar la confirmación localmente y sincronizarla al recuperar conectividad, evitando duplicados.

### Asignación y trazabilidad

- Cada pedido puede tener un domiciliario responsable (assigned_to_id) distinto del usuario que lo registró (created_by_id).
- Los repartidores solo consultan pedidos propios sin asignación o pedidos asignados a ellos; el administrador puede supervisar todos los usuarios y pedidos.
- Mantener una única fuente de verdad en SQLite/API y un historial de cambios por pedido.

### Requisitos de operación y calidad

- Prioridad: funcionamiento offline, rapidez, estabilidad y facilidad de uso en el Valle de Aburrá.
- Conservar el escáner OCR: extraer únicamente dirección y datos de ubicación necesarios; excluir destinatario, tracking, códigos y contenido ajeno a la ubicación.
- Conservar el mapa Leaflet local y SQLite. La navegación vial/geocodificación puede requerir servicios externos mientras no estén disponibles los datos locales.
- Mantener acceso simple por correo y contraseña. El administrador gestiona los roles desde la aplicación.
- No desplegar ni modificar servicios remotos de producción sin autorización explícita.

### Criterios de aceptación

1. El administrador ve usuarios/domiciliarios y su actividad, no el resumen global de pedidos.
2. El administrador puede asignar un pedido a un domiciliario activo y el pedido aparece en su lista.
3. Un repartidor no consulta pedidos asignados a otro repartidor.
4. La ruta no incluye pedidos ya entregados.
5. Al marcar una parada como entregada, pasa a Entregados y la navegación continúa con la siguiente parada, recalculando desde el GPS actual.
6. La entrega conserva usuario, fecha y hora en el historial y se refleja en el panel administrativo.
7. Una entrega sin conexión se sincroniza al recuperar conectividad sin duplicarse.

### Pendientes de validación antes de producción

- Ejecutar pruebas automatizadas y validar la migración SQLite sobre una copia de una base existente.
- Probar en un dispositivo móvil el ciclo de asignación, navegación, entrega, pérdida de conexión y sincronización.
- Probar OCR con guías físicas reales y confirmar la geocodificación.
- Incorporar y validar MBTiles del Valle de Aburrá y datos de calles para navegación totalmente offline.
- Revisar SECRET_KEY, CORS y configuración del entorno antes de cualquier despliegue.

### Estado de esta actualización

- **Integrado en main** mediante el PR #5, commit de merge: db0fc92069664c556716ec1fb781b3dafbe8a5bf.
- **CI del PR aprobado:** sintaxis Python, pruebas del backend, sintaxis JavaScript inline y scripts externos.
- **No desplegado en producción.**
- Antes de producción todavía se debe validar la migración sobre una copia de una base SQLite existente y probar en un dispositivo real la asignación, navegación, entrega, pérdida de conexión y sincronización offline.
