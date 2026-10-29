const DEMO = new URLSearchParams(location.search).has("demo");
const api = await import(DEMO ? "./capa/mock.js" : "./capa/odoo.js");
let GUIA = null; const guia = async () => GUIA || (GUIA = await fetch("datos/guia.json").then((r) => r.json()).catch(() => ({ areas: {} })));
const $ = (s) => document.querySelector(s), app = $("#app");
const ses = () => JSON.parse(localStorage.getItem("io_sesion2") || "null");
const fmt = (d) => new Date(d).toLocaleString("es-AR", { weekday: "short", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", timeZone: "America/Argentina/Buenos_Aires" });
const bar = (p) => `<div class="bar"><i style="width:${p}%"></i></div>`;
const ESTADO = { carga: ["En carga", ""], completo: ["Espera CEO", "a"], aprobado: ["Aprobado", "v"], observado: ["Observado", "r"] };
const ROL = { gerente: "Gerente", ugeop: "UGEOP", secretaria: "Secretaría COO", coo: "COO", ceo: "CEO" };
if ("serviceWorker" in navigator && location.protocol !== "file:") navigator.serviceWorker.register("sw.js");
const nom = (db, id) => db.usuarios.find((x) => x.id === id)?.nombre || "";
const avance = (db, ot) => Math.round((100 * db.areas.filter((a) => api.areaCompleta(db, ot, a.id)).length) / db.areas.length);
const pctItems = (db, ot) => { const its = db.items.filter((i) => i.ot === ot && !db.tareas.find((t) => t.ot === ot && t.area_id === i.area_id).no_aplica), n = db.items.filter((i) => i.ot === ot).length; return Math.round((100 * (its.filter((i) => i.hecho).length + n - its.length)) / n); };

function encabezado(u) { $("#enc").innerHTML = `<div><b>Tecnología ARME</b><small>Inicio de obra${u ? " · " + u.nombre : ""}</small></div>${u ? '<a href="#/salir">Salir</a>' : ""}`; }
function tabs(u, on) { const t = [["#/", u.rol === "gerente" ? "Mis pendientes" : "Obras"]]; if (["coo", "secretaria"].includes(u.rol)) t.push(["#/usuarios", "Usuarios"]);
  return t.length > 1 ? `<nav class="tabs">${t.map(([h, l]) => `<a href="${h}" class="${h === on ? "on" : ""}">${l}</a>`).join("")}</nav>` : ""; }
async function ingresar() {
  encabezado(null);
  app.innerHTML = `<div class="logo"><img src="iconos/icon.svg" alt=""><h1>Inicio de obra</h1><div class="muted">Checklist del comité de inicio · sin reunión</div></div>
  <div class="card"><label class="muted">Usuario</label><input id="u" autocomplete="username" placeholder="tu usuario de Odoo (email)" autocapitalize="none" inputmode="email">
  <label class="muted">Contraseña</label><input id="c" type="password" placeholder="contraseña o API key de Odoo">
  <button class="btn" id="go">Ingresar</button><div class="err" id="e"></div></div>
  <p class="muted" style="text-align:center">Ingresá con tu mismo usuario y contraseña de Odoo.<br>Si usás Google o doble factor, generá una API key en Odoo › Mi perfil › Seguridad.${DEMO ? "<br><b>Modo demo · datos de ejemplo</b>" : ""}</p>`;
  $("#go").onclick = async () => { $("#go").disabled = true; try { const u = await api.ingresar($("#u").value.trim(), $("#c").value); localStorage.setItem("io_sesion2", JSON.stringify(u)); location.hash = "#/"; } catch (e) { $("#e").textContent = e.message; } $("#go").disabled = false; };
}
async function inicio(u) {
  const db = await api.cargar(); let html = tabs(u, "#/") + `<h2>${u.rol === "gerente" ? "Mis pendientes" : "Inicio de obra por OT"}</h2>`;
  for (const ot of db.obras) {
    const [et, ec] = ESTADO[ot.estado];
    if (u.rol === "gerente" || u.rol === "ugeop" && false) {
      for (const aid of u.areas) { const a = db.areas.find((x) => x.id === aid), t = db.tareas.find((x) => x.ot === ot.id && x.area_id === aid), its = db.items.filter((i) => i.ot === ot.id && i.area_id === aid);
        const pend = t.no_aplica ? 0 : its.filter((i) => !i.hecho).length, tarde = pend && new Date(t.vence) < new Date(), p = t.no_aplica ? 100 : Math.round((100 * (its.length - pend)) / its.length);
        html += `<div class="card"><a href="#/ot/${ot.id}/area/${aid}"><div class="row"><b>${ot.name}</b><span class="tag ${t.no_aplica ? "" : pend ? (tarde || t.observada ? "r" : "a") : "v"}">${t.no_aplica ? "No aplica" : t.observada && pend ? "Observado CEO" : pend ? pend + " pendientes" : "Completo"}</span></div>
        <div class="muted">${a.name} · vence ${fmt(t.vence)}${tarde ? " · <b style='color:#b42318'>vencido</b>" : ""}</div>${bar(p)}<div class="muted">Avance general de la OT: ${avance(db, ot.id)}% · ${et}</div></a></div>`; }
    } else {
      const comp = db.areas.filter((a) => api.areaCompleta(db, ot.id, a.id)).length;
      html += `<div class="card"><a href="#/ot/${ot.id}"><div class="row"><b>${ot.name}</b><span class="tag ${ec}">${et}</span></div><div class="muted">${comp}/${db.areas.length} áreas completas · ronda ${ot.ronda + 1}</div>${bar(avance(db, ot.id))}</a></div>`;
    }
  }
  app.innerHTML = html;
}
async function area(u, otId, aid) {
  const db = await api.cargar(), ot = db.obras.find((o) => o.id === otId), a = db.areas.find((x) => x.id === aid), t = db.tareas.find((x) => x.ot === otId && x.area_id === aid);
  const its = db.items.filter((i) => i.ot === otId && i.area_id === aid), mia = u.areas.includes(aid), p = t.no_aplica ? 100 : Math.round((100 * its.filter((i) => i.hecho).length) / its.length);
  const resp = db.usuarios.filter((x) => x.areas.includes(aid)).map((x) => x.nombre).join(", ");
  const g = (await guia()).areas[a.code] || { manual: "", items: [] }, gi = (i, k) => g.items.find((x) => x.item === i.name) || g.items[k];
  app.innerHTML = `<a href="#/${u.rol === "gerente" ? "" : "ot/" + otId}" class="muted">‹ Volver</a><h2>${ot.name}</h2>
  ${t.observada ? `<div class="card" style="border-left:4px solid #b42318"><b style="color:#b42318">Observado por el CEO</b><div>${t.obs_ceo}</div><div class="muted">Corregí y volvé a marcar los ítems.</div></div>` : ""}
  <div class="card"><div class="row"><b>${a.name}</b><span class="muted">${p}%</span></div>${bar(p)}<div class="muted">Vence ${fmt(t.vence)} (hs lun–sáb) · responsable: ${resp}</div>
   ${g.manual ? `<details class="guia"><summary>📘 Cómo completar esta área</summary><p>${g.manual}</p></details>` : ""}</div>
  <div class="card"><label class="row" style="justify-content:flex-start;gap:10px"><input type="checkbox" id="na" ${t.no_aplica ? "checked" : ""} ${mia ? "" : "disabled"} style="width:24px;height:24px"><b>No aplica a esta obra</b></label>
   ${t.no_aplica ? `<div class="muted">Motivo: ${t.motivo}</div><div class="muted">✔ ${nom(db, t.na_por)} · ${fmt(t.na_at)}</div>` : mia ? `<div id="nabox" hidden><textarea id="motivo" rows="2" placeholder="Motivo (obligatorio)"></textarea><button class="btn sec" id="naok">Confirmar «No aplica»</button></div>` : ""}</div>
  ${t.no_aplica ? "" : `<div class="card">${its.map((i, k) => `<div class="item"><input type="checkbox" data-i="${i.id}" ${i.hecho ? "checked" : ""} ${mia ? "" : "disabled"}>
   <div style="flex:1"><div>${i.name}</div>${gi(i, k) ? `<details class="info"><summary>ⓘ Qué significa</summary><div><b>Qué:</b> ${gi(i, k).que}</div><div><b>Adjunto:</b> ${gi(i, k).adjunto}</div><div><b>Quién:</b> ${gi(i, k).quien}</div><div><b>Cuándo:</b> ${gi(i, k).cuando}</div></details>` : ""}${i.adj ? `<span class="tag">Requiere adjunto</span>` : ""}${i.observado && !i.hecho ? `<span class="tag r">Reabierto por CEO</span>` : ""}
   ${i.adjuntos.map((f) => `<div class="adj">📎 ${f}</div>`).join("")}
   ${i.hecho ? `<div class="muted">✔ ${nom(db, i.hecho_por)} · ${fmt(i.hecho_at)}${new Date(i.hecho_at) > new Date(i.vence) ? ' <span class="tag r">fuera de término</span>' : ""}</div>` : ""}
   ${mia && !i.hecho && i.adj ? `<label class="adj">＋ Adjuntar foto o PDF<input type="file" data-f="${i.id}" accept="image/*,application/pdf" capture="environment" hidden></label>` : ""}</div></div>`).join("")}</div>`}
  <div class="err" id="e"></div>${mia ? "" : '<p class="muted">Solo lectura: cada gerente marca lo suyo (registro indelegable, punto 2.1).</p>'}`;
  const err = (e) => ($("#e").textContent = e.message), re = () => area(u, otId, aid);
  app.querySelectorAll("[data-i]").forEach((c) => (c.onchange = async () => { try { await api.marcar(u, +c.dataset.i, c.checked); re(); } catch (e) { c.checked = !c.checked; err(e); } }));
  app.querySelectorAll("[data-f]").forEach((f) => (f.onchange = async () => { if (f.files[0]) { try { await api.marcar(u, +f.dataset.f, false, DEMO ? f.files[0].name : f.files[0]); re(); } catch (e) { err(e); } } }));
  const na = $("#na"); if (na && mia) na.onchange = async () => { if (t.no_aplica) { await api.noAplica(u, otId, aid, false, ""); re(); } else $("#nabox").hidden = !na.checked; };
  const ok = $("#naok"); if (ok) ok.onclick = async () => { try { await api.noAplica(u, otId, aid, true, $("#motivo").value); re(); } catch (e) { err(e); } };
}
async function consolidado(u, otId) {
  const db = await api.cargar(), ot = db.obras.find((o) => o.id === otId), [et, ec] = ESTADO[ot.estado];
  const filas = db.areas.map((a) => { const t = db.tareas.find((x) => x.ot === otId && x.area_id === a.id), its = db.items.filter((i) => i.ot === otId && i.area_id === a.id);
    const p = t.no_aplica ? 100 : Math.round((100 * its.filter((i) => i.hecho).length) / its.length), tarde = p < 100 && new Date(t.vence) < new Date();
    const tag = t.no_aplica ? ["No aplica", ""] : p === 100 ? ["Completo", "v"] : t.observada ? ["Observado", "r"] : tarde ? ["Vencido", "r"] : [p + "%", "a"];
    return `<a href="#/ot/${otId}/area/${a.id}"><div class="item" style="display:block"><div class="row"><span>${a.name}</span><span class="tag ${tag[1]}">${tag[0]}</span></div>${bar(p)}</div></a>`; }).join("");
  const comp = db.areas.filter((a) => api.areaCompleta(db, otId, a.id)).length, rondas = db.rondas.filter((r) => r.ot === otId);
  app.innerHTML = `<a href="#/" class="muted">‹ Volver</a><h2>${ot.name}</h2><div class="card"><div class="row"><b>Checklist consolidado</b><span class="tag ${ec}">${et}</span></div>${bar(avance(db, otId))}
  <div class="muted">${comp}/${db.areas.length} áreas completas · ítems ${pctItems(db, otId)}% · ronda ${ot.ronda + (ot.estado === "aprobado" ? 0 : 1)}</div></div>
  ${rondas.length ? `<div class="card"><b>Historial CEO</b>${rondas.map((r) => `<div class="item" style="display:block"><span class="tag ${r.res === "aprobado" ? "v" : "r"}">Ronda ${r.n} · ${r.res === "aprobado" ? "Aprobado" : "Observado"}</span> <span class="muted">${fmt(r.at)}</span>${r.obs ? `<div>${r.obs}</div>` : ""}${r.areas.length ? `<div class="muted">Reabre: ${r.areas.map((x) => db.areas.find((a) => a.id === x).name).join(", ")}</div>` : ""}</div>`).join("")}</div>` : ""}
  <div class="card">${filas}</div>${u.rol === "ceo" && ot.estado === "completo" ? `<a class="btn" style="text-align:center;text-decoration:none" href="#/aprobar/${otId}">Revisar y aprobar</a>` : ""}`;
}
async function aprobar(u, otId) {
  const db = await api.cargar(), ot = db.obras.find((o) => o.id === otId), ok = ot.estado === "completo";
  const val = [["Contrato o FCI firmado, garantías, pólizas y permisos", "LEG"], ["Presupuesto aprobado y alcance", "PRE"], ["Gantt único y calendario de cobros", "UGE"], ["Recursos humanos y materiales asignados", "RRH"], ["Plan logístico", "LOG"], ["Condición de seguridad (FRO y habilitación)", "HYS"]];
  const est = (c) => api.areaCompleta(db, otId, db.areas.find((x) => x.code === c).id);
  app.innerHTML = `<a href="#/ot/${otId}" class="muted">‹ Volver</a><h2>Aprobación formal del inicio</h2><div class="card"><b>${ot.name}</b>${bar(avance(db, otId))}<div class="muted">Ronda ${ot.ronda + 1} · ${ESTADO[ot.estado][0]}</div></div>
  <div class="card">${val.map(([t, c]) => `<div class="item"><span>${est(c) ? "✅" : "⏳"}</span><span>${t}</span></div>`).join("")}</div>
  ${!ok ? `<div class="card muted">Se habilita cuando las 11 áreas estén completas o marquen «No aplica».</div>` : `<div class="card"><label class="muted">Observaciones (obligatorias para devolver)</label><textarea id="o" rows="3"></textarea>
  <button class="btn ok" id="ap">Aprobar inicio de obra</button><button class="btn sec" id="dv">Devolver como Observado…</button>
  <div id="dvbox" hidden><div class="muted" style="margin-top:10px">Áreas a reabrir:</div>${db.areas.map((a) => `<label class="row" style="justify-content:flex-start;gap:8px;padding:4px 0"><input type="checkbox" data-a="${a.id}" style="width:20px;height:20px">${a.name}</label>`).join("")}
  <button class="btn" id="dvok" style="background:#b42318">Confirmar devolución</button></div>
  <div class="err" id="e"></div><div class="muted">Queda registrado con tu usuario, fecha y hora. Reemplaza la firma del acta de reunión.</div></div>`}`;
  if (!ok) return;
  $("#ap").onclick = async () => { await api.aprobar(u, otId, $("#o").value); location.hash = "#/ot/" + otId; };
  $("#dv").onclick = () => ($("#dvbox").hidden = false);
  $("#dvok").onclick = async () => { try { const n = await api.observar(u, otId, $("#o").value, [...app.querySelectorAll("[data-a]:checked")].map((x) => +x.dataset.a));
    app.innerHTML = `<div class="card"><span class="tag r">Devuelto como Observado</span><p>Se reabrieron las áreas elegidas y se avisó a: <b>${n.join(", ")}</b>.</p><a class="btn sec" style="text-align:center;text-decoration:none" href="#/ot/${otId}">Ver consolidado</a></div>`; } catch (e) { $("#e").textContent = e.message; } };
}
async function usuarios(u) {
  const db = await api.cargar(), an = (ids) => ids.map((i) => db.areas.find((a) => a.id === i).name).join(", ") || "—";
  app.innerHTML = tabs(u, "#/usuarios") + `<h2>Usuarios de la app</h2><div class="muted" style="margin-bottom:10px">Se administran en Odoo › Proyecto › Usuarios de la app. Cada uno ingresa con su propio usuario de Odoo; la app no guarda contraseñas.</div>
  ${db.usuarios.map((x) => `<div class="card"><div class="row"><b>${x.nombre}</b><span class="tag ${x.activo ? "v" : ""}">${x.activo ? "Activo" : "Inactivo"}</span></div>
   <div class="muted">${x.login} · ${ROL[x.rol]} · ${an(x.areas)}</div><div><span class="tag">${x.odoo ? "Con usuario Odoo" : "Sin usuario Odoo"}</span></div>
   <label class="row" style="justify-content:flex-start;gap:8px;margin-top:6px"><input type="checkbox" data-act="${x.id}" ${x.activo ? "checked" : ""} style="width:20px;height:20px"> Activo</label></div>`).join("")}`;
  app.querySelectorAll("[data-act]").forEach((c) => (c.onchange = async () => { await api.guardarUsuario(u, +c.dataset.act, { activo: c.checked }); usuarios(u); }));
}
async function ruta() { try { await ruta2(); } catch (e) { app.innerHTML = `<div class="card err">${e.message}</div>`; } }
async function ruta2() {
  const u = ses(), h = location.hash || "#/";
  if (h === "#/salir") { localStorage.removeItem("io_sesion2"); location.hash = "#/ingresar"; return; }
  if (!u || h === "#/ingresar") return ingresar();
  encabezado(u); let m;
  if ((m = h.match(/^#\/ot\/(\d+)\/area\/(\d+)/))) return area(u, +m[1], +m[2]);
  if ((m = h.match(/^#\/ot\/(\d+)/))) return consolidado(u, +m[1]);
  if ((m = h.match(/^#\/aprobar\/(\d+)/))) return aprobar(u, +m[1]);
  if (h === "#/usuarios") return usuarios(u);
  return inicio(u);
}
addEventListener("hashchange", ruta); ruta();
