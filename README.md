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
| `SECRET_KEY` | Clave secreta para firmar tokens JWT | Vacía en plantilla; fallback inseguro solo para desarrollo |
| `ALGORITHM` | Algoritmo de firma JWT | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Expiración de tokens JWT heredados o de compatibilidad (en minutos); el inicio de sesión actual usa sesiones persistentes revocables | `30` |
| `DATABASE_URL` | String de conexión a base de datos (SQLite, PostgreSQL, MySQL) | `sqlite:///./app.db` |
| `ALLOWED_ORIGINS` | Orígenes permitidos para CORS (separados por coma) | Vacío (solo mismo origen) |

En desarrollo puedes usar `http://localhost:8000,http://127.0.0.1:8000`. En producción configura únicamente los dominios reales de la interfaz. La aplicación rechaza `ALLOWED_ORIGINS=*` cuando el entorno está marcado como producción.

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
- `POST /token`: Autenticación y creación de una sesión persistente (`OAuth2PasswordRequestForm`).
- `POST /logout`: Revoca la sesión actual al cerrar sesión explícitamente.
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

### Sesión persistente

- Después de iniciar sesión, la sesión permanece guardada en el dispositivo aunque se cierre la pestaña, el navegador, la PWA o se reinicie el celular.
- Si se abre sin conexión, conserva el token y puede restaurar el perfil local para mostrar el módulo; al recuperar conexión, valida nuevamente la sesión y sincroniza los datos.
- La sesión solo se revoca desde la acción explícita **Salir / Cerrar sesión**; al volver a abrir Ruta Clara, se valida la sesión guardada y se abre el módulo correspondiente al rol.
- El navegador conserva el identificador de sesión en almacenamiento persistente local y el backend almacena únicamente su hash, sin guardar el token en texto plano.
- El endpoint `POST /logout` revoca la sesión actual en el servidor. Si el dispositivo está sin conexión, se elimina la sesión activa del dispositivo y se encola localmente la revocación del token; al recuperar conexión, Ruta Clara envía automáticamente esa revocación al servidor.
- Las sesiones nuevas no dependen del vencimiento corto de los JWT heredados; pueden revocarse en el servidor y dejan de ser válidas al cerrar sesión.

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
- Las nuevas paradas creadas sin conexión se guardan en el dispositivo con un identificador idempotente y se envían al servidor al recuperar conexión; después se sincronizan las confirmaciones de entrega usando el ID persistido.
- Si el servidor rechaza una parada por validación o permisos, la interfaz informa el error y no la presenta como guardada offline.
- El alcance offline sigue siendo parcial: el almacenamiento local y el mapa MBTiles no sustituyen la validación de sesión, geocodificación ni todos los servicios de la API.

### Asignación y trazabilidad

- Cada pedido puede tener un domiciliario responsable (assigned_to_id) distinto del usuario que lo registró (created_by_id).
- Los repartidores solo consultan pedidos con asignación vigente a su usuario; perder la asignación revoca el acceso inmediatamente. El administrador puede supervisar todos los usuarios y pedidos.
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
8. Una sesión iniciada permanece activa después de cerrar y volver a abrir la aplicación; solo se invalida al cerrar sesión explícitamente.

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
- **Sesión persistente integrada en main** mediante el PR #6, commit: c28cc541df1d5b3326120d645a228afbbc87297b.
- **CI del PR #6 aprobado:** sintaxis Python, pruebas del backend, sintaxis JavaScript inline y scripts externos.
- **Seguridad y permisos integrados en main** mediante PR #11 y PR #12; se limitaron los pedidos visibles al repartidor asignado, se protegieron las entregas finalizadas y se cerró CORS abierto en producción. Commit: 1f5253a8f1e1ce5fd8ed5e030d16bc8f3288da72.
- **CI de PR #11 y PR #12 aprobado**, incluidas pruebas de backend y sintaxis JavaScript.
- La sincronización automática de nuevas paradas offline está en revisión en el PR #14; no se considera integrada hasta que su CI pase y se fusione.
- Antes de producción todavía se debe validar la migración sobre una copia de una base SQLite existente y probar en un dispositivo real la asignación, navegación, entrega, pérdida de conexión y sincronización offline.

## 🎨 Identidad visual y experiencia de usuario

La interfaz de Ruta Clara debe mantener una apariencia de software empresarial de logística, clara y consistente en escritorio y dispositivos móviles.

- **Identidad:** paleta sobria basada en azul petróleo/grafito, verde azulado como acento funcional, fondos neutros y contraste accesible. Evitar degradados decorativos y exceso de colores.
- **Navegación:** menú lateral en escritorio y menú desplegable en móvil, con iconografía SVG uniforme y etiquetas claras.
- **Componentes:** tarjetas, tablas, formularios, botones, estados y campos deben compartir radios, bordes, espaciado, tipografía y jerarquía visual.
- **Iconografía:** priorizar iconos SVG consistentes frente a emojis en controles y navegación.
- **Responsive:** conservar una experiencia usable en pantallas pequeñas, sin ocultar acciones esenciales ni afectar el escáner, el mapa o la operación de entregas.
- **Alcance:** los cambios visuales no deben alterar autenticación, persistencia de sesión, asignaciones, estados de entrega, cálculo de recorridos ni funcionamiento offline.

### Reportes y seguridad del mapa

- El informe operativo para compartir o imprimir es un PDF A4 compacto, con identidad de Ruta Clara en el pie de página, responsable, periodo, conteos, direcciones, referencias, estado y fecha de actualización.
- El administrador puede descargar el informe de un domiciliario para los últimos siete días o una ruta específica. El domiciliario solo puede exportar sus propios recorridos.
- El XLSX editable ofrece datos en columnas, filtros y marca Ruta Clara al pie; el CSV semanal se conserva para análisis sin formato.
- El mapa es exclusivamente de consulta y navegación: tocar, pulsar o arrastrar el mapa nunca crea una parada. Las altas se realizan por formulario escrito, dictado por voz o escáner OCR.
- La descarga de reportes no expone destinatarios ni códigos de seguimiento.
