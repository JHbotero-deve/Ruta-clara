# Ruta Clara

PWA móvil (es-CO) para gestión de entregas de última milla, con autenticación y datos en la nube por empresa.

## Alcance actual
- Inicio de sesión y registro de empresas con Supabase Auth.
- Roles owner, admin y driver; invitaciones de un solo uso para incorporar miembros.
- Entregas almacenadas en PostgreSQL y asignables a repartidores.
- Políticas Row Level Security (RLS) para separar los datos por organización.
- Pantallas: Inicio, Escáner (simulado), Revisión, Ruta, Entregas, Historial, Equipo y Seguridad.
- Navegación inferior en móvil y barra lateral en escritorio.

## Límites actuales
- Cámara y OCR todavía no están activos.
- Sin validación de direcciones ni optimización de rutas.
- Mapa, distancia y tiempo siguen siendo ilustrativos.
- El backend Supabase debe configurarse y probarse antes de operar con datos reales.

## Arquitectura
\`\`\`
src/domain/       reglas puras (límite 30, allowlist OCR, duplicados, estados)
src/adapters/     puertos de scanner, validación de direcciones, rutas y persistencia
src/lib/          autenticación y acceso a Supabase
src/state/        sesión y estado de entregas
src/components/   UI (AppShell + shadcn/ui)
src/routes/       pantallas
supabase/         migraciones SQL y políticas RLS
\`\`\`

## Configuración
1. Crea un proyecto Supabase.
2. Ejecuta \`supabase/migrations/202611090001_initial_multi_tenant.sql\` en SQL Editor.
3. Copia \`.env.example\` a \`.env.local\` y agrega \`VITE_SUPABASE_URL\` y \`VITE_SUPABASE_ANON_KEY\`.
4. Configura confirmación de correo y URLs permitidas en Authentication > URL Configuration.
5. Ejecuta \`bun install\`, \`bun run dev\`, \`bun run test\` y \`bun run build\`.

La clave publicable/anon puede estar en el navegador únicamente con RLS activo y políticas correctas. Nunca agregues \`service_role\`, contraseñas de base de datos ni secretos a variables \`VITE_*\`.

## Pruebas
\`bun run test\` — \`src/domain/deliveries.test.ts\` cubre máximo de paradas, allowlist OCR, rechazo de campos, duplicados y transiciones de estado.

CI ejecuta pruebas y build en cada pull request. Antes de producción hay que probar registro, confirmación de correo, invitaciones y aislamiento RLS con dos organizaciones reales.
