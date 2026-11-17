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
- Escáner de etiquetas autorizado: leer el QR únicamente para identificar/deduplicar el envío cuando el permiso operativo lo cubra; extraer por OCR la dirección y las referencias del destinatario. No usar remitente como destino ni conservar nombres, tracking, productos o datos ajenos a la entrega.
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
- **Sincronización de nuevas paradas offline integrada en main** mediante PR #14, commit: 0db135a52bd9f23d5863897f1a17852051d8632d.
- **CI del PR #14 aprobado:** sintaxis Python, pruebas del backend, sintaxis JavaScript inline y scripts externos.
- **OCR de guías integrado en main** mediante PR #15, commit: c97c2a3cde366b6e1983997e1871aff476c26b78.
- El OCR distingue el bloque de remitente del destinatario, conserva guías donde la dirección aparece antes del nombre del destinatario y no usa la dirección del remitente cuando falta un destino identificable.
- **CI del PR #15 aprobado:** pruebas del backend, OCR de direcciones, sintaxis Python y JavaScript.
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


## Operación rápida del domiciliario: escáner, ruta y modo offline

### Objetivo operativo

Ruta Clara debe permitir que el domiciliario registre una tanda completa de paquetes, valide sus destinos y obtenga un orden de recorrido en **menos de cinco minutos como objetivo medible**, para salir a repartir sin transcribir manualmente cada dirección ni reconstruir la ruta después de cada entrega. El tiempo se medirá en pruebas con tandas representativas; no se considera garantizado hasta validar dispositivos y datos reales autorizados.

El flujo debe ser de captura continua: abrir cámara una vez, leer cada etiqueta, agregar cada parada automáticamente cuando la lectura sea confiable y continuar con la siguiente. Al terminar la tanda, ordenar todas las paradas pendientes desde la ubicación GPS actual y permitir iniciar el recorrido. No se debe obligar al domiciliario a borrar y volver a ingresar las paradas después de cada entrega.

### Alcance del QR y del OCR

- El QR y el OCR cumplen funciones diferentes. El QR identifica el paquete o envío; el OCR reconoce texto impreso para localizar la dirección de entrega y sus referencias.
- Cuando la autorización operativa cubra expresamente la lectura del QR, Ruta Clara podrá decodificarlo localmente y usar el identificador mínimo necesario para detectar duplicados. No debe asumir que el QR contiene una dirección ni utilizar su contenido para consultar servicios privados.
- El OCR debe reconocer la sección de destino/entrega y extraer: dirección, referencias de acceso (torre, piso, apartamento, interior, unidad, conjunto u oficina), barrio y municipio cuando estén explícitos o puedan validarse con datos locales.
- La dirección del remitente, devolución u origen nunca puede utilizarse como dirección de entrega ni como alternativa automática.
- No extraer ni conservar nombres de compradores, teléfonos, productos, precios, códigos de seguimiento ni otros datos que no sean necesarios para ubicar la parada. El identificador QR, si se autoriza y se requiere para deduplicar, se conservará de forma minimizada (preferiblemente hash local) y con retención limitada.
- Una sola captura de cámara debe alimentar el lector QR y el OCR, sin abrir dos flujos de cámara ni pedir dos fotografías. La captura debe poder procesarse en el dispositivo.
- Si hay más de una dirección candidata, no se identifica claramente el bloque de destino o la lectura tiene baja confianza, no crear una parada automáticamente: mostrar corrección breve de dirección y referencia.
- Las correcciones del domiciliario deben poder hacerse en una sola pantalla y conservar la referencia completa sin mezclarla con la nomenclatura principal.

### Requisitos de velocidad y experiencia

