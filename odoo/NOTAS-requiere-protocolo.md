# Check «Requiere protocolo de inicio de obra» (prep 2026-11-06)

## Decisión de Jorge
En el modal **Crear proyecto desde plantilla** (desde la orden de venta), casilla
**Requiere protocolo de inicio de obra**, default **desmarcada**.

- Marcada → se crea `x_inicio_obra` + áreas + ítems (como hoy post-parche SA 2638).
- Desmarcada → **no** se crea `x_inicio_obra` en absoluto.
- En el tablero del proyecto **nunca** van las `project.task` «Inicio de obra · …»
  (ya aplicado 2026-11-06).

## Dónde lo ve Comercial
1. Orden de venta → botón **Crear proyecto** (SA 2419 «Abrir asistente…»).
2. Modal `target=new` título «Crear proyecto desde plantilla».
3. Campos: Orden, Cliente, Empresa, Nombre del proyecto, **Plantilla**,
   **[NUEVO] Requiere protocolo de inicio de obra**, Proyecto creado.
4. Botón header **Crear proyecto ahora** → SA 2420.

## IDs Odoo (prod cooperativa-de-trabajo-el-sol)
| Pieza | Id / nombre |
|---|---|
| Modelo wizard | `x_crear_proyecto_desde` (ir.model #1953) |
| Form primary | view #8245 |
| Form Studio | view #8247 (agrega plantilla / nombre / OV) |
| Abrir modal | SA #2419 |
| Crear proyecto | SA #2420 «Crear proyecto» |
| Automation | #138 «Inicio de obra · al crear OT» `on_create` project.project |
| CODE_CREAR | SA #2638 |
| Campo flag | `x_io_requiere_protocolo` (boolean) en wizard **y** `project.project` |
| Vista wizard ARME | inherit #8245 prio 200, xpath after `x_studio_plantilla_de_proyecto` |
| Vista proyecto ARME | inherit #1989 prio 200, after `partner_id` |

## Gate exacto (CODE_CREAR)
```python
for prj in records:
    if prj.x_io_inicio_id: continue
    if not prj.x_io_requiere_protocolo: continue
    # … crea x_inicio_obra + tareas/ítems de área …
```

## Por qué el flag va en el `copy` (SA 2420)
La automation 138 es **on_create**. Si el flag se escribiera después del
`template.copy(...)`, CODE_CREAR ya corrió con el default `False` y no
re-dispara. Por eso SA 2420 mete `vals_project['x_io_requiere_protocolo']`
**antes** del copy (marcador `# [ARME IO] flag protocolo`).

## Default
Boolean Odoo sin valor = `False`. Casilla desmarcada al abrir el asistente
(SA 2419 no setea el campo).

## Huellas pre-parche (2026-11-06, America/Cordoba)
- SA 2638 CODE_CREAR vivo (sin gate, sin project.task): `7477ed7d5334cd9a14709651798b58cb1a9e47793406ae5fce97e6440fefb14e`
- SA 2420 vivo: `645ba5d13a5f23faca3cb127aebca43216085a5b3bd7df01274d0515e9ed5592`
- CODE_CREAR nuevo (con gate): `652304ef49b5678bf2abb8ec4f3bcfbc2ce11286834dd6d1bd7e8ad813474b11`
- SA 2420 nuevo: `50e46131bf0a654993782a5ecdcd1e21661308dd3a845baf42674e9b8d98f4dc`

## Scripts (NO corridos con --aplicar en esta prep)
```bash
cd /workspace/inicio-obra/app/odoo
python3 migrar_requiere_protocolo.py revisar
python3 migrar_requiere_protocolo.py revisar --diff
python3 migrar_requiere_protocolo.py backup
# solo con OK de Jorge:
python3 migrar_requiere_protocolo.py aplicar --confirmo-produccion
python3 migrar_requiere_protocolo.py revertir backup-requiere-protocolo-….json --confirmo-produccion
```

## coop-prueba
No hay base de prueba apuntada (`ODOO_URL`/`ODOO_DB` = prod). Prep = docs +
artefactos + `revisar` dry contra prod.

## Preguntas abiertas
1. Proyecto creado **sin** el wizard (Proyectos → Nuevo): flag default False →
   no hay protocolo. ¿Hace falta un botón «Generar protocolo» en el form del
   proyecto para los casos manuales?
2. Proyectos **ya** creados con `x_inicio_obra`: no se tocan. El campo nuevo
   queda False aunque exista protocolo (solo informativo hacia adelante, o
   ¿backfill True donde `x_io_inicio_id`?).
3. ¿Etiqueta exacta en el modal OK, o preferís «Requiere inicio de obra» más corta?

## Rollback
`migrar_requiere_protocolo.py revertir <backup> --confirmo-produccion` restaura
SA 2420 y SA 2638. Las vistas ARME creadas en ese apply se unlink-ean. Los
campos boolean nuevos **no** se borran solos (aviso en consola); unlink manual
si hace falta.

## Aplicado en producción (2026-11-06 ~17:52 America/Cordoba)
OK de Jorge. Backup: `odoo/backup-requiere-protocolo-20261106-175254.json`

| Pieza | Antes | Después |
|---|---|---|
| SA 2420 | `645ba5d1…` | `50e46131…` |
| SA 2638 | `7477ed7d…` | `652304ef…` |
| Campo project | — | id **44874** |
| Campo wizard | — | id **44876** |
| Vista wizard | — | id **8585** |
| Vista proyecto | — | id **8586** |

Rollback:
```bash
python3 migrar_requiere_protocolo.py revertir backup-requiere-protocolo-20261106-175254.json --confirmo-produccion
```


## Update 2026-11-06 ~18:01 America/Cordoba — selection obligatoria
Jorge: reemplazar checkbox por desplegable **Requiere / No requiere**, vacío al abrir, `required`.

Backup: `odoo/backup-requiere-seleccion-20261106-180152.json`

| Pieza | Cambio |
|---|---|
| Wizard field boolean #44876 | unlink |
| Wizard field selection | **#44878** `x_io_requiere_protocolo` options requiere/no_requiere, required=True |
| selection lines | #7860 Requiere, #7861 No requiere |
| Project field | sigue boolean **#44874** |
| Vista wizard #8585 | `required="1"`, label «Protocolo de inicio de obra» |
| SA 2420 | `50e46131…` → `5f29bbdc…` (mapea selection → boolean en copy) |
| SA 2638 | sin cambio (`652304ef…`) |

Rollback:
```bash
python3 migrar_requiere_seleccion.py revertir backup-requiere-seleccion-20261106-180152.json --confirmo-produccion
```
