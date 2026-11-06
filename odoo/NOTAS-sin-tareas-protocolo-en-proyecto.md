# Sin tareas de protocolo en el proyecto (prep 2026-11-06)

## Decisión de Jorge (6 nov)
Al crear un proyecto desde plantilla, **solo** se crean las tareas de la plantilla.
Las filas `project.task` «Inicio de obra · {área}» **nunca** deben crearse en el proyecto,
haya o no protocolo. El trabajo del protocolo vive en `x_inicio_obra` / checklists
(app y menú Inicio de obra).

## Qué hace CODE_CREAR (SA 2638) después del parche
1. Si el proyecto ya tiene `x_io_inicio_id`, no hace nada.
2. Crea `x_inicio_obra` ligado al proyecto y escribe `project.project.x_io_inicio_id`.
3. Por cada área activa: crea `x_inicio_obra_tarea` con `x_vence` (lun–sáb).
4. Crea en lote los `x_inicio_obra_item` de la plantilla del área (con `x_vence`).
5. **No** llama a `project.task.create`. No asigna `user_ids` ni `date_deadline` en el tablero.
6. `x_task_id` en tarea/ítem queda vacío (campo opcional).

## Cómo funciona la app sin project.task
- `server.js` ya lee solo `x_inicio_obra`, `_tarea`, `_item`, `_ronda` (no usa `x_task_id`).
- Plazos: `x_vence` en área e ítem.
- Asignación de área: `x_inicio_obra_usuario.x_area_ids` (quién ve qué en la app).
- Avisos de vencimiento (cron SA): actividades sobre `x_inicio_obra_tarea`, no sobre `project.task`.
- CODE_ITEM aún tiene un bucle que marca `state` en `x_task_id` si existe; con `x_task_id` vacío
  `mapped('x_task_id')` no hace nada. No hace falta tocar CODE_ITEM para este parche.

## Qué se pierde al no crear project.task
- Esas 11 filas dejan de aparecer en el kanban/lista del proyecto (deseado).
- Ya no hay asignación Odoo nativa (`user_ids`) ni deadline visible en Proyecto → Tareas
  para el protocolo (antes era redundante con la app).

## Pendiente → prep lista (2026-11-06)
Jorge pidió el check del comercial. Prep en rama `feat/requiere-protocolo-checkbox`
(`migrar_requiere_protocolo.py` + NOTAS-requiere-protocolo.md). **No aplicado** aún:
hasta el OK, CODE_CREAR sigue auto-creando `x_inicio_obra` en toda OT nueva.

## Scripts (no corridos en prod en esta prep)
- `migrar_sin_tareas_protocolo_en_proyecto.py` — revisar | backup | aplicar | revertir
- `limpiar_tareas_protocolo_existentes.py` — opcional, para las ~78 tareas ya creadas

Huella CODE_CREAR vivo pre-parche (2026-11-06):
`998f7d24ea7ad34b624e0f6996880c0401516a090bfdc7717ff9d3b0b5caf895`

## Incidente durante la prep (2026-11-06 ~16:48 ART / America/Cordoba)
Al probar el argparse se aplicó por error el CODE_CREAR nuevo unos segundos y se **revirtió** al instante
con `backup-sin-tareas-protocolo-20261106-164807.json`. Huella viva verificada de nuevo =
`998f7d24ea7ad34b624e0f6996880c0401516a090bfdc7717ff9d3b0b5caf895` (código original con project.task.create).
No se tocó limpieza de tareas existentes.
