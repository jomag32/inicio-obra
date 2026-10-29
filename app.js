import * as api from "./api/mock.js";
const $ = (s) => document.querySelector(s), app = $("#app");
const ses = () => JSON.parse(localStorage.getItem("io_sesion") || "null");
const fmt = (d) => new Date(d).toLocaleString("es-AR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", timeZone: "America/Argentina/Buenos_Aires" });
const pct = (a) => (a.length ? Math.round((100 * a.filter((i) => i.hecho).length) / a.length) : 0);
const bar = (p) => `<div class="bar"><i style="width:${p}%"></i></div>`;
if ("serviceWorker" in navigator && location.protocol !== "file:") navigator.serviceWorker.register("sw.js");

function encabezado(u) {
  $("#enc").innerHTML = `<div><b>Tecnología ARME</b><small>Inicio de obra${u ? " · " + u.nombre : ""}</small></div>${u ? '<a href="#/salir">Salir</a>' : ""}`;
}
async function ingresar() {
  const db = await api.cargar(); encabezado(null);
  app.innerHTML = `<div class="logo"><img src="iconos/icon.svg" alt=""><h1>Inicio de obra</h1><div class="muted">Checklist del comité de inicio · sin reunión</div></div>
  <div class="card"><label class="muted">Quién sos</label><select id="u">${db.usuarios.map((u) => `<option value="${u.id}">${u.nombre}</option>`).join("")}</select>
  <label class="muted">Contraseña</label><input id="c" type="password" placeholder="Tu contraseña" value="demo">
  <button class="btn" id="go">Ingresar</button><div class="err" id="e"></div></div>
  <p class="muted" style="text-align:center">Prototipo de prueba · datos de ejemplo, no conecta con Odoo</p>`;
  $("#go").onclick = async () => { try { const u = await api.ingresar(+$("#u").value, $("#c").value); localStorage.setItem("io_sesion", JSON.stringify(u)); location.hash = "#/"; } catch (e) { $("#e").textContent = e.message; } };
}
async function inicio(u) {
  const db = await api.cargar();
  const tabs = `<nav class="tabs"><a href="#/" class="on">${u.rol === "gerente" ? "Mis pendientes" : "Obras"}</a></nav>`;
  let html = `<h2>${u.rol === "gerente" ? "Mis pendientes" : "Inicio de obra por OT"}</h2>`;
  for (const ot of db.obras) {
    const todos = db.items.filter((i) => i.ot === ot.id), ap = db.aprob[ot.id];
    if (u.rol === "gerente") {
      const area = db.areas.find((a) => a.code === u.area), mios = todos.filter((i) => i.area_id === area.id), pend = mios.filter((i) => !i.hecho);
      const vence = mios[0].vence, tarde = pend.length && new Date(vence) < new Date();
      html += `<div class="card"><a href="#/ot/${ot.id}/area/${area.id}"><div class="row"><b>${ot.name}</b><span class="tag ${pend.length ? (tarde ? "r" : "a") : "v"}">${pend.length ? pend.length + " pendientes" : "Completo"}</span></div>
      <div class="muted">${area.name} · vence ${fmt(vence)}${tarde ? " · <b style='color:#b42318'>vencido</b>" : ""}</div>${bar(pct(mios))}
      <div class="muted">Avance general de la OT: ${pct(todos)}%</div></a></div>`;
    } else {
      const comp = db.areas.filter((a) => todos.filter((i) => i.area_id === a.id).every((i) => i.hecho)).length;
      html += `<div class="card"><a href="#/ot/${ot.id}"><div class="row"><b>${ot.name}</b><span class="tag ${ap ? "v" : comp === 11 ? "a" : ""}">${ap ? "Aprobado" : comp === 11 ? "Espera CEO" : "En carga"}</span></div>
      <div class="muted">${comp}/11 áreas completas · ${pct(todos)}%</div>${bar(pct(todos))}</a></div>`;
    }
  }
  app.innerHTML = tabs + html;
}
async function area(u, otId, aid) {
  const db = await api.cargar(), ot = db.obras.find((o) => o.id === otId), a = db.areas.find((x) => x.id === aid);
  const its = db.items.filter((i) => i.ot === otId && i.area_id === aid), mia = a.user_id === u.id;
  const nom = (id) => db.usuarios.find((x) => x.id === id)?.nombre || "";
  app.innerHTML = `<a href="#/${u.rol === "gerente" ? "" : "ot/" + otId}" class="muted">‹ Volver</a><h2>${ot.name}</h2>
  <div class="card"><div class="row"><b>${a.name}</b><span class="muted">${pct(its)}%</span></div>${bar(pct(its))}<div class="muted">Vence ${fmt(its[0].vence)} · responsable: ${nom(a.user_id)}</div></div>
  <div class="card">${its.map((i) => `<div class="item"><input type="checkbox" data-i="${i.id}" ${i.hecho ? "checked" : ""} ${mia ? "" : "disabled"}>
   <div style="flex:1"><div>${i.name}</div>${i.adj ? `<span class="tag">Requiere adjunto</span>` : ""}
   ${i.adjuntos.map((f) => `<div class="adj">📎 ${f}</div>`).join("")}
   ${i.hecho ? `<div class="muted">✔ ${nom(i.hecho_por)} · ${fmt(i.hecho_at)}${new Date(i.hecho_at) > new Date(i.vence) ? ' <span class="tag r">fuera de término</span>' : ""}</div>` : ""}
   ${mia && !i.hecho && i.adj ? `<label class="adj">＋ Adjuntar foto o PDF<input type="file" data-f="${i.id}" accept="image/*,application/pdf" capture="environment" hidden></label>` : ""}</div></div>`).join("")}
  <div class="err" id="e"></div></div>${mia ? "" : '<p class="muted">Solo lectura: cada gerente marca lo suyo (registro indelegable, punto 2.1).</p>'}`;
  app.querySelectorAll("[data-i]").forEach((c) => (c.onchange = async () => { try { await api.marcar(u, +c.dataset.i, c.checked); area(u, otId, aid); } catch (e) { c.checked = !c.checked; $("#e").textContent = e.message; } }));
  app.querySelectorAll("[data-f]").forEach((f) => (f.onchange = async () => { if (f.files[0]) { await api.marcar(u, +f.dataset.f, false, f.files[0].name); area(u, otId, aid); } }));
}
async function consolidado(u, otId) {
  const db = await api.cargar(), ot = db.obras.find((o) => o.id === otId), todos = db.items.filter((i) => i.ot === otId), ap = db.aprob[otId];
  const filas = db.areas.map((a) => { const its = todos.filter((i) => i.area_id === a.id), p = pct(its), tarde = p < 100 && new Date(its[0].vence) < new Date();
    return `<a href="#/ot/${otId}/area/${a.id}"><div class="item" style="display:block"><div class="row"><span>${a.name}</span><span class="tag ${p === 100 ? "v" : tarde ? "r" : "a"}">${p === 100 ? "Completo" : tarde ? "Vencido" : p + "%"}</span></div>${bar(p)}</div></a>`; }).join("");
  const comp = db.areas.filter((a) => todos.filter((i) => i.area_id === a.id).every((i) => i.hecho)).length;
  app.innerHTML = `<a href="#/" class="muted">‹ Volver</a><h2>${ot.name}</h2><div class="card"><div class="row"><b>Checklist consolidado</b><b>${pct(todos)}%</b></div>${bar(pct(todos))}
  <div class="muted">${comp}/11 áreas completas · ${todos.filter((i) => i.hecho).length}/${todos.length} ítems</div></div><div class="card">${filas}</div>
  ${ap ? `<div class="card"><span class="tag v">Aprobado</span> por ${db.usuarios.find((x) => x.id === ap.por).nombre} · ${fmt(ap.at)}</div>` : u.rol === "ceo" ? `<a class="btn" style="text-align:center;text-decoration:none" href="#/aprobar/${otId}">Ir a aprobación</a>` : ""}`;
}
async function aprobar(u, otId) {
  const db = await api.cargar(), ot = db.obras.find((o) => o.id === otId), todos = db.items.filter((i) => i.ot === otId), ok = todos.every((i) => i.hecho), ap = db.aprob[otId];
  const val = [["Contrato o FCI firmado, garantías, pólizas y permisos", "LEG"], ["Presupuesto aprobado y alcance", "PRE"], ["Gantt único y calendario de cobros", "UGE"], ["Recursos humanos y materiales asignados", "RRH"], ["Plan logístico", "LOG"], ["Condición de seguridad (FRO y habilitación)", "HYS"]];
  const est = (c) => { const a = db.areas.find((x) => x.code === c); return todos.filter((i) => i.area_id === a.id).every((i) => i.hecho); };
  app.innerHTML = `<a href="#/ot/${otId}" class="muted">‹ Volver</a><h2>Aprobación formal del inicio</h2><div class="card"><b>${ot.name}</b>${bar(pct(todos))}<div class="muted">${pct(todos)}% · 11 áreas</div></div>
  <div class="card">${val.map(([t, c]) => `<div class="item"><span>${est(c) ? "✅" : "⏳"}</span><span>${t}</span></div>`).join("")}</div>
  ${ap ? `<div class="card"><span class="tag v">Aprobado</span> ${fmt(ap.at)}</div>` : `<div class="card"><label class="muted">Observaciones (opcional)</label><textarea id="o" rows="2"></textarea>
  <button class="btn ok" id="ap" ${ok ? "" : "disabled style='opacity:.5'"}>Aprobar inicio de obra</button><div class="muted">${ok ? "Queda registrado con tu usuario, fecha y hora. Reemplaza la firma del acta de reunión." : "Se habilita cuando las 11 áreas completen su checklist."}</div></div>`}`;
  const b = $("#ap"); if (b) b.onclick = async () => { await api.aprobar(u, otId, $("#o").value); aprobar(u, otId); };
}
async function ruta() {
  const u = ses(), h = location.hash || "#/";
  if (h === "#/salir") { localStorage.removeItem("io_sesion"); location.hash = "#/ingresar"; return; }
  if (!u || h === "#/ingresar") return ingresar();
  encabezado(u); let m;
  if ((m = h.match(/^#\/ot\/(\d+)\/area\/(\d+)/))) return area(u, +m[1], +m[2]);
  if ((m = h.match(/^#\/ot\/(\d+)/))) return consolidado(u, +m[1]);
  if ((m = h.match(/^#\/aprobar\/(\d+)/))) return aprobar(u, +m[1]);
  return inicio(u);
}
addEventListener("hashchange", ruta); ruta();
