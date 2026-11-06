#!/usr/bin/env python3
"""Check «Requiere protocolo de inicio de obra» en el wizard Crear proyecto desde plantilla.

Flujo Comercial (venta → botón Crear proyecto → modal):
  1. Casilla en x_crear_proyecto_desde (default OFF).
  2. SA 2420 copia el flag a project.project.x_io_requiere_protocolo en el copy
     (antes del create: automation 138 es on_create).
  3. SA 2638 / CODE_CREAR solo crea x_inicio_obra (+ áreas/ítems) si el flag es True.
     Nunca crea project.task de protocolo (parche previo).

NO aplica a producción salvo --aplicar --confirmo-produccion.

Uso:
  python3 migrar_requiere_protocolo.py revisar
  python3 migrar_requiere_protocolo.py backup
  python3 migrar_requiere_protocolo.py aplicar --confirmo-produccion
  python3 migrar_requiere_protocolo.py revertir backup-requiere-protocolo-….json --confirmo-produccion

Credenciales: ODOO_URL, ODOO_DB, ODOO_API_KEY (o ODOO_API_KEY_ADMIN_ARME), ODOO_UID (default 2).
Nunca imprime secretos.
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time, difflib, xmlrpc.client
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plan_inicio_obra as plan

SA_CREAR_NAME = "Inicio de obra · crear tareas por área"
SA_CREAR_ID = 2638
AUTO_NAME = "Inicio de obra · al crear OT"
AUTO_ID = 138
SA_WIZ_NAME = "Crear proyecto"  # SA 2420 on x_crear_proyecto_desde
SA_WIZ_ID = 2420
WIZ_MODEL = "x_crear_proyecto_desde"
PROJ_MODEL = "project.project"
FIELD = "x_io_requiere_protocolo"
FIELD_LABEL = "Requiere protocolo de inicio de obra"
VIEW_WIZ_PARENT = 8245  # Default form view for x_crear_proyecto_desde
VIEW_WIZ_STUDIO = 8247  # Studio customization (has plantilla field)
VIEW_PROJ_PARENT = 1989  # project.project.form
MARKER = "[ARME IO] flag protocolo"

# Huellas verificadas 2026-11-06 (America/Cordoba) antes de este parche.
ESPERADO_CODE_CREAR = "7477ed7d5334cd9a14709651798b58cb1a9e47793406ae5fce97e6440fefb14e"
ESPERADO_SA2420 = "645ba5d13a5f23faca3cb127aebca43216085a5b3bd7df01274d0515e9ed5592"

huella = lambda c: hashlib.sha256((c or "").strip().encode()).hexdigest()


def conectar():
    url = os.environ.get("ODOO_URL", "https://cooperativa-de-trabajo-el-sol.odoo.com").rstrip("/")
    db = os.environ.get("ODOO_DB", "cooperativa-de-trabajo-el-sol")
    key = (os.environ.get("ODOO_API_KEY") or os.environ.get("ODOO_API_KEY_ADMIN_ARME", "")).strip()
    uid = int(os.environ.get("ODOO_UID", "2"))
    if not key:
        sys.exit("Falta ODOO_API_KEY / ODOO_API_KEY_ADMIN_ARME")
    m = xmlrpc.client.ServerProxy(url + "/xmlrpc/2/object", allow_none=True)
    return lambda model, method, *a, **k: m.execute_kw(db, uid, key, model, method, list(a), k)


def exigir_confirmacion(args):
    if not getattr(args, "confirmo_produccion", False):
        sys.exit("Abortado: falta --confirmo-produccion (no se escribe en producción).")


def mid(r, model):
    rows = r("ir.model", "search_read", [["model", "=", model]], fields=["id"])
    if not rows:
        sys.exit(f"No está el modelo {model}")
    return rows[0]["id"]


def field_exists(r, model, name):
    return bool(r("ir.model.fields", "search_count", [["model", "=", model], ["name", "=", name]]))


def leer_sa_crear(r):
    rows = r("ir.actions.server", "search_read", [["name", "=", SA_CREAR_NAME]],
             fields=["id", "name", "code", "model_id", "state"])
    if len(rows) != 1:
        sys.exit(f"Se esperaba 1 SA «{SA_CREAR_NAME}», hay {len(rows)}")
    return rows[0]


def leer_sa_wiz(r):
    rows = r("ir.actions.server", "read", [SA_WIZ_ID], ["id", "name", "code", "model_id", "state"])
    if not rows or rows[0]["name"] != SA_WIZ_NAME:
        # fallback by name + model
        rows = r("ir.actions.server", "search_read",
                 [["name", "=", SA_WIZ_NAME], ["model_id.model", "=", WIZ_MODEL]],
                 fields=["id", "name", "code", "model_id", "state"])
        if len(rows) != 1:
            sys.exit(f"No se encontró SA «{SA_WIZ_NAME}» en {WIZ_MODEL}")
    return rows[0]


def codigo_sa2420_nuevo():
    path = os.path.join(HERE, "SA2420_con_requiere_protocolo.py.txt")
    if not os.path.exists(path):
        sys.exit(f"Falta artefacto {path}")
    return Path(path).read_text()


def views_io(r):
    return r("ir.ui.view", "search_read",
             [["name", "ilike", "ARME IO requiere protocolo"]],
             fields=["id", "name", "model", "inherit_id", "arch_db", "priority"])


def cmd_revisar(r, diff=False):
    sa = leer_sa_crear(r)
    wiz = leer_sa_wiz(r)
    auto = r("base.automation", "search_read", [["name", "=", AUTO_NAME]],
             fields=["id", "name", "trigger", "action_server_ids", "active"])
    vivo_c = sa["code"] or ""
    nuevo_c = plan.CODE_CREAR
    vivo_w = wiz["code"] or ""
    nuevo_w = codigo_sa2420_nuevo()
    print("== revisar · check requiere protocolo ==")
    print(f"  wizard model: {WIZ_MODEL} (ir.model Studio «Crear proyecto desde venta»)")
    print(f"  modal views: form primary #{VIEW_WIZ_PARENT}, Studio #{VIEW_WIZ_STUDIO}")
    print(f"  SA wizard #{wiz['id']} «{wiz['name']}»  huella vivo={huella(vivo_w)}")
    print(f"             esperado pre-parche={ESPERADO_SA2420}  ({'OK' if huella(vivo_w)==ESPERADO_SA2420 else 'DISTINTO'})")
    print(f"             huella nuevo={huella(nuevo_w)}  marcado IO? {MARKER in vivo_w}")
    print(f"  SA CODE_CREAR #{sa['id']}  huella vivo={huella(vivo_c)}")
    print(f"             esperado pre-parche={ESPERADO_CODE_CREAR}  ({'OK' if huella(vivo_c)==ESPERADO_CODE_CREAR else 'DISTINTO'})")
    print(f"             huella nuevo={huella(nuevo_c)}")
    print(f"  automation: {[(a['id'], a['name'], a.get('trigger'), a.get('action_server_ids'), a.get('active')) for a in auto]}")
    print(f"  campo {PROJ_MODEL}.{FIELD}? {field_exists(r, PROJ_MODEL, FIELD)}")
    print(f"  campo {WIZ_MODEL}.{FIELD}? {field_exists(r, WIZ_MODEL, FIELD)}")
    print(f"  gate en vivo CODE_CREAR? {'if not prj.x_io_requiere_protocolo' in vivo_c}")
    print(f"  gate en plan CODE_CREAR? {'if not prj.x_io_requiere_protocolo' in nuevo_c}")
    print("  project.task.create en plan?", ("env['project.task'].create" in nuevo_c))
    vios = views_io(r)
    print(f"  vistas ARME IO: {[(v['id'], v['name'], v['model']) for v in vios]}")
    if diff:
        if huella(vivo_c) != huella(nuevo_c):
            sys.stdout.writelines(difflib.unified_diff(
                vivo_c.splitlines(True), nuevo_c.splitlines(True),
                fromfile="vivo-CODE_CREAR", tofile="plan.CODE_CREAR"))
        if huella(vivo_w) != huella(nuevo_w):
            sys.stdout.writelines(difflib.unified_diff(
                vivo_w.splitlines(True), nuevo_w.splitlines(True),
                fromfile="vivo-SA2420", tofile="SA2420_nuevo"))
    return sa, wiz, vivo_c, nuevo_c, vivo_w, nuevo_w


def cmd_backup(r):
    sa, wiz, *_ = cmd_revisar(r, diff=False)
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(HERE, f"backup-requiere-protocolo-{ts}.json")
    flds = r("ir.model.fields", "search_read",
             [["name", "=", FIELD], ["model", "in", [PROJ_MODEL, WIZ_MODEL]]],
             fields=["id", "model", "name", "ttype", "field_description", "state"])
    bk = {
        "ts": ts,
        "nota": "Backup pre-apply check requiere protocolo (campos + SA 2420 + SA 2638 + vistas ARME).",
        "sa2638": {"id": sa["id"], "name": sa["name"], "code": sa["code"], "huella": huella(sa["code"])},
        "sa2420": {"id": wiz["id"], "name": wiz["name"], "code": wiz["code"], "huella": huella(wiz["code"])},
        "fields": flds,
        "views_arme": views_io(r),
        "auto138": r("base.automation", "read", [AUTO_ID], ["id", "name", "trigger", "action_server_ids", "active"]),
    }
    json.dump(bk, open(path, "w"), ensure_ascii=False, indent=1)
    print("backup:", path)
    return path


def asegurar_campo(r, model, created):
    if field_exists(r, model, FIELD):
        print(f"  campo {model}.{FIELD} ya existe")
        rows = r("ir.model.fields", "search_read",
                 [["model", "=", model], ["name", "=", FIELD]], fields=["id"])
        return rows[0]["id"]
    fid = r("ir.model.fields", "create", {
        "name": FIELD,
        "field_description": FIELD_LABEL,
        "ttype": "boolean",
        "model_id": mid(r, model),
        "state": "manual",
        "copied": True,  # que copy de plantilla respete vals; default False en boolean
    })
    created["fields"].append({"model": model, "id": fid, "name": FIELD})
    print(f"  creado campo {model}.{FIELD} id={fid}")
    return fid


def asegurar_vista_wizard(r, created):
    existing = r("ir.ui.view", "search_read",
                 [["name", "=", "ARME IO requiere protocolo · wizard form"]],
                 fields=["id"])
    arch = f'''<?xml version="1.0"?>
<data>
  <xpath expr="//field[@name='x_studio_plantilla_de_proyecto']" position="after">
    <field name="{FIELD}"
           string="{FIELD_LABEL}"
           help="Si está marcado, al crear el proyecto se genera el protocolo de inicio de obra (checklist por área). Por defecto no."/>
  </xpath>
</data>'''
    if existing:
        r("ir.ui.view", "write", [existing[0]["id"]], {"arch_db": arch, "priority": 200})
        print(f"  vista wizard actualizada #{existing[0]['id']}")
        return existing[0]["id"]
    # Hereda del form primary; Studio (prio 99) agrega plantilla antes (prio 200).
    vid = r("ir.ui.view", "create", {
        "name": "ARME IO requiere protocolo · wizard form",
        "type": "form",
        "model": WIZ_MODEL,
        "mode": "extension",
        "inherit_id": VIEW_WIZ_PARENT,
        "priority": 200,
        "arch_db": arch,
    })
    created["views"].append({"id": vid, "name": "ARME IO requiere protocolo · wizard form"})
    print(f"  vista wizard creada #{vid}")
    return vid


def asegurar_vista_proyecto(r, created):
    existing = r("ir.ui.view", "search_read",
                 [["name", "=", "ARME IO requiere protocolo · project form"]],
                 fields=["id"])
    arch = f'''<?xml version="1.0"?>
<data>
  <xpath expr="//field[@name='partner_id']" position="after">
    <field name="{FIELD}" string="{FIELD_LABEL}"
           help="Indica si este proyecto disparó / debe tener protocolo de inicio de obra. Se setea desde el asistente de venta."/>
  </xpath>
</data>'''
    if existing:
        r("ir.ui.view", "write", [existing[0]["id"]], {"arch_db": arch, "priority": 200})
        print(f"  vista proyecto actualizada #{existing[0]['id']}")
        return existing[0]["id"]
    vid = r("ir.ui.view", "create", {
        "name": "ARME IO requiere protocolo · project form",
        "type": "form",
        "model": PROJ_MODEL,
        "mode": "extension",
        "inherit_id": VIEW_PROJ_PARENT,
        "priority": 200,
        "arch_db": arch,
    })
    created["views"].append({"id": vid, "name": "ARME IO requiere protocolo · project form"})
    print(f"  vista proyecto creada #{vid}")
    return vid


def cmd_aplicar(r, args):
    exigir_confirmacion(args)
    sa, wiz, vivo_c, nuevo_c, vivo_w, nuevo_w = cmd_revisar(r, diff=False)
    if "env['project.task'].create" in nuevo_c:
        sys.exit("El CODE_CREAR del plan todavía crea project.task; abortado.")
    if "if not prj.x_io_requiere_protocolo: continue" not in nuevo_c:
        sys.exit("El CODE_CREAR del plan no tiene el gate x_io_requiere_protocolo; abortado.")
    if MARKER not in nuevo_w:
        sys.exit("El artefacto SA2420 no tiene el marcador IO; abortado.")
    if huella(vivo_c) != ESPERADO_CODE_CREAR and huella(vivo_c) != huella(nuevo_c) and not args.forzar:
        sys.exit("CODE_CREAR vivo ≠ huella esperada. Revisar o --forzar.")
    if huella(vivo_w) != ESPERADO_SA2420 and MARKER not in vivo_w and not args.forzar:
        sys.exit("SA 2420 vivo ≠ huella esperada. Revisar o --forzar.")

    path = cmd_backup(r)
    created = {"fields": [], "views": []}

    print("-- campos --")
    asegurar_campo(r, PROJ_MODEL, created)
    asegurar_campo(r, WIZ_MODEL, created)

    print("-- vistas --")
    asegurar_vista_wizard(r, created)
    asegurar_vista_proyecto(r, created)

    print("-- SA 2420 (wizard) --")
    if MARKER in vivo_w and huella(vivo_w) == huella(nuevo_w):
        print("  SA 2420 ya está parcheado")
    else:
        r("ir.actions.server", "write", [wiz["id"]], {"code": nuevo_w})
        print(f"  SA #{wiz['id']} huella ahora {huella(nuevo_w)}")

    print("-- SA 2638 (CODE_CREAR) --")
    if huella(vivo_c) == huella(nuevo_c):
        print("  CODE_CREAR ya está parcheado")
    else:
        r("ir.actions.server", "write", [sa["id"]], {"code": nuevo_c})
        print(f"  SA #{sa['id']} huella ahora {huella(nuevo_c)}")

    # Anotar created en el backup para rollback fácil
    bk = json.load(open(path))
    bk["created_on_apply"] = created
    json.dump(bk, open(path, "w"), ensure_ascii=False, indent=1)

    print("aplicado.")
    print(f"rollback: python3 {os.path.basename(__file__)} revertir {os.path.basename(path)} --confirmo-produccion")


def cmd_revertir(r, args):
    exigir_confirmacion(args)
    path = args.backup
    if not os.path.isabs(path):
        cand = os.path.join(HERE, path)
        if os.path.exists(cand):
            path = cand
    bk = json.load(open(path))
    print("-- restaurar SA 2638 --")
    r("ir.actions.server", "write", [bk["sa2638"]["id"]], {"code": bk["sa2638"]["code"]})
    print(f"  huella {huella(bk['sa2638']['code'])}")
    print("-- restaurar SA 2420 --")
    r("ir.actions.server", "write", [bk["sa2420"]["id"]], {"code": bk["sa2420"]["code"]})
    print(f"  huella {huella(bk['sa2420']['code'])}")

    created = bk.get("created_on_apply") or {}
    for v in created.get("views") or []:
        try:
            r("ir.ui.view", "unlink", [v["id"]])
            print(f"  unlink vista #{v['id']} {v.get('name')}")
        except Exception as e:
            print(f"  no se pudo unlink vista #{v.get('id')}: {e}")
    # Campos custom: no los borramos automáticamente (pueden tener datos);
    # si no existían antes, se listan para borrado manual.
    pre_ids = {f["id"] for f in bk.get("fields") or []}
    for f in created.get("fields") or []:
        if f["id"] in pre_ids:
            continue
        print(f"  AVISO: campo creado {f['model']}.{f['name']} id={f['id']} — no se borra solo; unlink manual si corresponde.")
    # Vistas ARME por nombre (por si created_on_apply falta)
    for v in views_io(r):
        if v["id"] not in {x["id"] for x in (created.get("views") or [])}:
            # only remove if we created them in this apply; if backup has empty created, leave
            pass
    print("revertido (código SA). Revisar campos/vistas residuales arriba.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--confirmo-produccion", action="store_true")
    ap.add_argument("--forzar", action="store_true")
    ap.add_argument("--diff", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("revisar")
    sub.add_parser("backup")
    p_ap = sub.add_parser("aplicar")
    p_ap.add_argument("--confirmo-produccion", action="store_true")
    p_ap.add_argument("--forzar", action="store_true")
    p_rev = sub.add_parser("revertir")
    p_rev.add_argument("backup")
    p_rev.add_argument("--confirmo-produccion", action="store_true")
    args = ap.parse_args()
    r = conectar()
    if args.cmd == "revisar":
        cmd_revisar(r, diff=args.diff)
    elif args.cmd == "backup":
        cmd_backup(r)
    elif args.cmd == "aplicar":
        cmd_aplicar(r, args)
    elif args.cmd == "revertir":
        cmd_revertir(r, args)


if __name__ == "__main__":
    main()
