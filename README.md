# Inicio de obra · Tecnología ARME
PWA para celular + backend Node (sin dependencias) para el checklist asíncrono de **Inicio de obra** (protocolo v2): cada gerente completa su área desde el teléfono, UGEOP/Secretaría ven el consolidado, el COO recibe aviso al 100 % y el CEO aprueba o devuelve como *Observado* (historial de rondas).

## Cómo ingresa cada usuario
- Con **su mismo usuario de Odoo** (email) y **su contraseña**. Si entra a Odoo con Google o tiene doble factor: Odoo › Mi perfil › Seguridad › *Nueva clave API* y usa esa clave como contraseña.
- Además tiene que figurar **activo** en Odoo › Proyecto › Inicio de obra › Usuarios de la app (rol y áreas).
- La app **no guarda contraseñas** ni usa cuentas de servicio: el backend verifica la credencial contra Odoo y opera con la sesión del propio usuario, así cada tilde queda sellada en Odoo con su usuario, fecha y hora. La credencial viaja solo dentro de un token cifrado (AES‑256‑GCM) con la clave `IO_SESSION_SECRET`, que vive en el entorno del servidor.

## Variables de entorno (Render)
| Variable | Uso |
|---|---|
| `ODOO_URL`, `ODOO_DB` | Instancia de Odoo |
| `IO_SESSION_SECRET` | ≥32 caracteres aleatorios. Cambiarla cierra todas las sesiones |
| `SESSION_DAYS` (30), `RATE_LIMIT_PER_MIN` (120), `MAX_BODY_MB` (12), `DIAS_APROBADAS` (15) | Opcionales |

## Desarrollo
`npm start` (Node ≥ 20). Modo demo sin Odoo: abrir `/?demo` (contraseña `demo`, datos de ejemplo en el navegador).

## Estructura
- `server.js` API `/api/*` + archivos estáticos de `public/`. `GET /api/salud` para monitoreo.
- `public/` PWA (`app.js`, `api/odoo.js` real, `api/mock.js` demo, `datos/checklist.json`).
- `odoo/plan_inicio_obra.py` script que crea los modelos `x_inicio_obra*`, acciones y automatizaciones en Odoo (seco/aplicar/rollback). Los usuarios reales se cargan desde un archivo local que **no** está en el repo.
