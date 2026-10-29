#!/usr/bin/env python3
"""Plan de cambios Odoo 19 para 'Inicio de obra' asíncrono (Tecnología ARME).
Uso:  --dry-run (default, solo lee)  |  --apply  |  --rollback <backup.json>
Credenciales por entorno: ODOO_URL, ODOO_DB, ODOO_API_KEY (+ ODOO_UID, default 2). Nunca se imprimen.
Gerentes: managers.local.json (NO va al repo): código de área -> res.users id."""
import os, sys, json, time, argparse, xmlrpc.client
HERE = os.path.dirname(os.path.abspath(__file__))
CHK = json.load(open(os.path.join(HERE, "datos", "checklist.json")))
P = "x_inicio_obra"

# ---------- modelos y campos ----------
ROLES = "[('gerente','Gerente de área'),('secretaria','Secretaría COO'),('ugeop','UGEOP'),('coo','COO'),('ceo','CEO')]"
MODELS = [
 (f"{P}_usuario", "Inicio de obra · Usuario de la app", True, [
   ("x_login","char","Usuario (login app)",{}), ("x_email","char","Email",{}), ("x_rol","selection","Rol",{"selection":ROLES,"tracking":1}),
   ("x_active","boolean","Activo",{"tracking":1}), ("x_user_id","many2one","Usuario Odoo (opcional)",{"relation":"res.users"}),
   ("x_clave_configurada","boolean","Clave configurada (en backend)",{"readonly":True})]),
 (f"{P}_area", "Inicio de obra · Área", False, [
   ("x_code","char","Código",{}), ("x_sequence","integer","Orden",{}), ("x_user_id","many2one","Usuario Odoo del gerente (opcional)",{"relation":"res.users"}),
   ("x_plazo_horas","integer","Plazo (horas desde la OT)",{}), ("x_active","boolean","Activa",{})]),
 (f"{P}_plantilla", "Inicio de obra · Ítem plantilla", False, [
   ("x_area_id","many2one","Área",{"relation":f"{P}_area","on_delete":"cascade"}), ("x_sequence","integer","Orden",{}),
   ("x_requiere_adjunto","boolean","Requiere adjunto",{})]),
 (P, "Inicio de obra", True, [
   ("x_project_id","many2one","OT",{"relation":"project.project","on_delete":"cascade"}),
   ("x_state","selection","Estado",{"selection":"[('carga','En carga'),('completo','Completo · espera CEO'),('aprobado','Aprobado por CEO'),('observado','Observado')]","tracking":1}),
   ("x_items_total","integer","Ítems",{}), ("x_items_ok","integer","Ítems cumplidos",{}), ("x_avance","float","Avance %",{}),
   ("x_completo_at","datetime","Completo el",{}),
   ("x_ceo_user_id","many2one","Aprobado por",{"relation":"res.users","tracking":1}), ("x_ceo_at","datetime","Aprobado el",{"tracking":1}),
   ("x_ceo_obs","text","Observaciones del CEO",{}), ("x_ronda","integer","Ronda",{"tracking":1})]),
 (f"{P}_ronda", "Inicio de obra · Ronda de revisión CEO", False, [
   ("x_inicio_id","many2one","Inicio de obra",{"relation":P,"on_delete":"cascade"}), ("x_numero","integer","Ronda N°",{}),
   ("x_resultado","selection","Resultado",{"selection":"[('aprobado','Aprobado'),('observado','Devuelto como observado')]"}),
   ("x_obs","text","Observación",{}), ("x_usuario_id","many2one","CEO (usuario app)",{"relation":f"{P}_usuario"}),
   ("x_at","datetime","Fecha y hora",{}), ("x_avance","float","Avance al momento",{})]),
 (f"{P}_tarea", "Inicio de obra · Área por obra", True, [
   ("x_inicio_id","many2one","Inicio de obra",{"relation":P,"on_delete":"cascade"}), ("x_area_id","many2one","Área",{"relation":f"{P}_area"}),
   ("x_task_id","many2one","Tarea Odoo",{"relation":"project.task"}), ("x_vence","datetime","Vence (hs lun-sáb)",{}),
   ("x_no_aplica","boolean","No aplica a esta obra",{"tracking":1}), ("x_no_aplica_motivo","text","Motivo no aplica",{"tracking":1}),
   ("x_no_aplica_usuario_id","many2one","No aplica: marcado por",{"relation":f"{P}_usuario","tracking":1}), ("x_no_aplica_at","datetime","No aplica: fecha",{"tracking":1}),
   ("x_completa","boolean","Completa",{"tracking":1}), ("x_observada","boolean","Observada por CEO",{"tracking":1}), ("x_obs_ceo","text","Observación CEO vigente",{})]),
 (f"{P}_item", "Inicio de obra · Ítem", True, [
   ("x_inicio_id","many2one","Inicio de obra",{"relation":P,"on_delete":"cascade"}),
   ("x_task_id","many2one","Tarea del área",{"relation":"project.task"}),
   ("x_area_id","many2one","Área",{"relation":f"{P}_area"}), ("x_sequence","integer","Orden",{}),
   ("x_requiere_adjunto","boolean","Requiere adjunto",{}),
   ("x_hecho","boolean","Cumplido",{"tracking":1}), ("x_hecho_user_id","many2one","Marcado por",{"relation":"res.users","tracking":1}),
   ("x_hecho_at","datetime","Marcado el",{"tracking":1}),
   ("x_hecho_usuario_id","many2one","Marcado por (usuario app)",{"relation":f"{P}_usuario","tracking":1}),
   ("x_tarea_id","many2one","Área por obra",{"relation":f"{P}_tarea","on_delete":"cascade"}), ("x_observado","boolean","Observado por CEO",{"tracking":1}), ("x_vence","datetime","Vence",{}),
   ("x_fuera_termino","boolean","Fuera de término",{"tracking":1}), ("x_obs","text","Observación",{})]),
]
TASK_FIELDS = [("x_io_inicio_id","many2one","Inicio de obra",{"relation":P}), ("x_io_area_id","many2one","Área inicio de obra",{"relation":f"{P}_area"})]
PROJECT_FIELDS = [("x_io_inicio_id","many2one","Inicio de obra",{"relation":P})]
M2M = [(f"{P}_usuario","x_area_ids","Áreas",f"{P}_area","x_io_usuario_area_rel","x_usuario_id","x_area_id"),
       (f"{P}_ronda","x_tarea_ids","Áreas devueltas",f"{P}_tarea","x_io_ronda_tarea_rel","x_ronda_id","x_tarea_id"),
       (f"{P}_ronda","x_item_ids","Ítems devueltos",f"{P}_item","x_io_ronda_item_rel","x_ronda_id","x_item_id")]
