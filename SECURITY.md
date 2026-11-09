# SECURITY — Ruta Clara
## Autenticación y aislamiento
- Supabase Auth emite y renueva tokens de sesión.
- La aplicación usa únicamente la clave publicable/anon en el navegador.
- No se incluye ni se debe incluir la clave \`service_role\` en el frontend.
- Cada usuario recibe una organización propia al registrarse.
- Las tablas \`organizations\`, \`profiles\`, \`memberships\` y \`deliveries\` tienen Row Level Security habilitado.
- Las políticas validan la membresía y el rol en PostgreSQL; ocultar botones en la interfaz no sustituye la autorización de base de datos.
- El rol \`driver\` cambia estados solo en entregas asignadas mediante \`update_assigned_delivery_status\`.
## Datos de entrega
Los campos permitidos en el flujo OCR siguen siendo \`address\`, \`recipientName\` y \`unitName\`. No leer QR, códigos de barras ni identificadores codificados. Las imágenes no deben enviarse a APIs externas ni persistirse.
## Antes de producción
1. Ejecutar la migración en un proyecto Supabase nuevo y verificar todas las políticas RLS.
2. Probar que un usuario de una organización no puede leer ni modificar filas de otra.
3. Probar roles owner, admin y driver, incluida la asignación de entregas.
4. Configurar confirmación de correo, recuperación de contraseña y URLs permitidas.
5. Revisar dependencias y ejecutar pruebas automatizadas.
6. Configurar HTTPS, variables de entorno y protección de despliegue.
7. Habilitar cámara/OCR solo después de pruebas de recorte, privacidad y tráfico de red.
Reporta vulnerabilidades al responsable del proyecto en privado.
