// Backend de la app "Inicio de obra" (Tecnología ARME).
// - Sirve la PWA (carpeta public/) y una API JSON en /api/*.
// - NO guarda contraseñas ni usa una cuenta de servicio: cada usuario ingresa con SU usuario de Odoo (contraseña o API key
//   personal). El backend la verifica contra Odoo (common.authenticate) y exige una fila activa en x_inicio_obra_usuario.
//   Todo lo que el usuario hace se ejecuta en Odoo con su propia sesión, así el sello quién/cuándo (punto 2.2) es nativo.
// - La credencial viaja solo dentro de un token cifrado AES-256-GCM con IO_SESSION_SECRET (env de Render), nunca en claro.
const http = require("http"), fs = require("fs"), path = require("path"), crypto = require("crypto");
const ODOO_URL = (process.env.ODOO_URL || "").replace(/\/$/, ""), ODOO_DB = process.env.ODOO_DB || "";
const SECRET = process.env.IO_SESSION_SECRET || "", PORT = +process.env.PORT || 10000;
const TTL_DIAS = +process.env.SESSION_DAYS || 30, MAX_BODY = (+process.env.MAX_BODY_MB || 12) * 1048576;
const RATE = +process.env.RATE_LIMIT_PER_MIN || 120, DIAS_APROBADAS = +process.env.DIAS_APROBADAS || 15;
if (!ODOO_URL || !ODOO_DB || SECRET.length < 32) { console.error("Faltan ODOO_URL, ODOO_DB o IO_SESSION_SECRET (>=32)"); process.exit(1); }
const KEY = crypto.createHash("sha256").update(SECRET).digest();