ONE2MANY = [(P,"x_tarea_ids","Áreas",f"{P}_tarea","x_inicio_id"), (P,"x_ronda_ids","Rondas CEO",f"{P}_ronda","x_inicio_id"),(P,"x_item_ids","Ítems",f"{P}_item","x_inicio_id"), (f"{P}_area","x_plantilla_ids","Ítems plantilla",f"{P}_plantilla","x_area_id")]
GROUP_CEO = "Inicio de obra · Aprobador (CEO)"; GROUP_VER = "Inicio de obra · Consolidado (COO/Secretaría/UGEOP)"

# ---------- server actions (safe_eval) ----------
CODE_CREAR = r'''
# Al crear OT: 1 tarea por área asignada al gerente + ítems. Se corre una sola vez por OT.
for prj in records:
    if prj.x_io_inicio_id: continue
    ini = env['x_inicio_obra'].create({'x_name': 'Inicio de obra · ' + prj.name, 'x_project_id': prj.id, 'x_state': 'carga'})
    prj.write({'x_io_inicio_id': ini.id})
    base = prj.create_date or datetime.datetime.now()
    def vence_lun_sab(d, horas):
        # suma horas corridas salteando domingos completos (weekday 6)
        while horas > 0:
            if d.weekday() == 6:
                d = (d + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0); continue
            fin_dia = (d + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0)
            h = min(horas, (fin_dia - d).total_seconds() / 3600.0); d = d + datetime.timedelta(hours=h); horas -= h
        return d
    for a in env['x_inicio_obra_area'].search([('x_active','=',True)], order='x_sequence'):
        vence = vence_lun_sab(base, a.x_plazo_horas or 48)
        gerentes = env['x_inicio_obra_usuario'].search([('x_area_ids','in',a.id),('x_active','=',True)])
        t = env['project.task'].create({'name': 'Inicio de obra · ' + a.x_name, 'project_id': prj.id,
             'user_ids': [(6,0,gerentes.mapped('x_user_id').ids)], 'date_deadline': vence,
             'x_io_inicio_id': ini.id, 'x_io_area_id': a.id})
        ta = env['x_inicio_obra_tarea'].create({'x_name': a.x_name, 'x_inicio_id': ini.id, 'x_area_id': a.id, 'x_task_id': t.id, 'x_vence': vence})
        for p in a.x_plantilla_ids.sorted('x_sequence'):
            env['x_inicio_obra_item'].create({'x_name': p.x_name, 'x_inicio_id': ini.id, 'x_task_id': t.id, 'x_area_id': a.id,
                 'x_tarea_id': ta.id, 'x_sequence': p.x_sequence, 'x_requiere_adjunto': p.x_requiere_adjunto, 'x_vence': vence})
    ini.message_post(body='Inicio de obra creado: tareas asignadas a cada área.')
'''
CODE_ITEM = r'''
# Sello de evidencia (2.2): quién y cuándo, lo pone el servidor. Recalcula avance; si 100% avisa al COO.
for it in records:
    if it.x_hecho and not it.x_hecho_at:
        if it.x_requiere_adjunto and not env['ir.attachment'].search_count([('res_model','=','x_inicio_obra_item'),('res_id','=',it.id)]):
            raise UserError('Este ítem requiere un adjunto antes de marcarlo: ' + it.x_name)
        now = datetime.datetime.now()
        it.write({'x_observado': False, 'x_hecho_user_id': env.user.id, 'x_hecho_at': now, 'x_fuera_termino': bool(it.x_vence and now > it.x_vence)})
    elif not it.x_hecho and it.x_hecho_at:
        it.write({'x_hecho_user_id': False, 'x_hecho_at': False, 'x_fuera_termino': False})
for ini in records.mapped('x_inicio_id'):
    for ta in ini.x_tarea_ids:
        if ta.x_no_aplica and not (ta.x_no_aplica_motivo or '').strip(): raise UserError('"No aplica" requiere motivo: ' + ta.x_name)
        its = ini.x_item_ids.filtered(lambda i: i.x_tarea_id == ta)
        ta.write({'x_completa': bool(ta.x_no_aplica or all(its.mapped('x_hecho')))})
    vivos = ini.x_item_ids.filtered(lambda i: not i.x_tarea_id.x_no_aplica)
    tot = len(ini.x_item_ids); ok = len(vivos.filtered('x_hecho')) + (tot - len(vivos))
    vals = {'x_items_total': tot, 'x_items_ok': ok, 'x_avance': (100.0*ok/tot) if tot else 0}
    for t in ini.x_item_ids.mapped('x_task_id'):
        pend = t.x_io_inicio_id and ini.x_item_ids.filtered(lambda i: i.x_task_id == t and not i.x_hecho)
        t.write({'state': '01_in_progress' if pend else '1_done'})
    if tot and all(ini.x_tarea_ids.mapped('x_completa')) and ini.x_state in ('carga','observado'):
        vals.update({'x_state': 'completo', 'x_completo_at': datetime.datetime.now()})
        ini.write(vals)
        coo = env['res.users'].browse(COO_UID)
        ini.activity_schedule('mail.mail_activity_data_todo', user_id=coo.id, summary='Inicio de obra completo: presentar al CEO')
        ini.message_post(body='Las 11 áreas completaron su checklist (o marcaron No aplica).', partner_ids=[coo.partner_id.id])
    else:
        ini.write(vals)
'''
CODE_APROBAR = r'''
if not env.user.has_group('base.group_system') and not env.user.groups_id.filtered(lambda g: g.name == GROUP_CEO):
    raise UserError('Solo el CEO puede aprobar el inicio de obra.')
for ini in records:
    if ini.x_state != 'completo': raise UserError('Faltan ítems por completar.')
    ronda = (ini.x_ronda or 0) + 1
    env['x_inicio_obra_ronda'].create({'x_name': 'Ronda %d' % ronda, 'x_inicio_id': ini.id, 'x_numero': ronda, 'x_resultado': 'aprobado', 'x_at': datetime.datetime.now(), 'x_avance': ini.x_avance, 'x_obs': ini.x_ceo_obs})
    ini.write({'x_state': 'aprobado', 'x_ronda': ronda, 'x_ceo_user_id': env.user.id, 'x_ceo_at': datetime.datetime.now()})
    ini.message_post(body='Inicio formal de obra APROBADO por ' + env.user.name + '.')
'''

