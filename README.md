# inicio-obra (PROTOTIPO DE PRUEBA, sin publicar)
PWA para el checklist asíncrono de Inicio de obra (protocolo v2, 26/10/2026), Tecnología ARME.
- Datos simulados (`api/mock.js`) que reflejan los modelos planeados en Odoo: `x_inicio_obra`, `x_inicio_obra_item`, `x_inicio_obra_area`, `x_inicio_obra_plantilla`.
- Checklist por área: `datos/checklist.json` (sección 5, tablas 2.1, info mínima de Logística, FCI y checklist 6.1).
- Probar: `python3 -m http.server 8877` → http://localhost:8877 (contraseña de prueba: `demo`).
- Producción (pendiente): backend propio igual que hys-carga (cuenta de servicio de Odoo en env de Render, token HMAC por usuario, la API key nunca va al teléfono). Sin nombres reales ni credenciales en este repo.
