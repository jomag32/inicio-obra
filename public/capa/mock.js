// Capa de datos SIMULADA, espejo de los modelos planeados en Odoo:
// x_inicio_obra_usuario (usuarios de la app), x_inicio_obra_area, x_inicio_obra (por OT), x_inicio_obra_tarea (área por obra,
// "No aplica"), x_inicio_obra_item, x_inicio_obra_ronda (historial CEO). Sin nombres reales. En producción lo reemplaza un
// backend propio (patrón hys-carga): login contra x_inicio_obra_usuario, clave con hash solo en el backend, token HMAC.
const K = "io_mock_v2";
export function venceLunSab(desde, horas) { // suma horas salteando domingos
  let d = new Date(desde);
  while (horas > 0) {
    if (d.getDay() === 0) { d = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1); continue; }
    const fin = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1), h = Math.min(horas, (fin - d) / 3600e3);
    d = new Date(d.getTime() + h * 3600e3); horas -= h;
  }
  return d.toISOString();
}
export async function cargar() {
  let db = JSON.parse(localStorage.getItem(K) || "null"); if (db) return db;
  const chk = await (await fetch("datos/checklist.json")).json();
  const areas = chk.areas.map((a, i) => ({ id: i + 1, code: a.code, name: a.name, plazo_h: a.plazo_h }));
  const usuarios = areas.map((a, i) => ({ id: 100 + i, nombre: `Gerente ${a.name}`, login: `gerente.${a.code.toLowerCase()}`, rol: a.code === "UGE" ? "ugeop" : "gerente", areas: [a.id], activo: true, odoo: i % 3 !== 2, clave: true }));
  usuarios.push({ id: 120, nombre: "Gerente Legales 2", login: "legales.2", rol: "gerente", areas: [2], activo: true, odoo: false, clave: false },
    { id: 200, nombre: "COO (ejemplo)", login: "coo", rol: "coo", areas: [], activo: true, odoo: true, clave: true },
    { id: 201, nombre: "Secretaría COO (ejemplo)", login: "secretaria", rol: "secretaria", areas: [], activo: true, odoo: true, clave: true },
    { id: 202, nombre: "CEO (ejemplo)", login: "ceo", rol: "ceo", areas: [], activo: true, odoo: false, clave: true });
  const obras = [{ id: 9101, name: "OT 9101 - Galpón Ejemplo Norte", creada: "2026-10-24T09:00:00-03:00", estado: "carga", ronda: 0 },
                 { id: 9102, name: "OT 9102 - Tanque Ejemplo Sur", creada: "2026-10-28T15:00:00-03:00", estado: "carga", ronda: 0 }];
  const tareas = [], items = []; let id = 1, tid = 1;
  for (const ot of obras) chk.areas.forEach((a, ai) => {
    const vence = venceLunSab(ot.creada, a.plazo_h), t = { id: tid++, ot: ot.id, area_id: ai + 1, vence, no_aplica: false, motivo: "", na_por: null, na_at: null, observada: false, obs_ceo: "" };
    if (ot.id === 9101 && a.code === "COP") Object.assign(t, { no_aplica: true, motivo: "Materiales provistos por el cliente; no hay compras para esta obra.", na_por: 105, na_at: "2026-10-24T13:20:00-03:00" });
    tareas.push(t);
    a.items.forEach((s, j) => { const [name, f] = s.split("|"); const hecho = !t.no_aplica && (ot.id === 9101 ? (ai < 9 || (ai === 9 && j < 2)) : (ai < 3 && j < 2));
      items.push({ id: id++, ot: ot.id, area_id: ai + 1, name, adj: f === "adj", vence, hecho, hecho_por: hecho ? 100 + ai : null,
        hecho_at: hecho ? new Date(new Date(ot.creada).getTime() + (6 + j) * 3600e3).toISOString() : null, adjuntos: hecho && f === "adj" ? ["documento-ejemplo.pdf"] : [], observado: false }); });
  });
  db = { usuarios, areas, obras, tareas, items, rondas: [] }; localStorage.setItem(K, JSON.stringify(db)); return db;
}
const guardar = (db) => localStorage.setItem(K, JSON.stringify(db));
const esDe = (u, aid) => u.areas.includes(aid);
export const areaCompleta = (db, ot, aid) => { const t = db.tareas.find((x) => x.ot === ot && x.area_id === aid); return t.no_aplica || db.items.filter((i) => i.ot === ot && i.area_id === aid).every((i) => i.hecho); };
function recalcular(db, ot) { const o = db.obras.find((x) => x.id === ot); if (["carga", "observado"].includes(o.estado) && db.areas.every((a) => areaCompleta(db, ot, a.id))) o.estado = "completo"; }
export async function ingresar(login, clave) { const db = await cargar(); const u = db.usuarios.find((x) => x.login === login && x.activo);
  if (!u || clave !== "demo") throw new Error("Usuario o contraseña incorrectos."); return u; }