CODE_OBSERVAR = r'''
# CEO devuelve como Observado: obs obligatoria; reabre áreas/ítems marcados en x_observada / x_observado (los elige el CEO en el form o la app).
for ini in records:
    if ini.x_state != 'completo': raise UserError('Solo se puede observar un inicio completo.')
    if not (ini.x_ceo_obs or '').strip(): raise UserError('La observación es obligatoria para devolver.')
    tareas = ini.x_tarea_ids.filtered('x_observada'); items = ini.x_item_ids.filtered('x_observado')
    if not tareas and not items: raise UserError('Indicá qué áreas o ítems se reabren.')
    tareas |= items.mapped('x_tarea_id')
    ronda = (ini.x_ronda or 0) + 1
    env['x_inicio_obra_ronda'].create({'x_name': 'Ronda %d' % ronda, 'x_inicio_id': ini.id, 'x_numero': ronda, 'x_resultado': 'observado', 'x_obs': ini.x_ceo_obs,
        'x_at': datetime.datetime.now(), 'x_avance': ini.x_avance, 'x_tarea_ids': [(6,0,tareas.ids)], 'x_item_ids': [(6,0,items.ids)]})
    reabrir = items or ini.x_item_ids.filtered(lambda i: i.x_tarea_id in tareas)
    reabrir.write({'x_hecho': False, 'x_hecho_user_id': False, 'x_hecho_at': False, 'x_hecho_usuario_id': False, 'x_observado': True})
    tareas.write({'x_completa': False, 'x_no_aplica': False, 'x_obs_ceo': ini.x_ceo_obs})
    ini.write({'x_state': 'observado', 'x_ronda': ronda, 'x_ceo_obs': False})
    for ta in tareas:
        ps = env['x_inicio_obra_usuario'].search([('x_area_ids','in',ta.x_area_id.id)]).mapped('x_user_id.partner_id')
        ini.message_post(body='Observado por CEO (ronda %d) · %s: %s' % (ronda, ta.x_name, ta.x_obs_ceo), partner_ids=ps.ids)
        # usuarios sin Odoo: el backend de la app les manda email (x_email) y lo muestra como pendiente
'''
CODE_NO_APLICA = r'''
for ta in records:
    if ta.x_no_aplica and not ta.x_no_aplica_at:
        if not (ta.x_no_aplica_motivo or '').strip(): raise UserError('Indicá el motivo de "No aplica a esta obra".')
        u = env['x_inicio_obra_usuario'].search([('x_user_id','=',env.user.id)], limit=1)
        ta.write({'x_no_aplica_at': datetime.datetime.now(), 'x_no_aplica_usuario_id': ta.x_no_aplica_usuario_id.id or u.id, 'x_completa': True})
        ta.x_inicio_id.message_post(body='%s: No aplica a esta obra. Motivo: %s' % (ta.x_name, ta.x_no_aplica_motivo))
    elif not ta.x_no_aplica and ta.x_no_aplica_at:
        ta.write({'x_no_aplica_at': False, 'x_no_aplica_usuario_id': False})
    # dispara recálculo vía ítems
    ta.x_inicio_id.x_item_ids[:1].write({'x_obs': ta.x_inicio_id.x_item_ids[:1].x_obs})
'''
def form_view(model):
    return f'''<form string="Inicio de obra"><header>
<button name="__ACT_APROBAR__" type="action" string="Aprobar inicio (CEO)" class="btn-primary" invisible="x_state != 'completo'" groups="__GROUP_CEO__"/>
<button name="__ACT_OBSERVAR__" type="action" string="Devolver como Observado" invisible="x_state != 'completo'" groups="__GROUP_CEO__"/>
<field name="x_state" widget="statusbar"/></header><sheet>
<group><field name="x_name"/><field name="x_project_id"/><field name="x_avance" widget="progressbar"/>
<field name="x_items_ok"/><field name="x_items_total"/><field name="x_completo_at"/><field name="x_ceo_user_id"/><field name="x_ceo_at"/><field name="x_ceo_obs"/></group>
<notebook><page string="Áreas"><field name="x_tarea_ids"><list editable="bottom"><field name="x_area_id"/><field name="x_vence"/><field name="x_completa"/><field name="x_no_aplica"/><field name="x_no_aplica_motivo"/><field name="x_no_aplica_usuario_id" readonly="1"/><field name="x_no_aplica_at" readonly="1"/><field name="x_observada"/><field name="x_obs_ceo" readonly="1"/></list></field></page>
<page string="Rondas CEO"><field name="x_ronda_ids" readonly="1"><list><field name="x_numero"/><field name="x_resultado"/><field name="x_obs"/><field name="x_usuario_id"/><field name="x_at"/><field name="x_tarea_ids" widget="many2many_tags"/></list></field></page>
<page string="Ítems"><field name="x_item_ids"><list editable="bottom" default_group_by="x_area_id"><field name="x_area_id"/><field name="x_name"/><field name="x_hecho"/>
<field name="x_hecho_user_id" readonly="1"/><field name="x_hecho_at" readonly="1"/><field name="x_vence" readonly="1"/><field name="x_fuera_termino" readonly="1"/><field name="x_observado"/><field name="x_obs"/></list></field></page></notebook>
</sheet><chatter/></form>'''
VIEWS = [
 (P, "form", "form_view"),
 (P, "list", f'<list><field name="x_name"/><field name="x_project_id"/><field name="x_avance" widget="progressbar"/><field name="x_state"/><field name="x_ceo_at"/></list>'),
 (f"{P}_item", "list", '<list default_group_by="x_inicio_id"><field name="x_inicio_id"/><field name="x_area_id"/><field name="x_name"/><field name="x_hecho"/><field name="x_hecho_user_id"/><field name="x_hecho_at"/><field name="x_vence"/><field name="x_fuera_termino"/></list>'),
 (f"{P}_usuario", "list", '<list editable="bottom"><field name="x_name"/><field name="x_login"/><field name="x_email"/><field name="x_rol"/><field name="x_area_ids" widget="many2many_tags"/><field name="x_user_id"/><field name="x_active"/><field name="x_clave_configurada" readonly="1"/></list>'),
 (f"{P}_area", "list", '<list editable="bottom"><field name="x_sequence" widget="handle"/><field name="x_code"/><field name="x_name"/><field name="x_plazo_horas"/><field name="x_active"/></list>'),
]