// ---------- Odoo JSON-RPC ----------
let rid = 0;
async function rpc(service, method, args) {
  const r = await fetch(ODOO_URL + "/jsonrpc", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", method: "call", id: ++rid, params: { service, method, args } }) });
  const j = await r.json();
  if (j.error) { const m = j.error.data?.message || j.error.message || "Error de Odoo"; const e = new Error(m); e.odoo = true; throw e; }
  return j.result;
}
const ex = (s, model, method, args = [], kw = {}) => rpc("object", "execute_kw", [ODOO_DB, s.uid, s.pwd, model, method, args, kw]);

// ---------- token cifrado ----------
function firmar(o) { const iv = crypto.randomBytes(12), c = crypto.createCipheriv("aes-256-gcm", KEY, iv);
  const d = Buffer.concat([c.update(JSON.stringify(o), "utf8"), c.final()]); return Buffer.concat([iv, c.getAuthTag(), d]).toString("base64url"); }
function abrir(t) { try { const b = Buffer.from(t, "base64url"), d = crypto.createDecipheriv("aes-256-gcm", KEY, b.subarray(0, 12));
  d.setAuthTag(b.subarray(12, 28)); const o = JSON.parse(Buffer.concat([d.update(b.subarray(28)), d.final()]).toString("utf8"));
  return o.exp > Date.now() ? o : null; } catch { return null; } }

// ---------- límites ----------
const fallos = new Map(), ritmo = new Map();
function bloqueado(k) { const f = (fallos.get(k) || []).filter((t) => t > Date.now() - 15 * 60e3); fallos.set(k, f); return f.length >= 8; }
function demasiado(ip) { const m = Math.floor(Date.now() / 60e3), r = ritmo.get(ip); if (!r || r.m !== m) { ritmo.set(ip, { m, n: 1 }); return false; } return ++r.n > RATE; }

// ---------- utilidades ----------
const iso = (d) => (d ? d.replace(" ", "T") + "Z" : null), m2o = (v) => (Array.isArray(v) ? v[0] : null);
class Err extends Error { constructor(m, s = 400) { super(m); this.status = s; } }
async function perfil(s) {
  const u = await ex(s, "x_inicio_obra_usuario", "search_read", [[["x_user_id", "=", s.uid], ["x_active", "=", true]]], { fields: ["x_name", "x_rol", "x_area_ids"], limit: 1 });
  if (!u.length) throw new Err("Tu usuario de Odoo no está habilitado en la app (Proyecto › Usuarios de la app).", 403);
  return { id: s.uid, nombre: u[0].x_name, rol: u[0].x_rol || "gerente", areas: u[0].x_area_ids };
}
async function datos(s) {
  const desde = new Date(Date.now() - DIAS_APROBADAS * 864e5).toISOString().slice(0, 19).replace("T", " ");
  const obras = await ex(s, "x_inicio_obra", "search_read", [["|", ["x_state", "!=", "aprobado"], ["x_ceo_at", ">=", desde]]],
    { fields: ["x_name", "x_project_id", "x_state", "x_ronda", "create_date"], order: "id desc", limit: 60 });
  const ids = obras.map((o) => o.id);
  const [areas, tareas, items, rondas, usuarios] = await Promise.all([
    ex(s, "x_inicio_obra_area", "search_read", [[["x_active", "=", true]]], { fields: ["x_code", "x_name", "x_plazo_horas"], order: "x_sequence" }),
    ex(s, "x_inicio_obra_tarea", "search_read", [[["x_inicio_id", "in", ids]]], { fields: ["x_inicio_id", "x_area_id", "x_vence", "x_no_aplica", "x_no_aplica_motivo", "x_no_aplica_usuario_id", "x_no_aplica_at", "x_observada", "x_obs_ceo"] }),
    ex(s, "x_inicio_obra_item", "search_read", [[["x_inicio_id", "in", ids]]], { fields: ["x_inicio_id", "x_area_id", "x_tarea_id", "x_name", "x_requiere_adjunto", "x_vence", "x_hecho", "x_hecho_user_id", "x_hecho_at", "x_observado"], order: "x_sequence, id" }),
    ex(s, "x_inicio_obra_ronda", "search_read", [[["x_inicio_id", "in", ids]]], { fields: ["x_inicio_id", "x_numero", "x_resultado", "x_obs", "x_at", "x_tarea_ids"], order: "x_numero" }),
    ex(s, "x_inicio_obra_usuario", "search_read", [[]], { fields: ["x_name", "x_login", "x_rol", "x_area_ids", "x_active", "x_user_id"], context: { active_test: false } }),
  ]);
  const itemIds = items.map((i) => i.id);
  const adj = itemIds.length ? await ex(s, "ir.attachment", "search_read", [[["res_model", "=", "x_inicio_obra_item"], ["res_id", "in", itemIds]]], { fields: ["name", "res_id"] }) : [];
  const usu = new Map(usuarios.map((u) => [u.id, m2o(u.x_user_id)]));
  const tareaArea = new Map(tareas.map((t) => [t.id, m2o(t.x_area_id)]));
  return {
    areas: areas.map((a) => ({ id: a.id, code: a.x_code, name: a.x_name, plazo_h: a.x_plazo_horas })),
    obras: obras.map((o) => ({ id: o.id, name: o.x_project_id ? o.x_project_id[1] : o.x_name, creada: iso(o.create_date), estado: o.x_state || "carga", ronda: o.x_ronda || 0 })),
    tareas: tareas.map((t) => ({ id: t.id, ot: m2o(t.x_inicio_id), area_id: m2o(t.x_area_id), vence: iso(t.x_vence), no_aplica: t.x_no_aplica, motivo: t.x_no_aplica_motivo || "",
      na_por: usu.get(m2o(t.x_no_aplica_usuario_id)) || null, na_at: iso(t.x_no_aplica_at), observada: t.x_observada, obs_ceo: t.x_obs_ceo || "" })),
    items: items.map((i) => ({ id: i.id, ot: m2o(i.x_inicio_id), area_id: m2o(i.x_area_id), tarea: m2o(i.x_tarea_id), name: i.x_name, adj: i.x_requiere_adjunto, vence: iso(i.x_vence),
      hecho: i.x_hecho, hecho_por: m2o(i.x_hecho_user_id), hecho_at: iso(i.x_hecho_at), observado: i.x_observado, adjuntos: adj.filter((a) => a.res_id === i.id).map((a) => a.name) })),
    rondas: rondas.map((r) => ({ ot: m2o(r.x_inicio_id), n: r.x_numero, res: r.x_resultado, obs: r.x_obs || "", at: iso(r.x_at), areas: r.x_tarea_ids.map((t) => tareaArea.get(t)).filter(Boolean) })),
    usuarios: usuarios.map((u) => ({ id: m2o(u.x_user_id), fila: u.id, nombre: u.x_name, login: u.x_login || "", rol: u.x_rol, areas: u.x_area_ids, activo: u.x_active, odoo: true, clave: true })),
  };
}
const correr = (s, accion, model, ids) => ex(s, "ir.actions.server", "run", [[accion]], { context: { active_model: model, active_ids: ids, active_id: ids[0] } });
const ACC = { aprobar: 2643, observar: 2640 };

const rutas = {
  "POST /api/ingresar": async (b, _s, ip) => {
    const login = String(b.login || "").trim().toLowerCase(), clave = String(b.clave || "");
    if (!login || !clave) throw new Err("Ingresá usuario y contraseña.");
    if (bloqueado(login) || bloqueado(ip)) throw new Err("Demasiados intentos. Probá de nuevo en 15 minutos.", 429);
    let uid = false; try { uid = await rpc("common", "authenticate", [ODOO_DB, login, clave, {}]); } catch { uid = false; }
    if (!uid) { for (const k of [login, ip]) fallos.set(k, [...(fallos.get(k) || []), Date.now()]); throw new Err("Usuario o contraseña de Odoo incorrectos.", 401); }
    const s = { uid, pwd: clave }, p = await perfil(s);
    return { ...p, token: firmar({ uid, pwd: clave, exp: Date.now() + TTL_DIAS * 864e5 }) };
  },
  "GET /api/yo": async (_b, s) => perfil(s),
  "GET /api/datos": async (_b, s) => datos(s),
  "POST /api/marcar": async (b, s) => {
    const id = +b.item; if (!id) throw new Err("Ítem inválido.");
    if (b.adjunto) { const { nombre, datos: d, tipo } = b.adjunto;
      await ex(s, "ir.attachment", "create", [{ name: String(nombre).slice(0, 200), datas: String(d), mimetype: tipo || undefined, res_model: "x_inicio_obra_item", res_id: id }]); }
    if (typeof b.hecho === "boolean") await ex(s, "x_inicio_obra_item", "write", [[id], { x_hecho: b.hecho }]);
    return { ok: true };
  },
  "POST /api/no-aplica": async (b, s) => {
    const t = await ex(s, "x_inicio_obra_tarea", "search", [[["x_inicio_id", "=", +b.ot], ["x_area_id", "=", +b.area]]], { limit: 1 });
    if (!t.length) throw new Err("Área no encontrada.", 404);
    if (b.valor && !String(b.motivo || "").trim()) throw new Err("Escribí el motivo de «No aplica».");
    await ex(s, "x_inicio_obra_tarea", "write", [t, b.valor ? { x_no_aplica: true, x_no_aplica_motivo: String(b.motivo).trim() } : { x_no_aplica: false, x_no_aplica_motivo: false }]);
    return { ok: true };
  },
  "POST /api/aprobar": async (b, s) => { const ot = +b.ot; if (b.obs) await ex(s, "x_inicio_obra", "write", [[ot], { x_ceo_obs: String(b.obs) }]); await correr(s, ACC.aprobar, "x_inicio_obra", [ot]); return { ok: true }; },
  "POST /api/observar": async (b, s) => {
    const ot = +b.ot, areas = (b.areas || []).map(Number); if (!String(b.obs || "").trim()) throw new Err("La observación es obligatoria."); if (!areas.length) throw new Err("Elegí al menos un área a reabrir.");
    const t = await ex(s, "x_inicio_obra_tarea", "search", [[["x_inicio_id", "=", ot], ["x_area_id", "in", areas]]]);
    await ex(s, "x_inicio_obra", "write", [[ot], { x_ceo_obs: String(b.obs).trim() }]); await ex(s, "x_inicio_obra_tarea", "write", [t, { x_observada: true }]);
    await correr(s, ACC.observar, "x_inicio_obra", [ot]);
    const us = await ex(s, "x_inicio_obra_usuario", "search_read", [[["x_area_ids", "in", areas], ["x_active", "=", true]]], { fields: ["x_name"] });
    return { avisados: us.map((u) => u.x_name) };
  },
  "POST /api/usuario": async (b, s) => { await ex(s, "x_inicio_obra_usuario", "write", [[+b.fila], { x_active: !!b.activo }]); return { ok: true }; },
};

// ---------- servidor ----------
const PUB = path.join(__dirname, "public"), MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".webmanifest": "application/manifest+json", ".png": "image/png" };
const SEG = { "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY", "Strict-Transport-Security": "max-age=31536000",
  "Content-Security-Policy": "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; connect-src 'self'" };