export async function marcar(u, itemId, hecho, adjunto) {
  const db = await cargar(), it = db.items.find((i) => i.id === itemId);
  if (!esDe(u, it.area_id)) throw new Error("Solo el gerente del área puede marcar este ítem.");
  if (adjunto) it.adjuntos.push(adjunto);
  if (hecho && it.adj && !it.adjuntos.length) throw new Error("Este ítem requiere un adjunto.");
  Object.assign(it, { hecho, hecho_por: hecho ? u.id : null, hecho_at: hecho ? new Date().toISOString() : null, observado: hecho ? false : it.observado });
  recalcular(db, it.ot); guardar(db);
}
export async function noAplica(u, ot, aid, valor, motivo) {
  const db = await cargar(), t = db.tareas.find((x) => x.ot === ot && x.area_id === aid);
  if (!esDe(u, aid)) throw new Error("Solo el gerente del área decide si aplica.");
  if (valor && !motivo.trim()) throw new Error("Escribí el motivo de «No aplica».");
  Object.assign(t, { no_aplica: valor, motivo: valor ? motivo.trim() : "", na_por: valor ? u.id : null, na_at: valor ? new Date().toISOString() : null, observada: valor ? false : t.observada });
  recalcular(db, ot); guardar(db);
}
export async function aprobar(u, ot, obs) { const db = await cargar(), o = db.obras.find((x) => x.id === ot);
  if (u.rol !== "ceo") throw new Error("Solo el CEO aprueba."); if (o.estado !== "completo") throw new Error("Faltan áreas.");
  o.ronda++; o.estado = "aprobado"; db.rondas.push({ ot, n: o.ronda, res: "aprobado", obs, por: u.id, at: new Date().toISOString(), areas: [] }); guardar(db); }
export async function observar(u, ot, obs, areaIds) { const db = await cargar(), o = db.obras.find((x) => x.id === ot);
  if (u.rol !== "ceo") throw new Error("Solo el CEO devuelve."); if (!obs.trim()) throw new Error("La observación es obligatoria.");
  if (!areaIds.length) throw new Error("Elegí al menos un área a reabrir.");
  o.ronda++; o.estado = "observado"; db.rondas.push({ ot, n: o.ronda, res: "observado", obs: obs.trim(), por: u.id, at: new Date().toISOString(), areas: areaIds });
  for (const aid of areaIds) { const t = db.tareas.find((x) => x.ot === ot && x.area_id === aid); Object.assign(t, { observada: true, obs_ceo: obs.trim(), no_aplica: false, motivo: "", na_por: null, na_at: null });
    db.items.filter((i) => i.ot === ot && i.area_id === aid).forEach((i) => Object.assign(i, { hecho: false, hecho_por: null, hecho_at: null, observado: true })); }
  guardar(db); return areaIds.map((aid) => db.usuarios.filter((x) => x.areas.includes(aid)).map((x) => x.nombre)).flat(); }
export async function guardarUsuario(u, id, cambios) { const db = await cargar(); if (!["coo", "secretaria"].includes(u.rol)) throw new Error("Sin permiso.");
  Object.assign(db.usuarios.find((x) => x.id === id), cambios); guardar(db); }