1. Iniciar una sesión de escaneo continuo y mantener la cámara activa mientras se capturan varios paquetes.
2. Procesar cada etiqueta en segundo plano y mostrar un resultado compacto: dirección, municipio/barrio y referencia.
3. Agregar automáticamente solo lecturas inequívocas; advertir duplicados por identificador QR autorizado o por coincidencia de dirección.
4. Evitar formularios largos. Dirección es el dato indispensable; barrio y referencia son opcionales si la etiqueta no los contiene. El municipio puede completarse desde la selección de zona o el paquete local de direcciones, pero nunca inventarse.
5. Mostrar el contador de paquetes capturados, pendientes de validar y duplicados.
6. Al finalizar, ordenar todas las paradas pendientes en una sola operación desde el GPS actual. La entrega de una parada la mueve al historial y recalcula la siguiente sin borrar el resto de la ruta.
7. El escáner no debe esperar a que se sincronice cada paquete con el servidor para continuar. Las altas se guardan primero localmente y se sincronizan después, conservando identificadores idempotentes.

### Arquitectura necesaria para funcionamiento 100% offline

El objetivo offline comprende captura, QR, OCR, validación, geocodificación, optimización, mapa, navegación básica, persistencia e historial local. La conexión solo se necesita para sincronizar con el administrador cuando esté disponible.

- **QR local:** incluir una biblioteca de lectura empaquetada en los archivos estáticos de Ruta Clara; no cargar scripts desde CDN ni enviar imágenes a servicios de lectura externos.
- **OCR local:** ejecutar el motor OCR en el dispositivo con modelos de idioma almacenados localmente. Preparar recorte de regiones, corrección de orientación, contraste y resolución para reducir tiempo de procesamiento. No subir la fotografía de la etiqueta al servidor por defecto.
- **Geocodificación offline:** disponer de un índice local de calles, rangos de numeración y municipios del Valle de Aburrá. Las teselas MBTiles son imágenes de mapa y por sí solas no permiten convertir una dirección en coordenadas.
- **Optimización vial offline:** disponer de una red de calles enrutable (grafo vial) y un motor local de rutas. MBTiles no contiene necesariamente sentidos viales, restricciones, conexiones ni costos de recorrido.
- **Ordenamiento:** optimizar la secuencia sobre distancias/costos de la red vial, no únicamente sobre distancia en línea recta. Mantener soporte para más de ocho paradas y recalcular desde el GPS actual después de cada entrega.
- **Persistencia:** guardar paradas, coordenadas, estados, orden y cola de sincronización en almacenamiento local persistente. Cada parada debe tener identificador idempotente para evitar duplicados al reconectar.
- **Sincronización:** transmitir únicamente los campos necesarios, validar permisos en backend y reflejar los cambios en el panel administrativo. Mostrar claramente si una operación está guardada en el dispositivo o confirmada por el servidor.
- **Paquete offline:** permitir instalar/actualizar mapas, índice de direcciones y red vial de la zona de trabajo antes de salir. Informar versión, cobertura, tamaño y fecha de actualización del paquete.

### Límites técnicos actuales que deben resolverse

El estado actual del repositorio no equivale todavía a funcionamiento 100% offline:

- La captura de imagen llama al endpoint `POST /ocr-delivery-label`; Tesseract se ejecuta en el servidor. Por tanto, el OCR actual requiere conexión con el backend.
- Después de interpretar la guía, la interfaz consulta `/geocode`; el geocodificador usa ArcGIS y puede recurrir a Nominatim. No es geocodificación offline.
- El optimizador actual usa Haversine (distancia en línea recta), fuerza bruta hasta ocho paradas y heurística para conjuntos mayores. No calcula el costo real sobre calles ni produce por sí mismo instrucciones viales.
- El archivo MBTiles aporta teselas de mapa, pero no sustituye el índice geográfico ni el grafo vial necesarios para ubicar direcciones y calcular recorridos sin conexión.
- La sincronización de paradas nuevas offline ya existe parcialmente, pero el flujo completo de captura y geocodificación todavía depende de servicios conectados.

No se debe anunciar ni marcar el producto como 100% offline hasta implementar y probar todos esos componentes en modo avión en un dispositivo real.

### Uso complementario de Mercado Envíos Flex y límites de integración

Ruta Clara es una herramienta independiente de apoyo a la operación del domiciliario. No debe presentarse como aplicación oficial, integración certificada ni sustituto de la aplicación de Mercado Envíos Flex.

