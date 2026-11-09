# Ruta Clara
PWA móvil en español para gestión de entregas de última milla con autenticación y aislamiento de datos por empresa.
## Arquitectura
- React 19, TanStack Start/Router, Vite y TypeScript.
- Supabase Auth para cuentas de empresa y sesiones.
- PostgreSQL con Row Level Security (RLS) para aislar organizaciones.
- \`supabase/migrations/\` contiene el esquema y políticas de seguridad.
- \`src/lib/supabase-data.ts\` conecta la aplicación con la API de datos.
## Configuración local
1. Crea un proyecto en Supabase.
2. Ejecuta \`supabase/migrations/202611090001_initial_multi_tenant.sql\` en SQL Editor.
3. Copia \`.env.example\` a \`.env.local\` y agrega la URL y la clave publicable/anon de Supabase.
4. Configura la URL de retorno y confirmación de correo en Authentication > URL Configuration de Supabase.
5. Ejecuta \`bun install\`, \`bun run dev\`, \`bun run test\` y \`bun run build\`.
## Variables de entorno
- \`VITE_SUPABASE_URL\`: URL pública del proyecto Supabase.
- \`VITE_SUPABASE_ANON_KEY\`: clave publicable/anon. Es segura para el navegador solo porque RLS está habilitado y las políticas limitan cada organización.
Nunca agregues \`service_role\`, contraseñas de base de datos ni secretos de servidor a variables \`VITE_*\` o al repositorio.
## Modelo de acceso
- El primer usuario que se registra crea una organización y queda como \`owner\`.
- Los roles definidos son \`owner\`, \`admin\` y \`driver\`.
- Los miembros solo consultan registros de su organización.
- Propietarios y administradores gestionan entregas.
- Los repartidores cambian el estado únicamente de las entregas asignadas mediante una función SQL controlada.
La creación de usuarios adicionales y asignación de repartidores requiere implementar el flujo de invitaciones antes de operar con un equipo real.
## Alcance pendiente
- Invitaciones y administración de miembros.
- Pruebas de integración con un proyecto Supabase real.
- Escáner OCR local, geocodificación y optimización de rutas.
- Despliegue con variables de entorno configuradas.
