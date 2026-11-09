# SECURITY — Ruta Clara

Estado: la autenticación y el almacenamiento multiempresa están implementados en una rama de trabajo. Cámara y OCR **no** están activos. Las integraciones de cámara, OCR, geolocalización y rutas deben pasar pruebas de seguridad antes de habilitarse.

## Activos
- Texto impreso de la zona inferior de la etiqueta: dirección, cliente/destinatario, nombre de unidad (datos personales).
- Imagen capturada (temporal).
- Tokens de sesión y datos de entregas por organización.
- Claves de servicios de validación/rutas (solo backend).

## Amenazas y controles

| Amenaza | Control |
|---|---|
| Lectura de QR / códigos de barras / identificadores privados de Mercado Libre | Sin librerías QR/barcode en dependencias; sin detector de códigos; OCR solo sobre el recorte de la zona inferior autorizada; zonas superiores excluidas en la guía visual. |
| OCR produce campos extra (ids, números de envío) | Allowlist estricta \`address\`, \`recipientName\`, \`unitName\` en \`sanitizeOcrResult\`; todo lo demás se rechaza y no se infiere. |
| Exfiltración de imágenes | OCR local en el dispositivo; prohibido enviar imágenes a APIs externas. |
| Persistencia de imágenes | No se guarda la imagen completa; el recorte temporal se descarta tras extraer texto. |
| Recorte incorrecto incluye códigos | Si no se aísla la zona autorizada, se detiene el proceso y se pide recaptura manual. |
| Permisos excesivos | Cámara solo al pulsar "Iniciar escaneo"; sin geolocalización hasta "Recalcular desde GPS". |
| Exposición de claves API | El frontend usa solo la clave publicable/anon de Supabase. La clave \`service_role\`, contraseñas y claves de otros servicios deben permanecer en servidor. |
| Fuga en logs | Los eventos registran acción/estado, nunca nombres, direcciones ni imágenes. |
| Falsa sensación de seguridad | La UI identifica claramente las funciones que siguen siendo simuladas y no presenta el mapa como georreferenciado. |

## Autenticación y aislamiento
- Supabase Auth gestiona las cuentas y tokens de sesión.
- El primer registro crea una organización y asigna el rol \`owner\`.
- Las invitaciones son códigos aleatorios de un solo uso, con vencimiento de siete días; se almacena un hash del código.
- Las tablas \`organizations\`, \`profiles\`, \`memberships\` y \`deliveries\` tienen RLS habilitado.
- Propietarios y administradores gestionan entregas; los repartidores solo consultan entregas asignadas y cambian su estado mediante una función SQL restringida.
- La UI no sustituye la autorización: las políticas y funciones de PostgreSQL deben ser la barrera efectiva.
- No se debe desplegar con datos reales hasta probar que una cuenta de otra organización no puede leer ni modificar registros.

## Verificaciones antes de habilitar el escáner
1. Auditoría de dependencias: ningún paquete de QR/barcode (zxing, quagga, jsqr, html5-qrcode, BarcodeDetector, etc.).
2. Prueba de red: escanear sin tráfico saliente con imágenes.
3. Prueba de allowlist con salidas OCR maliciosas.
4. Prueba de recorte con etiquetas sintéticas (nunca reales).
5. Revisión de almacenamiento: sin imágenes en IndexedDB/localStorage/caché.

## Verificaciones antes de producción
1. Ejecutar la migración en un proyecto Supabase nuevo.
2. Probar aislamiento RLS con al menos dos organizaciones y sus tres roles.
3. Probar expiración, reutilización y código inválido de invitaciones.
4. Configurar confirmación de correo, recuperación de contraseña y URLs permitidas.
5. Revisar dependencias y ejecutar pruebas automatizadas.
6. Configurar HTTPS y variables de entorno sin secretos en el cliente.

## Reporte
Reporta vulnerabilidades al responsable del proyecto en privado.