function enviar(res, st, o) { res.writeHead(st, { ...SEG, "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" }); res.end(JSON.stringify(o)); }
http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://x"), ip = (req.headers["x-forwarded-for"] || req.socket.remoteAddress || "").split(",")[0].trim();
  if (url.pathname === "/api/salud") return enviar(res, 200, { ok: true, servicio: "inicio-obra", odoo: !!ODOO_URL });
  if (url.pathname.startsWith("/api/")) {
    if (demasiado(ip)) return enviar(res, 429, { error: "Demasiadas solicitudes." });
    const f = rutas[req.method + " " + url.pathname]; if (!f) return enviar(res, 404, { error: "No existe." });
    let body = ""; let n = 0;
    for await (const ch of req) { n += ch.length; if (n > MAX_BODY) return enviar(res, 413, { error: "Archivo demasiado grande." }); body += ch; }
    try {
      let s = null;
      if (url.pathname !== "/api/ingresar") { s = abrir((req.headers.authorization || "").replace(/^Bearer /, "")); if (!s) return enviar(res, 401, { error: "Sesión vencida. Ingresá de nuevo." }); }
      return enviar(res, 200, await f(body ? JSON.parse(body) : {}, s, ip));
    } catch (e) {
      const st = e.status || (e.odoo ? 422 : 500); if (st === 500) console.error("error", req.method, url.pathname, e.message);
      if (e.odoo && /Access Denied|AccessDenied/i.test(e.message)) return enviar(res, 401, { error: "Tu contraseña de Odoo cambió. Ingresá de nuevo." });
      return enviar(res, st, { error: st === 500 ? "Error interno." : e.message });
    }
  }
  let p = path.normalize(path.join(PUB, url.pathname === "/" ? "index.html" : url.pathname));
  if (!p.startsWith(PUB) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) p = path.join(PUB, "index.html");
  res.writeHead(200, { ...SEG, "Content-Type": MIME[path.extname(p)] || "application/octet-stream", "Cache-Control": p.endsWith("sw.js") || p.endsWith(".html") ? "no-cache" : "public, max-age=300" });
  fs.createReadStream(p).pipe(res);
}).listen(PORT, () => console.log("inicio-obra escuchando en", PORT));
