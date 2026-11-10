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
- **Cálculo y Optimización de Rutas**: Algoritmo `Haversine` para distancias esféricas reales en la Tierra y motor híbrido de optimización de rutas (Fuerza Bruta exacta para $N \le 8$ y heurística *Nearest Neighbor* para conjuntos mayores).
- **Gestión de Ubicaciones y Referencias**: Modelado ORM completo con SQLAlchemy y validación estricta de datos de entrada/salida mediante esquemas Pydantic v2.
- **Preparado para Producción**: Configuración flexible con variables de entorno (`DATABASE_URL`, `SECRET_KEY`, `ALLOWED_ORIGINS`), middleware CORS, Dockerfile optimizado y `docker-compose.yml`.
- **Documentación OpenAPI Automática**: Swagger UI interactivo disponible nativamente en `/docs` y Redoc en `/redoc`.

---

## 🏗️ Arquitectura del Proyecto

```text
ruta clara/
├── database.py              # Configuración de SQLAlchemy y gestión de la sesión get_db
├── index.html               # Visualizador web con Google Maps API
├── requirements.txt         # Dependencias de producción
├── Dockerfile               # Imagen Docker de producción
├── docker-compose.yml       # Orquestación de servicios
├── .env.example             # Plantilla de variables de entorno
├── .gitignore               # Exclusiones para control de versiones
├── README.md                # Documentación del proyecto
└── src/
    ├── __init__.py
    ├── main.py              # Punto de entrada FastAPI, CORS y middleware
    ├── models.py            # Modelos ORM (SQLAlchemy) y Esquemas DTO (Pydantic)
    ├── auth.py              # Lógica de seguridad, JWT y hashing de contraseñas
    ├── routes.py            # Enrutador principal de endpoints RESTful
    └── route_optimizer.py   # Algoritmo Haversine y cálculo de ruta óptima
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
