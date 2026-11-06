#!/usr/bin/env python3
"""Limpieza OPCIONAL (NO ejecutar hasta que Jorge lo pida): borra project.task
«Inicio de obra · …» ya creadas en OTs y limpia x_task_id en x_inicio_obra_tarea / x_inicio_obra_item.

No toca x_inicio_obra ni los checklists. El protocolo en la app sigue igual.

Uso (solo dry-run por defecto):
  python3 limpiar_tareas_protocolo_existentes.py revisar
  python3 limpiar_tareas_protocolo_existentes.py backup
  python3 limpiar_tareas_protocolo_existentes.py aplicar --confirmo-produccion

Credenciales: iguales que migrar_sin_tareas_protocolo_en_proyecto.py. Nunca imprime secretos.
"""
from __future__ import annotations
import argparse, json, os, sys, time, xmlrpc.client

HERE = os.path.dirname(os.path.abspath(__file__))
DOMAIN = [["name", "ilike", "Inicio de obra ·"]]


def conectar():
    url = os.environ.get("ODOO_URL", "https://cooperativa-de-trabajo-el-sol.odoo.com").rstrip("/")
    db = os.environ.get("ODOO_DB", "cooperativa-de-trabajo-el-sol")
    key = (os.environ.get("ODOO_API_KEY") or os.environ.get("ODOO_API_KEY_ADMIN_ARME", "")).strip()
    uid = int(os.environ.get("ODOO_UID", "2"))
    if not key:
        sys.exit("Falta ODOO_API_KEY / ODOO_API_KEY_ADMIN_ARME")
    m = xmlrpc.client.ServerProxy(url + "/xmlrpc/2/object", allow_none=True)
    return lambda model, method, *a, **k: m.execute_kw(db, uid, key, model, method, list(a), k)


def listar(r):
    ids = r("project.task", "search", DOMAIN)
    rows = []
    for i in range(0, len(ids), 80):
        rows += r("project.task", "read", ids[i:i+80], ["id", "name", "project_id", "create_date", "x_io_inicio_id", "x_io_area_id"])
    return rows


def cmd_revisar(r):
    rows = listar(r)
    prjs = {}
    for row in rows:
        pid = row["project_id"][0] if row["project_id"] else None
        prjs.setdefault(pid, []).append(row["id"])
    print("== limpiar tareas de protocolo existentes (DRY info) ==")
    print(f"  project.task a borrar: {len(rows)} en {len(prjs)} proyectos")
    for pid, tids in sorted(prjs.items(), key=lambda x: -(len(x[1]))):
        nombre = next((t["project_id"][1] for t in rows if t["project_id"] and t["project_id"][0] == pid), "?")
        print(f"    proyecto {pid} {nombre}: {len(tids)} tareas")
    # links
    ta = r("x_inicio_obra_tarea", "search_count", [["x_task_id", "!=", False]])
    it = r("x_inicio_obra_item", "search_count", [["x_task_id", "!=", False]])
    print(f"  x_inicio_obra_tarea con x_task_id: {ta}")
    print(f"  x_inicio_obra_item con x_task_id: {it}")
    print("  (aplicar: unlink de esas project.task + write x_task_id=False en tarea/ítem)")
    return rows


def cmd_backup(r):
    rows = listar(r)
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(HERE, f"backup-limpiar-tareas-protocolo-{ts}.json")
    ta_ids = r("x_inicio_obra_tarea", "search", [["x_task_id", "!=", False]])
    it_ids = r("x_inicio_obra_item", "search", [["x_task_id", "!=", False]])
    ta = r("x_inicio_obra_tarea", "read", ta_ids, ["id", "x_task_id", "x_inicio_id", "x_name"]) if ta_ids else []
    it = r("x_inicio_obra_item", "read", it_ids, ["id", "x_task_id", "x_inicio_id", "x_name"]) if it_ids else []
    bk = {"ts": ts, "tasks": rows, "tareas_x_task": ta, "items_x_task": it}
    json.dump(bk, open(path, "w"), ensure_ascii=False, indent=1)
    print("backup:", path)
    return path


def cmd_aplicar(r, args):
    if not args.confirmo_produccion:
        sys.exit("Abortado: falta --confirmo-produccion")
    path = cmd_backup(r)
    rows = listar(r)
    ids = [t["id"] for t in rows]
    # limpiar links primero
    ta_ids = r("x_inicio_obra_tarea", "search", [["x_task_id", "in", ids]]) if ids else []
    it_ids = r("x_inicio_obra_item", "search", [["x_task_id", "in", ids]]) if ids else []
    if ta_ids:
        r("x_inicio_obra_tarea", "write", ta_ids, {"x_task_id": False})
        print(f"  limpiados x_task_id en {len(ta_ids)} x_inicio_obra_tarea")
    if it_ids:
        r("x_inicio_obra_item", "write", it_ids, {"x_task_id": False})
        print(f"  limpiados x_task_id en {len(it_ids)} x_inicio_obra_item")
    if ids:
        r("project.task", "unlink", ids)
        print(f"  borradas {len(ids)} project.task de protocolo")
    print("backup en", path)
    print("Listo. Los checklists x_inicio_obra_* siguen intactos.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--confirmo-produccion", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("revisar")
    sub.add_parser("backup")
    sub.add_parser("aplicar")
    args = ap.parse_args()
    r = conectar()
    if args.cmd == "revisar":
        cmd_revisar(r)
    elif args.cmd == "backup":
        cmd_backup(r)
    elif args.cmd == "aplicar":
        cmd_aplicar(r, args)


if __name__ == "__main__":
    main()
