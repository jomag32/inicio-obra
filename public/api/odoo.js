// Capa de datos real: habla con el backend (/api), que opera en Odoo con la sesión del propio usuario.
const tok = () => JSON.parse(localStorage.getItem("io_sesion2") || "null")?.token;
async function q(metodo, ruta, cuerpo) {
  const r = await fetch("/api/" + ruta, { method: metodo, headers: { "Content-Type": "application/json", ...(tok() ? { Authorization: "Bearer " + tok() } : {}) }, body: cuerpo ? JSON.stringify(cuerpo) : undefined });
  const j = await r.json().catch(() => ({ error: "Sin conexión con el servidor." }));
  if (r.status === 401 && ruta !== "ingresar") { localStorage.removeItem("io_sesion2"); location.hash = "#/ingresar"; }
  if (!r.ok) throw new Error(j.error || "Error"); return j;
}
let cache = null;
export async function cargar() { return (cache = await q("GET", "datos")); }
export const areaCompleta = (db, ot, aid) => { const t = db.tareas.find((x) => x.ot === ot && x.area_id === aid); return !!t && (t.no_aplica || db.items.filter((i) => i.ot === ot && i.area_id === aid).every((i) => i.hecho)); };
export const ingresar = (login, clave) => q("POST", "ingresar", { login, clave });
const b64 = (f) => new Promise((ok, mal) => { const r = new FileReader(); r.onload = () => ok(String(r.result).split(",")[1]); r.onerror = mal; r.readAsDataURL(f); });
export async function marcar(_u, item, hecho, archivo) {
  const c = { item }; if (archivo) c.adjunto = { nombre: archivo.name, tipo: archivo.type, datos: await b64(archivo) }; else c.hecho = hecho;
  return q("POST", "marcar", c);
}
export const noAplica = (_u, ot, area, valor, motivo) => q("POST", "no-aplica", { ot, area, valor, motivo });
export const aprobar = (_u, ot, obs) => q("POST", "aprobar", { ot, obs });
export const observar = async (_u, ot, obs, areas) => (await q("POST", "observar", { ot, obs, areas })).avisados;
export const guardarUsuario = (_u, id, c) => q("POST", "usuario", { fila: cache?.usuarios.find((x) => x.id === id)?.fila, activo: c.activo });
export const demo = false;
