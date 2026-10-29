// Capa de datos SIMULADA. Refleja los modelos planeados en Odoo (x_inicio_obra, x_inicio_obra_item, x_inicio_obra_area).
// Sin nombres reales: los gerentes reales viven solo en la config de Odoo. En producción esto lo reemplaza api/odoo.js
// (backend propio con cuenta de servicio, patrón hys-carga: token HMAC por usuario, la API key nunca va al teléfono).
const K = "io_mock_v1";
export async function cargar() {
  let db = JSON.parse(localStorage.getItem(K) || "null");
  if (db) return db;
  const chk = await (await fetch("datos/checklist.json")).json();
  const usuarios = chk.areas.map((a, i) => ({ id: 100 + i, nombre: `Gerente ${a.name}`, rol: "gerente", area: a.code }));
  usuarios.push({ id: 200, nombre: "COO (ejemplo)", rol: "coo" }, { id: 201, nombre: "Secretaría COO (ejemplo)", rol: "consolidado" }, { id: 202, nombre: "CEO (ejemplo)", rol: "ceo" });
  const areas = chk.areas.map((a, i) => ({ id: i + 1, code: a.code, name: a.name, user_id: 100 + i, plazo_h: a.plazo_h }));
  const obras = [{ id: 9101, name: "OT 9101 - Galpón Ejemplo Norte", creada: "2026-10-27T09:00:00-03:00" },
                 { id: 9102, name: "OT 9102 - Tanque Ejemplo Sur", creada: "2026-10-28T15:00:00-03:00" }];
  const items = []; let id = 1;
  for (const ot of obras) chk.areas.forEach((a, ai) => a.items.forEach((t, j) => {
    const [name, f] = t.split("|"); const vence = new Date(new Date(ot.creada).getTime() + a.plazo_h * 3600e3).toISOString();
    const hecho = ot.id === 9101 ? (ai < 9 || (ai === 9 && j < 2)) : (ai < 3 && j < 2);
    items.push({ id: id++, ot: ot.id, area_id: ai + 1, name, adj: f === "adj", vence, hecho,
      hecho_por: hecho ? 100 + ai : null, hecho_at: hecho ? new Date(new Date(ot.creada).getTime() + (6 + j) * 3600e3 + (ai === 4 ? 60 * 3600e3 : 0)).toISOString() : null,
      adjuntos: hecho && f === "adj" ? ["documento-ejemplo.pdf"] : [], obs: "" });
  }));
  db = { usuarios, areas, obras, items, aprob: {} };
  localStorage.setItem(K, JSON.stringify(db)); return db;
}
const guardar = (db) => localStorage.setItem(K, JSON.stringify(db));
export async function ingresar(uid, clave) { const db = await cargar(); const u = db.usuarios.find((x) => x.id === uid);
  if (!u || clave !== "demo") throw new Error("Contraseña incorrecta."); return u; }
export async function marcar(u, itemId, hecho, adjunto) {
  const db = await cargar(); const it = db.items.find((i) => i.id === itemId); const area = db.areas.find((a) => a.id === it.area_id);
  if (area.user_id !== u.id) throw new Error("Solo el gerente del área puede marcar este ítem.");
  if (adjunto) it.adjuntos.push(adjunto);
  if (hecho && it.adj && !it.adjuntos.length) throw new Error("Este ítem requiere un adjunto.");
  it.hecho = hecho; it.hecho_por = hecho ? u.id : null; it.hecho_at = hecho ? new Date().toISOString() : null; guardar(db); return it;
}
export async function aprobar(u, ot, obs) { const db = await cargar(); if (u.rol !== "ceo") throw new Error("Solo el CEO aprueba.");
  db.aprob[ot] = { por: u.id, at: new Date().toISOString(), obs }; guardar(db); }
