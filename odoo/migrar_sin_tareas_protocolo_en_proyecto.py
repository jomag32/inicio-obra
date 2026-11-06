#!/usr/bin/env python3
"""Parche SA 2638 «Inicio de obra · crear tareas por área»: deja de crear project.task
«Inicio de obra · {área}» en el tablero del proyecto. Sigue creando x_inicio_obra,
x_inicio_obra_tarea e x_inicio_obra_item (app / menú Inicio de obra).

NO aplica a producción salvo --aplicar --confirmo-produccion.

Uso:
  python3 migrar_sin_tareas_protocolo_en_proyecto.py revisar
  python3 migrar_sin_tareas_protocolo_en_proyecto.py backup
  python3 migrar_sin_tareas_protocolo_en_proyecto.py aplicar --confirmo-produccion
  python3 migrar_sin_tareas_protocolo_en_proyecto.py revertir backup-sin-tareas-….json --confirmo-produccion

Credenciales: ODOO_URL, ODOO_DB, ODOO_API_KEY (o ODOO_API_KEY_ADMIN_ARME), ODOO_UID (default 2).
Nunca imprime secretos.
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time, difflib, xmlrpc.client
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plan_inicio_obra as plan

SA_NAME = "Inicio de obra · crear tareas por área"
SA_ID_ESPERADO = 2638
AUTO_NAME = "Inicio de obra · al crear OT"
# Huella del CODE_CREAR vivo verificado 2026-11-06 (América/Córdoba) antes de este parche.
ESPERADO_VIVO = "998f7d24ea7ad34b624e0f6996880c0401516a090bfdc7717ff9d3b0b5caf895"
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


def leer_sa(r):
    rows = r("ir.actions.server", "search_read", [["name", "=", SA_NAME]], fields=["id", "name", "code", "model_id", "state"])
    if len(rows) != 1:
        sys.exit(f"Se esperaba 1 SA «{SA_NAME}», hay {len(rows)}")
    sa = rows[0]
    if sa["id"] != SA_ID_ESPERADO:
        print(f"AVISO: id vivo {sa['id']} ≠ {SA_ID_ESPERADO} (se sigue por nombre).")
    auto = r("base.automation", "search_read", [["name", "=", AUTO_NAME]], fields=["id", "name", "trigger", "action_server_ids"])
    return sa, auto


def cmd_revisar(r, diff=False):
    sa, auto = leer_sa(r)
    vivo = sa["code"] or ""
    nuevo = plan.CODE_CREAR
    hv, hn = huella(vivo), huella(nuevo)
    n_tasks = r("project.task", "search_count", [["name", "ilike", "Inicio de obra ·"]])
    n_ini = r("x_inicio_obra", "search_count", [])
    print("== revisar · sin tareas de protocolo en el proyecto ==")
    print(f"  SA #{sa['id']} «{sa['name']}»  state={sa.get('state')}")
    print(f"  automatización: {[(a['id'], a['name'], a.get('action_server_ids')) for a in auto]}")
    print(f"  huella vivo : {hv}")
    print(f"  huella esp. : {ESPERADO_VIVO}  ({'OK' if hv == ESPERADO_VIVO else 'DISTINTO — alguien cambió el código'})")
    print(f"  huella nuevo: {hn}")
    crea = "env['project.task'].create"
    print(f"  vivo crea project.task.create? {'sí' if crea in vivo else 'no'}")
    print(f"  nuevo crea project.task.create? {'sí' if crea in nuevo else 'no'}")
    print(f"  project.task «Inicio de obra · …» existentes: {n_tasks}")
    print(f"  x_inicio_obra existentes: {n_ini}")
    if hv == hn:
        print("  Código vivo ya es el nuevo: nada que aplicar.")
    elif diff:
        sys.stdout.writelines(difflib.unified_diff(
            vivo.splitlines(True), nuevo.splitlines(True),
            fromfile=f"vivo-{sa['id']}", tofile="plan.CODE_CREAR"))
    return sa, vivo, nuevo


def cmd_backup(r):
    sa, auto = leer_sa(r)
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(HERE, f"backup-sin-tareas-protocolo-{ts}.json")
    bk = {
        "ts": ts,
        "sa": {"id": sa["id"], "name": sa["name"], "code": sa["code"], "huella": huella(sa["code"])},
        "auto": auto,
        "nota": "Backup de CODE_CREAR (SA crear tareas por área) antes de dejar de crear project.task de protocolo.",
    }
    json.dump(bk, open(path, "w"), ensure_ascii=False, indent=1)
    print("backup:", path)
    print("huella:", bk["sa"]["huella"])
    return path


def exigir_confirmacion(args):
    if not getattr(args, "confirmo_produccion", False):
        sys.exit("Abortado: falta --confirmo-produccion (no se escribe en producción).")


def cmd_aplicar(r, args):
    exigir_confirmacion(args)
    sa, vivo, nuevo = cmd_revisar(r, diff=False)
    if huella(vivo) == huella(nuevo):
        print("Nada que aplicar.")
        return
    if huella(vivo) != ESPERADO_VIVO and not args.forzar:
        sys.exit("El código vivo no coincide con la huella verificada. Revisar a mano o pasar --forzar.")
    if "env['project.task'].create" in nuevo:
        sys.exit("El CODE_CREAR del plan todavía crea project.task; abortado.")
    path = cmd_backup(r)
    r("ir.actions.server", "write", [sa["id"]], {"code": nuevo})
    # re-leer
    sa2, _ = leer_sa(r)
    print(f"aplicado SA #{sa2['id']}: huella ahora {huella(sa2['code'])}")
    print(f"rollback: python3 {os.path.basename(__file__)} revertir {os.path.basename(path)} --confirmo-produccion")


def cmd_revertir(r, args):
    exigir_confirmacion(args)
    bk = json.load(open(args.backup if args.backup.endswith(".json") else args.backup))
    if isinstance(args.backup, str) and not args.backup.endswith(".json"):
        pass
    sid = bk["sa"]["id"]
    code = bk["sa"]["code"]
    r("ir.actions.server", "write", [sid], {"code": code})
    print(f"restaurada SA #{sid}, huella {huella(code)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--confirmo-produccion", action="store_true", help="Obligatorio para aplicar/revertir en prod")
    ap.add_argument("--forzar", action="store_true", help="Aplicar aunque la huella viva no coincida")
    ap.add_argument("--diff", action="store_true", help="En revisar, mostrar diff unificado")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("revisar")
    sub.add_parser("backup")
    p_ap = sub.add_parser("aplicar")
    p_ap.add_argument("--confirmo-produccion", action="store_true", help="Obligatorio para escribir en prod")
    p_ap.add_argument("--forzar", action="store_true")
    p_rev = sub.add_parser("revertir")
    p_rev.add_argument("backup", help="Ruta al JSON de backup")
    p_rev.add_argument("--confirmo-produccion", action="store_true", help="Obligatorio para escribir en prod")
    args = ap.parse_args()
    r = conectar()
    if args.cmd == "revisar":
        cmd_revisar(r, diff=args.diff)
    elif args.cmd == "backup":
        cmd_backup(r)
    elif args.cmd == "aplicar":
        cmd_aplicar(r, args)
    elif args.cmd == "revertir":
        # argparse put backup on subparser; merge
        if not hasattr(args, "backup"):
            sys.exit("Falta ruta de backup")
        cmd_revertir(r, args)


if __name__ == "__main__":
    main()