- El domiciliario continúa utilizando la aplicación oficial de Flex para las acciones que la operación o las condiciones de Mercado Libre exijan, incluida la confirmación oficial de eventos cuando corresponda.
- Ruta Clara no automatiza inicios de sesión, no controla la aplicación oficial, no intercepta su tráfico, no extrae datos de sesiones privadas, no consulta endpoints no documentados ni intenta eludir controles técnicos.
- La lectura local de QR y etiquetas queda condicionada al alcance de la autorización operativa recibida. La autorización verbal declarada por el usuario debe documentarse por escrito, identificando quién la concede y su facultad para hacerlo, qué campos se pueden tratar, finalidades, conservación, sincronización y proveedores involucrados.
- Antes del piloto con etiquetas reales, revisar las condiciones aplicables de Mercado Libre y el acuerdo con quien entrega/encarga los paquetes. La autorización de una persona no debe presumirse como autorización de todos los actores ni de los titulares de datos.
- Aplicar minimización, finalidad, acceso restringido, seguridad, calidad y retención limitada conforme a la Ley 1581 de 2012 y sus normas reglamentarias. Esta documentación técnica no constituye concepto jurídico ni garantiza riesgo legal cero; solicitar revisión de un abogado colombiano antes de producción.

Referencias para revisión:
- [Instructivo oficial de conductores de Envíos Flex Colombia](https://http2.mlstatic.com/frontend-assets/shipping-flex-frontend/instructivos/flex_drivers_co.pdf).
- [Especificación técnica de etiquetas de Mercado Envíos](https://developers.mercadolibre.com/es_ar/label).
- [Ley 1581 de 2012 — Protección de datos personales](https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=49981).
- [Decreto 1377 de 2013 — Reglamentación parcial de la Ley 1581](https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=53646).

### Exportación de documentos desde el menú hamburguesa

Las descargas son acciones ocasionales y no deben ocupar espacio en la vista operativa de paradas/rutas ni dispararse al tocar una ruta.

- Retirar de la tarjeta/lista de paradas los botones de Reporte PDF, Excel editable e Historial CSV.
- Ubicar esas acciones dentro del menú hamburguesa, bajo una sección **Documentos y exportaciones**.
- PDF y Excel exportan la ruta actualmente seleccionada. Si no existe ruta activa, informar el motivo sin iniciar una descarga.
- Historial CSV permanece disponible solo para administradores, respetando los permisos actuales.
- Al elegir una descarga, cerrar el menú y ejecutar únicamente la exportación solicitada. Nunca descargar automáticamente al seleccionar/cambiar una ruta ni al abrir la vista.
- Mantener los botones de exportación individual del panel administrativo y las restricciones de acceso existentes.

### Criterios de aceptación del nuevo flujo

1. En una prueba representativa, el domiciliario puede capturar y preparar una tanda completa en menos de cinco minutos; medir tiempo total y tiempo por etiqueta.
2. Una captura procesa QR y OCR desde la misma imagen, sin doble escaneo manual.
3. El identificador QR autorizado permite detectar duplicados, pero nunca se interpreta como dirección sin un formato documentado.
4. Ninguna etiqueta de remitente o devolución genera una parada.
5. Las lecturas ambiguas solicitan confirmación y nunca inventan una dirección.
6. En modo avión, QR, OCR, geocodificación local, ordenamiento, mapa y registro de entrega siguen operativos con el paquete offline instalado.
7. La ruta admite más de ocho paradas y utiliza costos de calles, no solo Haversine.
8. Después de entregar una parada, esta sale de pendientes, queda en historial y la siguiente se recalcula desde el GPS actual.
9. Al recuperar conexión, las paradas y estados se sincronizan sin duplicados y el administrador ve los cambios.
10. Los botones de PDF, Excel y CSV ya no aparecen en la vista de rutas; están en el menú hamburguesa y cada descarga requiere una acción explícita.
11. Las pruebas con etiquetas reales se realizan únicamente con autorización documentada y datos controlados; las imágenes de prueba se eliminan según la política definida.