class Odoo:
    def __init__(s, apply):
        s.url = os.environ.get("ODOO_URL","https://cooperativa-de-trabajo-el-sol.odoo.com"); s.db = os.environ.get("ODOO_DB","cooperativa-de-trabajo-el-sol")
        s.key = (os.environ.get("ODOO_API_KEY") or os.environ.get("ODOO_API_KEY_ADMIN_ARME","")).strip(); s.uid = int(os.environ.get("ODOO_UID","2"))
        if not s.key: sys.exit("Falta ODOO_API_KEY")
        s.m = xmlrpc.client.ServerProxy(s.url+"/xmlrpc/2/object", allow_none=True); s.apply = apply; s.log = []; s.n = 0
    def r(s, model, method, *a, **k): return s.m.execute_kw(s.db, s.uid, s.key, model, method, list(a), k)
    def create(s, model, vals, label):
        s.n += 1
        if not s.apply:
            print(f"  [dry] {s.n:03d} create {model:28s} {label}"); return -s.n
        rid = s.r(model, "create", vals); s.log.append([model, rid, label]); s.save(); print(f"  [ok ] {model} #{rid} {label}"); return rid
    def save(s): json.dump({"created": s.log, "ts": s.ts}, open(s.bk, "w"), indent=1, ensure_ascii=False)

