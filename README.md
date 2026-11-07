# Ruta Clara

PWA móvil (es-CO) para gestión de entregas de última milla. **Versión visual DEMO**: todos los datos son ficticios.

## Alcance actual
- Pantallas: Inicio, Escáner (simulado), Revisión, Ruta, Entregas, Historial, Seguridad.
- Navegación inferior en móvil y barra lateral en escritorio.
- Estado en memoria (se reinicia al recargar).

## Límites de la demo
- Sin cámara, sin OCR, sin permisos del dispositivo.
- Sin validación de direcciones ni optimización de rutas: se muestran como "Próximamente".
- Mapa, distancia y tiempo son ilustrativos.
- Sin base de datos, sin claves API, sin servicios externos, sin publicación.

## Decisiones de seguridad
Ver [SECURITY.md](./SECURITY.md). Resumen: nunca leer QR/códigos de barras; OCR local solo sobre la zona inferior autorizada; solo 3 campos permitidos; sin guardar imágenes; claves solo en backend.

## Arquitectura
```
src/domain/       reglas puras (límite 30, allowlist OCR, duplicados, estados de entrega)
src/adapters/     puertos: scanner, address-validation, route-optimization, persistence (no implementados)
src/state/        store DEMO en memoria
src/components/   UI (AppShell + shadcn/ui)
src/routes/       pantallas
```
La UI depende del dominio; los adaptadores se conectarán detrás de interfaces. Validación y rutas irán en funciones de servidor.

## Pruebas
`bun run test` — `src/domain/deliveries.test.ts` cubre: máximo 30 paradas, allowlist OCR, rechazo de campos, duplicados por dirección normalizada y transiciones de estado.

Plan futuro: pruebas de red sin tráfico de imágenes, auditoría de dependencias de códigos, pruebas de recorte con etiquetas sintéticas.