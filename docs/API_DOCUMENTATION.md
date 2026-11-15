# Guía de API y Referencia Técnica - Ruta Clara

Esta documentación proporciona detalles técnicos exhaustivos sobre la estructura de la API, modelos de datos, algoritmos de optimización y ejemplos de integración HTTP.

---

## ⚙️ Algoritmo de Optimización de Ruta

La optimización de rutas en **Ruta Clara** se realiza en dos etapas principales:

### 1. Fórmula del Haversine
Se utiliza la fórmula del Haversine para calcular la distancia del gran círculo entre dos puntos en la superficie de una esfera (la Tierra) dadas sus longitudes y latitudes:

$$\text{dlat} = \text{lat}_2 - \text{lat}_1$$
$$\text{dlon} = \text{lon}_2 - \text{lon}_1$$
$$a = \sin^2\left(\frac{\text{dlat}}{2}\right) + \cos(\text{lat}_1) \cdot \cos(\text{lat}_2) \cdot \sin^2\left(\frac{\text{dlon}}{2}\right)$$
$$c = 2 \cdot \text{atan2}\left(\sqrt{a}, \sqrt{1-a}\right)$$
$$d = R \cdot c$$

Donde $R = 6371.0 \text{ km}$ (Radio medio de la Tierra).

### 2. Resolución del Problema del Viajante (TSP)
- **Para $N \le 8$ (Solución Exacta)**: Se evalúan todas las permutaciones posibles de las ubicaciones ($O(N!)$) para garantizar la ruta globalmente óptima de menor distancia absoluta.
- **Para $N > 8$ (Solución Escalable)**: Se aplica la heurística del *Vecino Más Cercano (Nearest Neighbor)* para evitar cuellos de botella computacionales, garantizando un tiempo de respuesta rápido con complejidad $O(N^2)$.

---

## 📡 Referencia de Endpoints HTTP

### 1. Autenticación y Registro

#### Registrar Usuario
- **Ruta**: `POST /register`
- **Cuerpo de la Solicitud** (`application/json`):
```json
{
  "username": "operador_ruta",
  "email": "operador@rutaclara.com",
  "password": "PasswordSeguro123!"
}
```
- **Respuesta de Éxito** (`201 Created`):
```json
{
  "id": 1,
  "username": "operador_ruta",
  "email": "operador@rutaclara.com",
  "disabled": false
}
```

#### Obtener Token JWT
- **Ruta**: `POST /token`
- **Cuerpo de la Solicitud** (`application/x-www-form-urlencoded`):
```text
username=operador_ruta&password=PasswordSeguro123!
```
- **Respuesta de Éxito** (`200 OK`):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

### 2. Ubicaciones

#### Registrar Ubicación
- **Ruta**: `POST /locations`
- **Cabecera**: `Authorization: Bearer <token_jwt>`
- **Cuerpo de la Solicitud** (`application/json`):
```json
{
  "name": "Centro de Distribución Norte",
  "latitude": 4.7110,
  "longitude": -74.0721
}
```
- **Respuesta de Éxito** (`201 Created`):
```json
{
  "id": 1,
  "name": "Centro de Distribución Norte",
  "latitude": 4.7110,
  "longitude": -74.0721,
  "references": []
}
```

#### Listar Ubicaciones
- **Ruta**: `GET /locations`
- **Cabecera**: `Authorization: Bearer <token_jwt>`
- **Respuesta de Éxito** (`200 OK`):
```json
[
  {
    "id": 1,
    "name": "Centro de Distribución Norte",
    "latitude": 4.7110,
    "longitude": -74.0721,
    "references": []
  },
  {
    "id": 2,
    "name": "Punto de Entrega Chapinero",
    "latitude": 4.6486,
    "longitude": -74.0628,
    "references": []
  }
]
```

---

### 3. Ruta Óptima

#### Calcular Ruta Óptima
- **Ruta**: `GET /optimal_route`
- **Cabecera**: `Authorization: Bearer <token_jwt>`
- **Respuesta de Éxito** (`200 OK`): Devuelve la secuencia de ubicaciones en el orden óptimo de visita.
```json
[
  {
    "id": 1,
    "name": "Centro de Distribución Norte",
    "latitude": 4.7110,
    "longitude": -74.0721,
    "references": []
  },
  {
    "id": 2,
    "name": "Punto de Entrega Chapinero",
    "latitude": 4.6486,
    "longitude": -74.0628,
    "references": []
  }
]
```

---

## 4. Reporte profesional de recorridos

### Descargar PDF
- **Ruta**: `GET /export/delivery-route.pdf`
- **Autenticación**: sesión activa.
- **Parámetros opcionales**:
  - `route_id`: exporta todas las paradas de una ruta específica.
  - `driver_id`: disponible solo para administradores; genera el informe del domiciliario seleccionado de los últimos siete días si no se especifica `route_id`.
- Los domiciliarios solo pueden exportar sus propios recorridos. Los administradores pueden exportar una ruta completa o seleccionar un domiciliario.
- El PDF incluye responsable, periodo, conteos de paradas/entregas/pendientes/novedades, direcciones, municipio/barrio, referencias de acceso, estado y última actualización.
- El documento es compacto, tamaño A4, con pie de página de marca Ruta Clara y numeración. No incluye nombres de destinatarios ni códigos de seguimiento.
- Respuestas: `200 application/pdf`; `403` sin permisos; `404` si no hay paradas; `422` si falta seleccionar ruta o domiciliario.

### Exportación de datos
El CSV semanal existente se conserva como formato tabular para análisis en Excel. El PDF es el formato recomendado para imprimir, compartir y archivar un recorrido.

## 5. Seguridad del mapa
Los eventos de toque/clic del mapa no crean, guardan ni geocodifican paradas. El mapa solo permite consultar puntos ya registrados y navegar. Las nuevas paradas se ingresan mediante formulario, dictado por voz o escáner OCR, y requieren la acción explícita del usuario.