def run(apply):
    o = Odoo(apply); o.ts = time.strftime("%Y%m%d-%H%M%S"); o.bk = os.path.join(HERE, f"backup-{o.ts}.json")
    mg = json.load(open(os.path.join(HERE, "managers.local.json")))
    print(f"== Inicio de obra · {'APPLY' if apply else 'DRY-RUN (no escribe nada)'} ==")
    # Pre-chequeos (lecturas)
    exist = o.r("ir.model","search_read",[["model","like",P]],fields=["model"])
    if exist: sys.exit(f"Ya existen modelos {P}*: {[e['model'] for e in exist]} -> abortar (usar --rollback)")
    uids = [u["user_id"] for u in mg["usuarios"] if u["user_id"]]
    ok_u = {u["id"]: u["name"] for u in o.r("res.users","read",uids,fields=["name"])}
    print(f"Pre-chequeo: {len(ok_u)}/{len(set(uids))} usuarios de gerentes existen; sin usuario Odoo (entran por la tabla de la app): {[u['name'] for u in mg['usuarios'] if not u['user_id']]}")
    if apply:  # backup de lo que toca (solo lectura previa para registro)
        snap = {"project_task_fields": sorted(k for k in o.r("project.task","fields_get",attributes=["type"]) if k.startswith("x_io")),
                "automations": o.r("base.automation","search_read",[],fields=["name"])}
        json.dump(snap, open(os.path.join(HERE, f"snapshot-{o.ts}.json"),"w"), ensure_ascii=False)
    print("1) Modelos y campos")
    mid = {}
    for model, name, chatter, fields in MODELS:
        vals = {"model": model, "name": name, "state": "manual", "is_mail_thread": chatter, "is_mail_activity": chatter}
        mid[model] = o.create("ir.model", vals, f"{model} ({name}){' +chatter' if chatter else ''}")
        for fn, ft, fl, extra in fields:
            o.create("ir.model.fields", {"model_id": mid[model], "name": fn, "ttype": ft, "field_description": fl, "state": "manual", **extra}, f"  {model}.{fn} [{ft}]")
    for model, fn, fl, rel, inv in ONE2MANY:
        o.create("ir.model.fields", {"model_id": mid[model], "name": fn, "ttype": "one2many", "field_description": fl, "relation": rel, "relation_field": inv, "state": "manual"}, f"  {model}.{fn} [one2many]")
    for model, fn, fl, rel, tbl, c1, c2 in M2M:
        o.create("ir.model.fields", {"model_id": mid[model], "name": fn, "ttype": "many2many", "field_description": fl, "relation": rel, "relation_table": tbl, "column1": c1, "column2": c2, "state": "manual"}, f"  {model}.{fn} [many2many]")
    for target, flds in (("project.task", TASK_FIELDS), ("project.project", PROJECT_FIELDS)):
        tid = o.r("ir.model","search",[["model","=",target]])[0]
        for fn, ft, fl, extra in flds:
            o.create("ir.model.fields", {"model_id": tid, "name": fn, "ttype": ft, "field_description": fl, "state": "manual", **extra}, f"  {target}.{fn} [{ft}]")
    print("2) Grupos y permisos")
    g_ceo = o.create("res.groups", {"name": GROUP_CEO}, GROUP_CEO + f" (miembro: CEO={mg.get('CEO')})")
    g_ver = o.create("res.groups", {"name": GROUP_VER}, GROUP_VER + f" (COO, secretaria, UGEOP)")
    g_user = o.r("ir.model.data","search_read",[["module","=","base"],["name","=","group_user"]],fields=["res_id"])[0]["res_id"]
    for model in mid:
        cfg = model in (f"{P}_area", f"{P}_plantilla", f"{P}_usuario", f"{P}_ronda")
        o.create("ir.model.access", {"name": f"acc_{model}_user", "model_id": mid[model], "group_id": g_user, "perm_read": True, "perm_write": not cfg, "perm_create": False, "perm_unlink": False}, f"{model}: internos leen{'' if cfg else '+escriben'}")
        o.create("ir.model.access", {"name": f"acc_{model}_ver", "model_id": mid[model], "group_id": g_ver, "perm_read": True, "perm_write": True, "perm_create": True, "perm_unlink": False}, f"{model}: consolidado CRUD sin borrar")
    for mm in (f"{P}_item", f"{P}_tarea"):
      o.create("ir.rule", {"name": f"{mm}: cada gerente edita solo su área", "model_id": mid[mm], "groups": [(4, g_user)],
        "domain_force": "[('x_area_id','in',user.env['x_inicio_obra_usuario'].search([('x_user_id','=',user.id)]).x_area_ids.ids)]", "perm_read": False, "perm_write": True, "perm_create": False, "perm_unlink": False}, f"regla escritura por gerente en {mm} (2.1 indelegable; usuarios sin Odoo pasan por backend)")
    aid_by = {}
    print("3) Configuración: 11 áreas + ítems plantilla")
    for i, a in enumerate(CHK["areas"]):
        aid = aid_by[a["code"]] = o.create(f"{P}_area", {"x_name": a["name"], "x_code": a["code"], "x_sequence": (i+1)*10, "x_plazo_horas": a["plazo_h"], "x_active": True},
                       f"{a['code']} {a['name']} plazo {a['plazo_h']}h lun-sáb")
        for j, it in enumerate(a["items"]):
            n, _, f = it.partition("|")
            o.create(f"{P}_plantilla", {"x_name": n, "x_area_id": aid, "x_sequence": j+1, "x_requiere_adjunto": f == "adj"}, f"    · {n[:60]}{' [adj]' if f else ''}")
    print("3b) Usuarios de la app (x_inicio_obra_usuario) — sin claves: las maneja el backend")
    for u in mg["usuarios"]:
        o.create(f"{P}_usuario", {"x_name": u["name"], "x_rol": u["rol"], "x_active": True, "x_user_id": u["user_id"] or False,
                 "x_area_ids": [(6,0,[aid_by[c] for c in u["areas"]])] if apply else []},
                 f"{u['name']} · {u['rol']} · áreas {','.join(u['areas']) or '-'} · res.users {u['user_id'] or 'NINGUNO (completar login/email)'}")
    print("4) Acciones de servidor y automatizaciones")
    hdr = f"COO_UID = {mg['COO']}\nGROUP_CEO = {GROUP_CEO!r}\n"
    sa_crear = o.create("ir.actions.server", {"name": "Inicio de obra · crear tareas por área", "model_id": o.r("ir.model","search",[["model","=","project.project"]])[0], "state": "code", "code": CODE_CREAR}, "server action crear")
    o.create("base.automation", {"name": "Inicio de obra · al crear OT", "model_id": o.r("ir.model","search",[["model","=","project.project"]])[0], "trigger": "on_create", "action_server_ids": [(6,0,[sa_crear])] if apply else []}, "automation on_create project.project (TODO proyecto nuevo)")
    sa_item = o.create("ir.actions.server", {"name": "Inicio de obra · sellar ítem y recalcular", "model_id": mid[f"{P}_item"], "state": "code", "code": hdr + CODE_ITEM}, "server action ítem")
    o.create("base.automation", {"name": "Inicio de obra · ítem marcado", "model_id": mid[f"{P}_item"], "trigger": "on_create_or_write", "trigger_field_ids": [], "action_server_ids": [(6,0,[sa_item])] if apply else []}, "automation on_write x_hecho")
    sa_obs = o.create("ir.actions.server", {"name": "Devolver como Observado (CEO)", "model_id": mid[P], "state": "code", "code": hdr + CODE_OBSERVAR}, "server action observar CEO (botón)")
    sa_na = o.create("ir.actions.server", {"name": "Inicio de obra · No aplica", "model_id": mid[f"{P}_tarea"], "state": "code", "code": hdr + CODE_NO_APLICA}, "server action No aplica")
    o.create("base.automation", {"name": "Inicio de obra · área No aplica / recalcular", "model_id": mid[f"{P}_tarea"], "trigger": "on_create_or_write", "action_server_ids": [(6,0,[sa_na])] if apply else []}, "automation on_write x_no_aplica (sella quién/cuándo, motivo obligatorio, recalcula)")
    sa_apr = o.create("ir.actions.server", {"name": "Aprobar inicio (CEO)", "model_id": mid[P], "state": "code", "code": hdr + CODE_APROBAR, "binding_model_id": mid[P]}, "server action aprobar CEO (botón)")
    print("5) Vistas, acción y menú (Proyecto > Inicio de obra)")
    for model, vt, arch in VIEWS:
        if arch == "form_view": arch = form_view(model).replace("__ACT_APROBAR__", str(sa_apr)).replace("__ACT_OBSERVAR__", str(sa_obs)).replace("__GROUP_CEO__", "base.group_system")
        o.create("ir.ui.view", {"name": f"{model}.{vt}", "model": model, "type": vt, "arch_base": arch}, f"vista {vt} {model}")
    act = o.create("ir.actions.act_window", {"name": "Inicio de obra", "res_model": P, "view_mode": "list,form"}, "acción ventana")
    act_i = o.create("ir.actions.act_window", {"name": "Checklist consolidado", "res_model": f"{P}_item", "view_mode": "list"}, "acción consolidado")
    act_a = o.create("ir.actions.act_window", {"name": "Áreas y gerentes", "res_model": f"{P}_area", "view_mode": "list"}, "acción config")
    parent = o.r("ir.ui.menu","search",[["name","=","Project"],["parent_id","=",False]]) or o.r("ir.ui.menu","search",[["name","ilike","Proyecto"],["parent_id","=",False]])
    act_u = o.create("ir.actions.act_window", {"name": "Usuarios de la app", "res_model": f"{P}_usuario", "view_mode": "list"}, "acción usuarios app (admin)")
    for nm, a, seq in (("Usuarios de la app", act_u, 53), ("Inicio de obra", act, 50), ("Checklist consolidado", act_i, 51), ("Áreas y gerentes", act_a, 52)):
        o.create("ir.ui.menu", {"name": nm, "parent_id": parent[0] if parent else False, "action": f"ir.actions.act_window,{a}", "sequence": seq}, f"menú {nm}")
    print(f"== Total operaciones: {o.n}. {'Backup: '+o.bk if apply else 'Nada fue escrito.'}")
    print("Nota: el botón CEO usa el grupo propio en prod (en dry-run se muestra base.group_system como placeholder); agregar CEO/COO/secretaria/UGEOP a los grupos al aplicar.")

def rollback(path):
    o = Odoo(True); d = json.load(open(path))
    for model, rid, label in reversed(d["created"]):
        try: o.r(model, "unlink", [rid]); print(f"  [del] {model} #{rid} {label}")
        except Exception as e: print(f"  [ERR] {model} #{rid}: {str(e)[:120]}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true"); g.add_argument("--apply", action="store_true"); g.add_argument("--rollback", metavar="BACKUP")
    a = ap.parse_args()
    if a.rollback: rollback(a.rollback)
    elif a.apply:
        if input("Escribe en Odoo PRODUCCIÓN. Escribí APLICAR: ") != "APLICAR": sys.exit("cancelado")
        run(True)
    else: run(False)
