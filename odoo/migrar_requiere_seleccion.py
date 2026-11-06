#!/usr/bin/env python3
"""Wizard: boolean → selection obligatoria Requiere / No requiere (empieza vacío).

- x_crear_proyecto_desde.x_io_requiere_protocolo: selection required, sin default
- project.project.x_io_requiere_protocolo: sigue boolean (True si 'requiere')
- Vista wizard #8585: required=1
- SA 2420: mapea selection → boolean en vals del copy

NO escribe en prod sin --aplicar --confirmo-produccion.
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time, xmlrpc.client
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
SA_WIZ_ID = 2420
SA_WIZ_NAME = "Crear proyecto"
WIZ_MODEL = "x_crear_proyecto_desde"
PROJ_MODEL = "project.project"
FIELD = "x_io_requiere_protocolo"
VIEW_WIZ_ID = 8585
FIELD_WIZ_BOOL_ID = 44876  # actual boolean a reemplazar
ESPERADO_SA2420 = "50e46131bf0a654993782a5ecdcd1e21661308dd3a845baf42674e9b8d98f4dc"
SELECTION = "[('requiere', 'Requiere'), ('no_requiere', 'No requiere')]"
LABEL = "Protocolo de inicio de obra"
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


def exigir(args):
    if not getattr(args, "confirmo_produccion", False):
        sys.exit("Abortado: falta --confirmo-produccion")


def mid(r, model):
    return r("ir.model", "search_read", [["model", "=", model]], fields=["id"])[0]["id"]


def leer_campo_wiz(r):
    rows = r("ir.model.fields", "search_read",
             [["model", "=", WIZ_MODEL], ["name", "=", FIELD]],
             fields=["id", "name", "ttype", "selection", "required", "field_description", "selection_ids"])
    return rows[0] if rows else None


def leer_sa(r):
    rows = r("ir.actions.server", "read", [SA_WIZ_ID], ["id", "name", "code"])
    if not rows or rows[0]["name"] != SA_WIZ_NAME:
        sys.exit("SA 2420 inesperada")
    return rows[0]


def codigo_nuevo():
    p = Path(HERE) / "SA2420_con_requiere_seleccion.py.txt"
    if not p.exists():
        sys.exit(f"Falta {p}")
    return p.read_text()


def arch_nuevo():
    return f'''<?xml version="1.0"?>
<data>
  <xpath expr="//field[@name='x_studio_plantilla_de_proyecto']" position="after">
    <field name="{FIELD}" string="{LABEL}" required="1"
           help="Obligatorio: elegí Requiere o No requiere antes de crear el proyecto."/>
  </xpath>
</data>'''


def cmd_revisar(r):
    sa = leer_sa(r)
    fld = leer_campo_wiz(r)
    view = r("ir.ui.view", "read", [VIEW_WIZ_ID], ["id", "name", "arch_db", "active"])[0]
    nuevo = codigo_nuevo()
    print("== revisar · selection requerida ==")
    print(f"  SA #{sa['id']} huella vivo={huella(sa['code'])}")
    print(f"             esperado pre={ESPERADO_SA2420} ({'OK' if huella(sa['code'])==ESPERADO_SA2420 else 'DISTINTO'})")
    print(f"             huella nuevo={huella(nuevo)}")
    print(f"  campo wizard: {fld}")
    print(f"  vista #{view['id']} active={view.get('active')}")
    print(f"  arch has required=1? {'required=\"1\"' in (view.get('arch_db') or '')}")
    print("  SA has eleccion map?", ("(eleccion == 'requiere')" in (sa["code"] or "")))
    print(f"  SA nuevo has UserError vacío? {'Debe indicar si la obra requiere' in nuevo}")
    return sa, fld, view, nuevo


def cmd_backup(r):
    sa, fld, view, _ = cmd_revisar(r)
    proj = r("ir.model.fields", "search_read",
             [["model", "=", PROJ_MODEL], ["name", "=", FIELD]],
             fields=["id", "name", "ttype", "field_description", "required"])
    sels = []
    if fld and fld.get("selection_ids"):
        sels = r("ir.model.fields.selection", "read", fld["selection_ids"],
                 ["id", "value", "name", "sequence", "field_id"])
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(HERE, f"backup-requiere-seleccion-{ts}.json")
    bk = {
        "ts": ts,
        "nota": "Backup pre-apply: selection requerida Requiere/No requiere en wizard",
        "sa2420": {"id": sa["id"], "name": sa["name"], "code": sa["code"], "huella": huella(sa["code"])},
        "field_wiz": fld,
        "field_wiz_selections": sels,
        "field_proj": proj,
        "view_8585": {"id": view["id"], "name": view["name"], "arch_db": view["arch_db"]},
    }
    json.dump(bk, open(path, "w"), ensure_ascii=False, indent=1)
    print("backup:", path)
    return path


def cmd_aplicar(r, args):
    exigir(args)
    sa, fld, view, nuevo = cmd_revisar(r)
    if "(eleccion == 'requiere')" not in nuevo:
        sys.exit("Artefacto SA2420 incompleto")
    if huella(sa["code"]) != ESPERADO_SA2420 and "(eleccion == 'requiere')" not in (sa["code"] or "") and not args.forzar:
        sys.exit("SA 2420 vivo ≠ huella esperada (boolean patch). Usá --forzar si corresponde.")
    if fld and fld["ttype"] == "selection" and fld.get("required") and "(eleccion == 'requiere')" in (sa["code"] or ""):
        print("Ya aplicado (selection + SA). Nada que hacer.")
        return

    path = cmd_backup(r)
    created = {"field_wiz_id": None, "unlinked_field_id": None}

    # 1) Quitar campo de la vista para poder unlink del boolean
    print("-- vista: quitar campo temporalmente --")
    r("ir.ui.view", "write", [VIEW_WIZ_ID], {"arch_db": "<data/>"})

    # 2) Reemplazar boolean por selection (mismo nombre técnico)
    if fld:
        if fld["ttype"] == "boolean":
            print(f"-- unlink boolean wizard #{fld['id']} --")
            r("ir.model.fields", "unlink", [fld["id"]])
            created["unlinked_field_id"] = fld["id"]
        elif fld["ttype"] == "selection":
            print(f"-- campo ya selection #{fld['id']}, se actualiza required/selection --")
            r("ir.model.fields", "write", [fld["id"]], {
                "field_description": LABEL,
                "required": True,
                "selection": SELECTION,
            })
            created["field_wiz_id"] = fld["id"]

    if not created["field_wiz_id"]:
        # recreate after unlink or if missing
        still = leer_campo_wiz(r)
        if still:
            created["field_wiz_id"] = still["id"]
            r("ir.model.fields", "write", [still["id"]], {
                "field_description": LABEL,
                "required": True,
                "selection": SELECTION if still["ttype"] == "selection" else still.get("selection"),
            })
        else:
            print("-- create selection field --")
            fid = r("ir.model.fields", "create", {
                "name": FIELD,
                "model_id": mid(r, WIZ_MODEL),
                "field_description": LABEL,
                "ttype": "selection",
                "selection": SELECTION,
                "required": True,
                "state": "manual",
                "copied": False,
            })
            created["field_wiz_id"] = fid
            print(f"  creado #{fid}")

    # Ensure selection lines exist / match
    fld2 = leer_campo_wiz(r)
    print("  campo post:", fld2)
    if fld2["ttype"] != "selection":
        sys.exit("El campo wizard no quedó como selection")

    # 3) Vista definitiva
    print("-- vista wizard required --")
    r("ir.ui.view", "write", [VIEW_WIZ_ID], {"arch_db": arch_nuevo()})

    # 4) SA 2420
    print("-- SA 2420 --")
    r("ir.actions.server", "write", [sa["id"]], {"code": nuevo})
    sa2 = leer_sa(r)
    print(f"  huella ahora {huella(sa2['code'])}")

    bk = json.load(open(path))
    bk["created_on_apply"] = created
    bk["field_wiz_after"] = leer_campo_wiz(r)
    bk["view_after"] = r("ir.ui.view", "read", [VIEW_WIZ_ID], ["id", "arch_db"])[0]
    json.dump(bk, open(path, "w"), ensure_ascii=False, indent=1)
    print("aplicado.")
    print(f"rollback: python3 {os.path.basename(__file__)} revertir {os.path.basename(path)} --confirmo-produccion")


def cmd_revertir(r, args):
    exigir(args)
    path = args.backup
    if not os.path.isabs(path):
        cand = os.path.join(HERE, path)
        if os.path.exists(cand):
            path = cand
    bk = json.load(open(path))
    print("-- restaurar SA 2420 --")
    r("ir.actions.server", "write", [bk["sa2420"]["id"]], {"code": bk["sa2420"]["code"]})
    print("  huella", huella(bk["sa2420"]["code"]))

    # Vista primero sin el selection field si vamos a recrear boolean
    print("-- vista backup arch --")
    r("ir.ui.view", "write", [bk["view_8585"]["id"]], {"arch_db": bk["view_8585"]["arch_db"]})

    cur = leer_campo_wiz(r)
    old = bk.get("field_wiz")
    if cur and cur["ttype"] == "selection" and old and old["ttype"] == "boolean":
        print(f"-- unlink selection #{cur['id']} y recrear boolean --")
        # clear view first to avoid dangling ref if arch still points - arch already restored expects boolean
        r("ir.ui.view", "write", [VIEW_WIZ_ID], {"arch_db": "<data/>"})
        r("ir.model.fields", "unlink", [cur["id"]])
        fid = r("ir.model.fields", "create", {
            "name": FIELD,
            "model_id": mid(r, WIZ_MODEL),
            "field_description": old.get("field_description") or "Requiere protocolo de inicio de obra",
            "ttype": "boolean",
            "required": False,
            "state": "manual",
            "copied": True,
        })
        print(f"  boolean recreado #{fid}")
        r("ir.ui.view", "write", [bk["view_8585"]["id"]], {"arch_db": bk["view_8585"]["arch_db"]})
    print("revertido (aprox.). Revisar campo/vista.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--confirmo-produccion", action="store_true")
    ap.add_argument("--forzar", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("revisar")
    sub.add_parser("backup")
    p = sub.add_parser("aplicar")
    p.add_argument("--confirmo-produccion", action="store_true")
    p.add_argument("--forzar", action="store_true")
    pr = sub.add_parser("revertir")
    pr.add_argument("backup")
    pr.add_argument("--confirmo-produccion", action="store_true")
    args = ap.parse_args()
    r = conectar()
    if args.cmd == "revisar":
        cmd_revisar(r)
    elif args.cmd == "backup":
        cmd_backup(r)
    elif args.cmd == "aplicar":
        cmd_aplicar(r, args)
    elif args.cmd == "revertir":
        cmd_revertir(r, args)


if __name__ == "__main__":
    main()
