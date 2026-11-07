# SECURITY — Ruta Clara

Estado: versión visual DEMO. Cámara y OCR **no** están activos. Los controles descritos son requisitos para la integración futura y deben pasar pruebas de seguridad antes de habilitarse.

## Activos
- Texto impreso de la zona inferior de la etiqueta: dirección, cliente/destinatario, nombre de unidad (datos personales).
- Imagen capturada (temporal).
- Claves de servicios de validación/rutas (solo backend).

## Amenazas y controles

| Amenaza | Control |
|---|---|
| Lectura de QR / códigos de barras / identificadores privados de Mercado Libre | Sin librerías QR/barcode en dependencias; sin detector de códigos; OCR solo sobre el recorte de la zona inferior autorizada; zonas superiores excluidas en la guía visual. |
| OCR produce campos extra (ids, números de envío) | Allowlist estricta `address`, `recipientName`, `unitName` en `sanitizeOcrResult`; todo lo demás se rechaza y no se infiere. |
| Exfiltración de imágenes | OCR local en el dispositivo; prohibido enviar imágenes a APIs externas. |
| Persistencia de imágenes | No se guarda la imagen completa; el recorte temporal se descarta tras extraer texto. |
| Recorte incorrecto incluye códigos | Si no se aísla la zona autorizada, se detiene el proceso y se pide recaptura manual. |
| Permisos excesivos | Cámara solo al pulsar "Iniciar escaneo"; sin geolocalización hasta "Recalcular desde GPS". |
| Exposición de claves API | Claves únicamente en funciones de servidor; nunca en el bundle del cliente. |
| Fuga en logs | Los eventos registran acción/estado, nunca nombres, direcciones ni imágenes. |
| Falsa sensación de seguridad | La UI no muestra sellos de seguridad; indica "lectura local", "zona autorizada detectada" y "códigos excluidos por diseño". |

## Verificaciones antes de habilitar el escáner
1. Auditoría de dependencias: ningún paquete de QR/barcode (zxing, quagga, jsqr, html5-qrcode, BarcodeDetector, etc.).
2. Prueba de red: escanear sin tráfico saliente con imágenes.
3. Prueba de allowlist con salidas OCR maliciosas.
4. Prueba de recorte con etiquetas sintéticas (nunca reales).
5. Revisión de almacenamiento: sin imágenes en IndexedDB/localStorage/caché.

## Reporte
Reporte vulnerabilidades al responsable del proyecto en privado.