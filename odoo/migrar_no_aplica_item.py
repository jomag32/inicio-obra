#!/usr/bin/env python3
"""Migración ADITIVA: «No aplica» por ítem en x_inicio_obra_item (Tecnología ARME · Inicio de obra).
Uso:  (sin flags) DRY-RUN, solo lee  |  --apply  |  --rollback backup-na-item-<ts>.json [--borrar-campos]
Credenciales por entorno: ODOO_URL, ODOO_DB, ODOO_API_KEY (+ ODOO_UID, default 2). Nunca se imprimen.
Qué hace --apply (todo con backup previo en JSON):
  1) crea 4 campos nuevos en x_inicio_obra_item (no toca ni borra datos existentes; todos los ítems quedan con «No aplica» = falso):
     x_no_aplica, x_no_aplica_motivo, x_no_aplica_user_id, x_no_aplica_at
  2) reemplaza el código de las acciones «sellar ítem y recalcular» y «Devolver como Observado (CEO)» por la versión de plan_inicio_obra.py
  3) agrega x_no_aplica a los campos disparadores de la automatización «ítem marcado».
--rollback restaura el código y los disparadores guardados. Los campos quedan (son inocuos) salvo --borrar-campos."""
import os, sys, json, time, argparse, xmlrpc.client
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import plan_inicio_obra as plan
M = "x_inicio_obra_item"
ACC = {"item": "Inicio de obra · sellar ítem y recalcular", "observar": "Devolver como Observado (CEO)"}
AUTO = "Inicio de obra · ítem marcado"

def conectar():
    url = os.environ.get("ODOO_URL", "").rstrip("/"); db = os.environ.get("ODOO_DB", ""); key = os.environ.get("ODOO_API_KEY", "").strip(); uid = int(os.environ.get("ODOO_UID", "2"))
    if not (url and db and key): sys.exit("Faltan ODOO_URL, ODOO_DB u ODOO_API_KEY")
    m = xmlrpc.client.ServerProxy(url + "/xmlrpc/2/object", allow_none=True)
    return lambda model, method, *a, **k: m.execute_kw(db, uid, key, model, method, list(a), k)

def hdr(code):  # conserva la cabecera viva (COO_UID / GROUP_CEO) de la acción actual
    return "".join(l + "\n" for l in code.splitlines()[:2] if l.startswith(("COO_UID", "GROUP_CEO")))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true"); ap.add_argument("--rollback"); ap.add_argument("--borrar-campos", action="store_true"); a = ap.parse_args()
    r = conectar()
    if a.rollback:
        bk = json.load(open(a.rollback))
        for x in bk["acciones"]: r("ir.actions.server", "write", [x["id"]], {"code": x["code"]}); print("  restaurada acción", x["id"])
        if bk.get("auto"): r("base.automation", "write", [bk["auto"]["id"]], {"trigger_field_ids": [(6, 0, bk["auto"]["trigger_field_ids"])]}); print("  restaurada automatización", bk["auto"]["id"])
        if a.borrar_campos and bk["campos_creados"]: r("ir.model.fields", "unlink", bk["campos_creados"]); print("  campos borrados", bk["campos_creados"])
        return
    print(f"== «No aplica» por ítem · {'APPLY' if a.apply else 'DRY-RUN (no escribe nada)'} ==")
    mid = r("ir.model", "search", [["model", "=", M]]); assert mid, "No existe " + M
    exist = {f["name"] for f in r("ir.model.fields", "search_read", [["model", "=", M], ["name", "in", [f[0] for f in plan.NA_ITEM_FIELDS]]], fields=["name"])}
    acc = {k: r("ir.actions.server", "search_read", [["name", "=", v]], fields=["code"]) for k, v in ACC.items()}
    for k, v in acc.items(): assert len(v) == 1, f"Acción «{ACC[k]}»: se esperaba 1, hay {len(v)}"
    auto = r("base.automation", "search_read", [["name", "=", AUTO]], fields=["trigger_field_ids"]); assert len(auto) == 1, "Automatización no encontrada"
    ts = time.strftime("%Y%m%d-%H%M%S"); bkf = os.path.join(HERE, f"backup-na-item-{ts}.json")
    bk = {"ts": ts, "campos_creados": [], "acciones": [{"id": v[0]["id"], "code": v[0]["code"]} for v in acc.values()], "auto": auto[0]}
    nuevo = {"item": plan.CODE_ITEM, "observar": plan.CODE_OBSERVAR}
    if a.apply: json.dump(bk, open(bkf, "w"), ensure_ascii=False, indent=1); print("  backup:", bkf)
    for fn, ft, fl, extra in plan.NA_ITEM_FIELDS:
        if fn in exist: print("  = ya existe", fn); continue
        print(f"  + campo {M}.{fn} [{ft}]")
        if a.apply:
            bk["campos_creados"].append(r("ir.model.fields", "create", {"model_id": mid[0], "name": fn, "ttype": ft, "field_description": fl, "state": "manual", **extra}))
            json.dump(bk, open(bkf, "w"), ensure_ascii=False, indent=1)
    for k, v in acc.items():
        code = hdr(v[0]["code"]) + nuevo[k]
        print(f"  ~ acción «{ACC[k]}» #{v[0]['id']}: {'sin cambios' if code == v[0]['code'] else 'se reemplaza el código'}")
        if a.apply and code != v[0]["code"]: r("ir.actions.server", "write", [v[0]["id"]], {"code": code})
    trig = r("ir.model.fields", "search", [["model", "=", M], ["name", "in", ["x_hecho", "x_no_aplica"]]]) if a.apply else []
    print(f"  ~ automatización «{AUTO}» #{auto[0]['id']}: disparadores x_hecho + x_no_aplica")
    if a.apply: r("base.automation", "write", [auto[0]["id"]], {"trigger_field_ids": [(6, 0, sorted(set(auto[0]["trigger_field_ids"]) | set(trig)))]})
    print("Listo." if a.apply else "Dry-run: nada escrito. Repetir con --apply.")

if __name__ == "__main__": main()
