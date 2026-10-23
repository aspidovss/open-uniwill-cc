"use strict";
/* Control Center for Linux — web UI */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const h = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) if (k !== null && k !== undefined) e.append(k.nodeType ? k : String(k));
  return e;
};

// ---------------------------------------------------------------- token / api
(function initToken() {
  const m = location.hash.match(/token=([\w-]+)/);
  if (m) { try { sessionStorage.setItem("uwcc-token", m[1]); } catch (_) {} history.replaceState(null, "", location.pathname); }
})();
const TOKEN = (() => { try { return sessionStorage.getItem("uwcc-token") || ""; } catch (_) { return ""; } })();

async function api(path, body, method) {
  const opt = { method: method || (body ? "POST" : "GET"), headers: { "X-UWCC-Token": TOKEN } };
  if (body) { opt.body = JSON.stringify(body); opt.headers["Content-Type"] = "application/json"; }
  const r = await fetch("/api/" + path, opt);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
function toast(msg, err) {
  const t = h("div", { class: "tst" + (err ? " err" : "") }, msg);
  $("#toast").append(t); setTimeout(() => t.remove(), 3500);
}
let osdTimer;
function osd(text) {
  const o = $("#osd"); o.textContent = text; o.classList.add("show");
  clearTimeout(osdTimer); osdTimer = setTimeout(() => o.classList.remove("show"), 1600);
}
async function act(fn, ok) {
  try { await fn(); if (ok) toast(ok); await refresh(); }
  catch (e) { toast(e.message.includes("software") ? t("This effect is not available for this keyboard") : t("Error: {0}", errText(e.message)), true); }
}

function errText(m) { return t(m); }

// ---------------------------------------------------------------- language
function setLang(l, save) {
  LANG = l === "ru" ? "ru" : "en";
  try { localStorage.setItem("uwcc-lang", LANG); } catch (_) {}
  document.documentElement.lang = LANG;
  i18nStatic();
  $$("#lang-seg button").forEach(b => b.classList.toggle("on", b.dataset.lang === LANG));
  if (save) api("setting", { key: "lang", value: LANG }).catch(() => {});
  if (S) render();
  if (lastMonitor) onMonitor(lastMonitor);
  paintConn();
}
$$("#lang-seg button").forEach(b => b.addEventListener("click", () => setLang(b.dataset.lang, true)));

// ---------------------------------------------------------------- state
let S = null;
const MODES = [
  { id: 0, name: "Office mode", osd: "Office", glyph: "☾", desc: "Quiet and calm. Low fan noise." },
  { id: 1, name: "Gaming mode", osd: "Gaming", glyph: "◆", desc: "Balanced performance for games and work." },
  { id: 2, name: "Turbo mode", osd: "Turbo", glyph: "⚡", desc: "Best performance for gaming." },
  { id: 3, name: "Custom mode", osd: "Custom", glyph: "✎", desc: "Your own power limits and fan curves in five slots." },
];
const CML_TABLES = ["M1T1", "M1T2", "M1T3", "M2T1", "M2T2", "M2T3"];
const MODE_OF_PREFIX = { 1: "Gaming", 2: "Office", 3: "Turbo", 4: "Custom" };
function isStd() { return S && S.power && S.power.manager === "std"; }
function slotName(p, i) { const n = p && p.CustomizeName; return n && !/^\d+$/.test(n) ? n : String(i); }
function tableList() {
  if (!isStd()) return CML_TABLES;
  const order = ["Mode1_Profile1", "Mode1_Profile2", "Mode2_Profile1", "Mode2_Profile2", "Mode3_Profile1", "Mode3_Profile2",
    "Mode4_Profile1", "Mode4_Profile2", "Mode4_Profile3", "Mode4_Profile4", "Mode4_Profile5"];
  return order.map(n => S.profiles[n]?.FAN?.TableName).filter((x, i, a) => x && a.indexOf(x) === i && (!S.power.turbo_support ? !x.startsWith("M3") : true));
}
function tableLabel(n) {
  if (!n || n.length < 4) return n;
  const m = n[1], i = +n[3];
  if (m === "4" && isStd()) return `${t("Custom")} · ${slotName(S.profiles["Mode4_Profile" + i], i)}`;
  return `${t(MODE_OF_PREFIX[m] || "?")} · ${i}`;
}
const TABLE_LABEL = new Proxy({}, { get: (_, k) => typeof k === "string" ? tableLabel(k) : undefined });
const EFFECT_NAME = {
  Single: "Single colour", Breathing: "Breathing", Wave: "Wave", Reactive: "Reactive", Rainbow: "Rainbow", Ripple: "Ripple",
  Raindrop: "Raindrop", Neon: "Neon", Marquee: "Marquee", Stack: "Stack", Impact: "Impact", Spark: "Spark",
  Aurora: "Aurora", Music: "Music mode", UserMode: "User mode", Gaming: "Gaming mode", Flash: "Flash",
  Mix: "Mix", RippleO: "Ripple O", Alphabet: "Alphabet", StarHitting: "Star hitting", StarSpark: "Star spark",
  Thinking: "Pulse", ColorfulWave: "Colour wave",
};

async function refresh() {
  S = await api("state");
  if (S.settings.lang && S.settings.lang !== LANG) setLang(S.settings.lang, false);
  render();
}

// ---------------------------------------------------------------- navigation
$$("#nav a").forEach(a => a.addEventListener("click", () => {
  $$("#nav a").forEach(x => x.classList.toggle("active", x === a));
  $$(".page").forEach(p => p.classList.toggle("active", p.id === "page-" + a.dataset.page));
  try { localStorage.setItem("uwcc-page", a.dataset.page); } catch (_) {}
}));
try { const p = localStorage.getItem("uwcc-page"); if (p) $(`#nav a[data-page="${p}"]`)?.click(); } catch (_) {}

// ---------------------------------------------------------------- render all
function render() {
  if (!S) return;
  const mode = S.power.mode;
  const pill = $("#modepill"); pill.textContent = MODES[mode] ? t(MODES[mode].name) : "—"; pill.className = "modepill m" + mode;
  $("#brand-sub").textContent = S.platform.project_name;
  renderModes(); renderFanPage(); renderLiquid(); renderLight(); renderBattery(); renderSwitches(); renderBinding(); renderInfo(); renderAuto();
  renderHistSeg(); drawHistory();
}

// ---------------------------------------------------------------- monitor
const hist = { cpu: [], gpu: [] };
function gauge(label, value, unit, max, sub, color) {
  const v = value == null ? 0 : value, frac = Math.max(0, Math.min(1, v / max));
  const R = 56, C = Math.PI * R, off = C * (1 - frac);
  return h("div", { class: "card gauge" },
    svgEl(`<svg viewBox="0 0 150 90"><path d="M19 80 A56 56 0 0 1 131 80" fill="none" stroke="#1d252c" stroke-width="12" stroke-linecap="round"/>` +
      `<path d="M19 80 A56 56 0 0 1 131 80" fill="none" stroke="${color || "var(--acc)"}" stroke-width="12" stroke-linecap="round" stroke-dasharray="${C}" stroke-dashoffset="${off}" style="transition:stroke-dashoffset .6s"/></svg>`),
    h("div", { class: "v" }, value == null ? "—" : `${value}${unit}`), h("div", { class: "l" }, label), h("div", { class: "s" }, sub || ""));
}
function svgEl(markup) { const d = document.createElement("div"); d.innerHTML = markup; return d.firstChild; }
function onMonitor(m) {
  const g = $("#gauges"); g.innerHTML = "";
  g.append(gauge(t("CPU temperature"), m.cpu.temp, "°C", 100, m.cpu.mhz ? `${m.cpu.mhz} ${t("MHz")}` : ""));
  g.append(gauge(t("CPU load"), m.cpu.usage, "%", 100, m.cpu.power_w != null ? `${m.cpu.power_w} ${t("W")}` : ""));
  if (m.gpu && m.gpu.asleep) {
    g.append(gauge(t("GPU"), null, "", 100, t("asleep (saving power)"), "var(--gpu)"));
    g.append(gauge(t("Memory"), m.memory.usage, "%", 100, `${(m.memory.used_mb / 1024).toFixed(1)} / ${(m.memory.total_mb / 1024).toFixed(1)} ${t("GB")}`));
  } else if (m.gpu) {
    g.append(gauge(t("GPU temperature"), m.gpu.temp, "°C", 100, m.gpu.core_mhz ? `${m.gpu.core_mhz} ${t("MHz")}` : "", "var(--gpu)"));
    g.append(gauge(t("GPU load"), m.gpu.usage, "%", 100, m.gpu.power_w ? `${m.gpu.power_w} ${t("W")}` : "", "var(--gpu)"));
  } else {
    g.append(gauge(t("CPU fan"), m.fans.cpu_duty, "%", 100, `${m.fans.cpu_rpm} ${t("rpm")}`));
    g.append(gauge(t("Memory"), m.memory.usage, "%", 100, `${(m.memory.used_mb / 1024).toFixed(1)} / ${(m.memory.total_mb / 1024).toFixed(1)} ${t("GB")}`));
  }
  const fb = $("#fan-bars"); fb.innerHTML = "";
  const bar = (cls, name, duty, rpm) => h("div", { class: "bar " + cls },
    h("div", { class: "top" }, h("span", {}, name), h("span", { class: "muted" }, `${duty}% · ${rpm} ${t("rpm")}`)),
    h("div", { class: "track" }, h("div", { class: "fill", style: `width:${Math.min(100, duty)}%` })));
  fb.append(bar("cpu", t("Processor fan"), m.fans.cpu_duty, m.fans.cpu_rpm));
  if (m.fans.gpu_duty != null) fb.append(bar("gpu", t("Graphics card fan"), m.fans.gpu_duty, m.fans.gpu_rpm));
  fb.append(h("p", { class: "muted tiny" }, S ? `${t("Active table:")} ${TABLE_LABEL[S.power.current_table] || "—"}${S.power.fan_boost ? " · " + t("Fan Boost") : ""}` : ""));
  if (m !== lastMonitor) {
    hist.cpu.push(m.cpu.temp ?? null); hist.gpu.push(m.gpu?.temp ?? null);
    for (const k of ["cpu", "gpu"]) if (hist[k].length > 120) hist[k].shift();
  }
  drawHist();
  $("#st-mem").innerHTML = ""; $("#st-mem").append(h("h3", {}, t("Memory")), h("div", { class: "big" }, `${m.memory.usage}%`), h("div", { class: "sub" }, t("{0} of {1} GB", (m.memory.used_mb / 1024).toFixed(1), (m.memory.total_mb / 1024).toFixed(1))));
  $("#st-net").innerHTML = ""; $("#st-net").append(h("h3", {}, t("Network")), h("div", { class: "big" }, `↓ ${fmtRate(m.net.down_kbs)}`), h("div", { class: "sub" }, `↑ ${fmtRate(m.net.up_kbs)}`));
  const b = m.battery; $("#st-bat").innerHTML = "";
  $("#st-bat").append(h("h3", {}, t("Battery")), h("div", { class: "big" }, b.present ? `${b.percent}%` : t("none")),
    h("div", { class: "sub" }, b.present ? `${batStatus(b.status)}${b.remaining_min ? " · " + t("{0} h {1} min", Math.floor(b.remaining_min / 60), b.remaining_min % 60) : ""}${m.ac ? " · " + t("on AC") : ""}` : ""));
  lastMonitor = m; updateBatStats();
}
let lastMonitor = null;
function fmtRate(k) { return k > 1024 ? `${(k / 1024).toFixed(1)} ${t("MB/s")}` : `${k} ${t("KB/s")}`; }
function batStatus(s) { return { Charging: t("Charging"), Discharging: t("Discharging"), Full: t("Fully charged"), "Not charging": t("Not charging") }[s] || s || ""; }
function drawHist() {
  const svg = $("#temp-chart"), W = 400, H = 140;
  const line = (arr, color) => {
    const pts = arr.map((v, i) => v == null ? null : `${(i / 119) * W},${H - (v / 100) * H}`).filter(Boolean);
    return pts.length > 1 ? `<polyline points="${pts.join(" ")}" fill="none" stroke="${color}" stroke-width="2"/>` : "";
  };
  let grid = ""; for (const t of [25, 50, 75]) grid += `<line x1="0" x2="${W}" y1="${H - t / 100 * H}" y2="${H - t / 100 * H}" stroke="#1f2830"/><text x="4" y="${H - t / 100 * H - 3}" fill="#55636e" font-size="9">${t}°</text>`;
  svg.innerHTML = grid + line(hist.cpu, "var(--cpu)") + line(hist.gpu, "var(--gpu)");
}

// ---------------------------------------------------------------- modes
function fanDisabledNote(el) {
  el.innerHTML = "";
  el.append(h("div", { class: "card warn" }, h("h3", {}, t("Mode control is unavailable")),
    h("p", { class: "muted" }, t("This laptop's controller does not report RamFan 1.5 support, and the original software uses a different algorithm on such machines. To avoid writing wrong values to the EC, modes and fan curves are disabled. Monitoring, lighting and switches work."))));
}
function renderModes() {
  const box = $("#mode-cards"); box.innerHTML = "";
  if (!S.platform.fan_control) { fanDisabledNote(box); box.style.display = "block"; return; }
  box.style.display = "";
  const modes = MODES.filter(m => m.id !== 3 || S.power.custom_support);
  box.classList.toggle("four", modes.length === 4);
  for (const m of modes) {
    const dis = m.id === 2 && !S.power.turbo_support;
    box.append(h("div", { class: `mode${S.power.mode === m.id ? " on" : ""}${dis ? " dis" : ""}`, onclick: () => act(() => api("mode", { mode: m.id }), t(m.name)) },
      h("span", { class: "badge" }, t("Active")), h("div", { class: "glyph" }, m.glyph), h("h2", {}, t(m.name)), h("p", {}, dis ? t("Not supported by this laptop") : t(m.desc))));
  }
  const mode = S.power.mode;
  const seg = $("#profile-seg"); seg.innerHTML = "";
  const key = { 0: "office", 1: "gaming", 2: "turbo", 3: "custom" }[mode];
  const idx = S.power.profile_index[key];
  $("#profile-editor").classList.toggle("hidden", !isStd());
  if (isStd()) {
    const n = S.power.slots[key];
    $("#profile-hint").textContent = mode === 3 ? t("Five slots with your own power limits and fan curves. In this mode the Fn mode key steps through the slots.")
      : t("Each profile has its own fan curve and power limits.");
    for (let i = 0; i < n; i++) {
      const pn = `Mode${{ 1: 1, 0: 2, 2: 3, 3: 4 }[mode]}_Profile${i + 1}`;
      const label = mode === 3 ? slotName(S.profiles[pn], i + 1) : t("Profile {0}", i + 1);
      seg.append(h("button", { class: i === idx ? "on" : "", onclick: () => act(() => api("profile", { mode, index: i }), label) }, label));
    }
    $("#profile-info").innerHTML = "";
    renderProfileEditor();
    $("#fanboost").checked = S.power.fan_boost;
    return;
  }
  if (mode === 2) {
    $("#profile-hint").textContent = t("Turbo mode uses the fan table of the previous mode; performance is set by the controller.");
  } else {
    $("#profile-hint").textContent = t("Each profile has its own fan curve and power limits.");
    for (let i = 0; i < 3; i++) seg.append(h("button", { class: i === idx ? "on" : "", onclick: () => act(() => api("profile", { mode, index: i }), t("Profile {0}", i + 1)) }, t("Profile {0}", i + 1)));
  }
  const info = $("#profile-info"); info.innerHTML = "";
  const pname = mode === 2 ? null : `Mode${mode === 1 ? 1 : 2}_Profile${idx + 1}`;
  const p = pname && S.profiles[pname];
  const kpi = (k, v) => h("div", { class: "kpi" }, h("div", { class: "k" }, k), h("div", { class: "v" }, v));
  if (p) {
    const c = p.CPU;
    info.append(kpi(t("Fan table"), TABLE_LABEL[p.FAN.TableName] || p.FAN.TableName),
      kpi(t("PL1 / PL2 (AC)"), c.PL1_Enabled || c.PL2_Enabled ? `${c.PL1_Enabled ? c.PL1 : "—"} / ${c.PL2_Enabled ? c.PL2 : "—"} ${t("W")}` : t("EC default")),
      kpi(t("PL1 / PL2 (battery)"), c.PL1_dc_Enabled || c.PL2_dc_Enabled ? `${c.PL1_dc_Enabled ? c.PL1_dc : "—"} / ${c.PL2_dc_Enabled ? c.PL2_dc : "—"} ${t("W")}` : t("EC default")),
      kpi(t("Fan protection"), p.FAN.SkipSafetyAbnormalProtection ? t("check skipped") : t("enabled")));
    if (S.platform.nv_gpu) info.append(kpi("cTGP", p.GPU.ConfigurableTGPSwitch ? `${p.GPU.ConfigurableTGPTarget} ${t("W")}` : t("off")), kpi("Dynamic Boost", p.GPU.DynamicBoostSwitch ? `${p.GPU.DynamicBoost} ${t("W")}` : t("off")));
  }
  const d = S.power.pl_default?.[{ 0: "office", 1: "gaming", 2: "turbo" }[mode]];
  if (d) info.append(kpi(t("Controller factory PL"), `${d.PL1} / ${d.PL2} / ${d.PL4} ${t("W")}`));
  $("#fanboost").checked = S.power.fan_boost;
}
// ---------------------------------------------------------------- profile editor (RamFan1p5 manager)
let pe = null;
function renderProfileEditor() {
  const name = S.power.current_profile, prof = S.profiles[name], L = S.power.limits || {};
  if (!prof) return;
  if (pe && pe.Name === name && $("#pe-rows").contains(document.activeElement)) return;   // user is editing
  if (!pe || pe.Name !== name) pe = JSON.parse(JSON.stringify(prof));
  const custom = name.startsWith("Mode4");
  $("#pe-title").textContent = custom ? t("Custom slot: {0}", slotName(prof, +name.slice(-1))) : t("Profile settings: {0}", tableLabel(prof.FAN.TableName));
  $("#pe-note").textContent = t("The values are applied on AC power; on battery the controller's own limits are used.") +
    (L.source === "ec-defaults" ? " " + t("The firmware limit table could not be read, limits are taken from the controller defaults.") : "");
  $("#pe-reset").textContent = custom ? t("Reset slot to factory") : t("Reset profile to factory");
  const rows = $("#pe-rows"); rows.innerHTML = "";
  const row = (title, sub, ctrl, out) => rows.append(h("div", { class: "pe-row" }, h("div", { class: "lbl" }, h("b", {}, title), h("small", {}, sub)), h("div", { class: "val" }, ctrl), out || h("span")));
  const slider = (sect, key, min, max, unit) => {
    if (max > min) pe[sect][key] = Math.min(Math.max(pe[sect][key], min), max);
    const o = h("output", {}, `${pe[sect][key]} ${unit}`);
    const r = h("input", { type: "range", min, max: Math.max(min, max), step: 1, value: Math.min(Math.max(pe[sect][key], min), Math.max(min, max)) });
    r.addEventListener("input", () => { pe[sect][key] = +r.value; o.textContent = `${r.value} ${unit}`; });
    return [r, o];
  };
  const toggle = (sect, key, after) => {
    const c = h("input", { type: "checkbox" }); c.checked = !!pe[sect][key];
    c.addEventListener("change", () => { pe[sect][key] = c.checked ? 1 : 0; if (after) after(); });
    return h("label", { class: "sw" }, c, h("span"));
  };
  if (custom) {
    const inp = h("input", { type: "text", maxlength: 24, value: slotName(prof, +name.slice(-1)) });
    inp.addEventListener("input", () => { pe.CustomizeName = inp.value; });
    row(t("Slot name"), t("Shown here, on the fan page and in notifications"), inp);
  }
  const W = t("W");
  let [r, o] = slider("CPU", "PL1", L.pl_min, L.pl1_max, W); row(t("Long-term power limit (PL1)"), t("The power the processor holds under a long load"), r, o);
  [r, o] = slider("CPU", "PL2", L.pl_min, L.pl2_max, W); row(t("Short-term power limit (PL2)"), t("For short bursts; not lower than PL1"), r, o);
  [r, o] = slider("CPU", "PL4", L.pl_min, L.pl4_max, W); row(t("Peak power limit (PL4)"), t("The most the processor may draw for an instant; not lower than PL2"), r, o);
  if (L.tcc_max > 0) {
    [r, o] = slider("CPU", "TccOffset", 0, L.tcc_max, "°C");
    row(t("Lower the throttle temperature (TCC offset)"), t("The processor starts to cut its clock this many degrees below its maximum"), h("div", { class: "row", style: "flex:1" }, toggle("CPU", "TccOffsetSwitch"), r), o);
  }
  if (S.platform.nv_gpu && (L.ctgp_support || L.db_support)) {
    if (L.ctgp_support) {
      [r, o] = slider("GPU", "ConfigurableTGPTarget", L.tgp_default, L.tgp_max + (pe.GPU.DynamicBoostSwitch ? 0 : L.db_max), W);
      row(t("Graphics power target (cTGP)"), t("The total power the graphics card may use"), h("div", { class: "row", style: "flex:1" }, toggle("GPU", "ConfigurableTGPSwitch"), r), o);
    }
    if (L.db_support) {
      [r, o] = slider("GPU", "DynamicBoost", 0, L.db_max, W);
      row(t("Dynamic Boost"), t("Lets the graphics card take power from the processor"), h("div", { class: "row", style: "flex:1" }, toggle("GPU", "DynamicBoostSwitch", () => renderProfileEditor()), r), o);
    }
  }
}
$("#pe-apply").addEventListener("click", () => {
  if (!pe) return;
  const c = pe.CPU;
  if (c.PL2 < c.PL1) c.PL2 = c.PL1;
  if (c.PL4 < c.PL2) return toast(t("PL4 must not be lower than PL2"), true);
  const body = { CPU: { PL1: c.PL1, PL2: c.PL2, PL4: c.PL4, TccOffsetSwitch: c.TccOffsetSwitch, TccOffset: c.TccOffset },
    GPU: { ConfigurableTGPSwitch: pe.GPU.ConfigurableTGPSwitch, ConfigurableTGPTarget: pe.GPU.ConfigurableTGPTarget,
      DynamicBoostSwitch: pe.GPU.DynamicBoostSwitch, DynamicBoost: pe.GPU.DynamicBoost } };
  if (!S.platform.nv_gpu) delete body.GPU;
  if (pe.Name.startsWith("Mode4")) body.CustomizeName = pe.CustomizeName;
  act(async () => { await api("profiles/" + pe.Name, body, "PUT"); pe = null; }, t("Profile applied"));
});
$("#pe-reset").addEventListener("click", () => {
  if (!pe || !confirm(t("Reset “{0}” to the factory values? Its power limits and fan curve are replaced.", pe.Name.startsWith("Mode4") ? slotName(pe, +pe.Name.slice(-1)) : tableLabel(pe.FAN.TableName)))) return;
  act(async () => { await api("profile-reset/" + pe.Name, {}); pe = null; edit = null; }, t("Factory values restored"));
});

$("#fanboost").addEventListener("change", e => act(() => api("fanboost", { on: e.target.checked }), e.target.checked ? t("Fan Boost on") : t("Fan Boost off")));
$("#btn-restore").addEventListener("click", () => { if (confirm(t("Reset modes and profiles to factory values?"))) act(() => api("restore", {}), t("Settings restored")); });

// ---------------------------------------------------------------- fans
let curTable = null, fanKind = "CPU", edit = null;
function renderFanPage() {
  if (!S.platform.fan_control) { $("#page-fans").querySelectorAll(".card").forEach(c => c.classList.add("hidden")); return; }
  const list = tableList();
  if (!curTable || !list.includes(curTable)) curTable = list.includes(S.power.current_table) ? S.power.current_table : list[0];
  $("#pl-card").classList.toggle("hidden", isStd());
  const seg = $("#table-seg"); seg.innerHTML = "";
  for (const n of list) seg.append(h("button", { class: n === curTable ? "on" : "", onclick: () => { curTable = n; edit = null; renderFanPage(); } },
    TABLE_LABEL[n] + (n === S.power.current_table ? " ●" : "")));
  $("#fan-kind-seg").classList.toggle("hidden", !S.platform.nv_gpu);
  if (!S.platform.nv_gpu) fanKind = "CPU";
  if (!edit || edit.Name !== curTable) edit = JSON.parse(JSON.stringify(S.tables[curTable] || null));
  if (!edit) { $("#curve").innerHTML = ""; return; }
  $("#respective").checked = !!edit.FanControlRespective;
  drawCurve(); drawPts(); if (!isStd()) renderPL();
}
function factoryOf(name) {
  const src = { 1: "Gaming", 2: "Office", 3: "Turbo", 4: "Gaming" }[name[1]];
  return S.default_tables && S.default_tables["DefaultFanTable_" + src];
}
$$("#fan-presets button").forEach(b => b.addEventListener("click", () => {
  const f = factoryOf(curTable);
  if (!edit || !f) return toast(t("The factory curve has not been read from the controller yet"), true);
  for (const k of ["CPU", "GPU"]) {
    if (!f[k]) continue;
    edit[k] = JSON.parse(JSON.stringify(f[k]));
    const act = edit[k].map((p, i) => i).filter(i => edit[k][i].Duty <= 100 && (i === 0 || edit[k][i].UpT < 255));
    for (const i of act) {
      if (b.dataset.p === "max") edit[k][i].Duty = 100;
      else if (b.dataset.p === "quiet") edit[k][i].Duty = Math.round(edit[k][i].Duty * 0.8);   // OEM rule for its quiet table
    }
    const top = act[act.length - 1];
    if (top !== undefined && edit[k][top].Duty < 40) edit[k][top].Duty = 40;
  }
  drawCurve(); drawPts();
  toast(t("Preset loaded into the editor — press Save to write it"));
}));
$$("#fan-kind-seg button").forEach(b => b.addEventListener("click", () => { fanKind = b.dataset.k; $$("#fan-kind-seg button").forEach(x => x.classList.toggle("on", x === b)); drawCurve(); drawPts(); }));
function activePts() { return edit[fanKind].map((p, i) => ({ ...p, i })).filter(p => p.Duty <= 100 && (p.i === 0 || p.UpT < 255)); }
const CX = t => 50 + (t - 20) / 80 * 570, CY = d => 270 - d / 100 * 250, TX = x => Math.round(20 + (x - 50) / 570 * 80), DY = y => Math.round((270 - y) / 250 * 100);
let curveDrag = null;
function drawCurve() {
  const svg = $("#curve"); const pts = activePts();
  let g = '<g class="grid">';
  for (let t = 20; t <= 100; t += 10) g += `<line x1="${CX(t)}" x2="${CX(t)}" y1="20" y2="270"/><text x="${CX(t) - 8}" y="288">${t}°</text>`;
  for (let d = 0; d <= 100; d += 25) g += `<line x1="50" x2="620" y1="${CY(d)}" y2="${CY(d)}"/><text x="14" y="${CY(d) + 4}">${d}%</text>`;
  g += "</g>";
  let path = "";
  pts.forEach((p, k) => {
    const x = CX(Math.max(20, p.i === 0 ? 20 : p.UpT)), y = CY(p.Duty);
    path += k === 0 ? `M${x},${y}` : ` L${x},${CY(pts[k - 1].Duty)} L${x},${y}`;
  });
  if (pts.length) path += ` L620,${CY(pts[pts.length - 1].Duty)}`;
  const col = fanKind === "GPU" ? "var(--gpu)" : "var(--acc)";
  let circles = "";
  pts.forEach(p => { circles += `<circle class="pt ${fanKind === "GPU" ? "gpu" : ""}" data-i="${p.i}" r="7" cx="${CX(Math.max(20, p.i === 0 ? 20 : p.UpT))}" cy="${CY(p.Duty)}"><title>${t("Level")} ${p.i}: ${p.i ? p.UpT + "°C" : t("start")} → ${p.Duty}%</title></circle>`; });
  svg.innerHTML = g + `<path d="${path}" fill="none" stroke="${col}" stroke-width="2.5"/>` + circles;
  // the drag state lives outside drawCurve(): the SVG is re-rendered on every move
  svg.onpointerdown = e => {
    e.preventDefault();                       // no text selection / native drag (Edge, WebKitGTK)
    const c = e.target.closest(".pt"); if (c) { curveDrag = +c.dataset.i; svg.setPointerCapture(e.pointerId); }
  };
  svg.onpointermove = e => {
    const drag = curveDrag;
    if (drag == null) return;
    e.preventDefault();
    const r = svg.getBoundingClientRect(), x = (e.clientX - r.left) / r.width * 640, y = (e.clientY - r.top) / r.height * 300;
    const P = edit[fanKind], p = P[drag];
    p.Duty = Math.max(0, Math.min(100, DY(y)));
    if (drag > 0) {
      // equal neighbours are allowed: factory tables use them (e.g. 55/55 °C)
      const lo = drag > 1 ? P[drag - 1].UpT : 21, hiP = P[drag + 1];
      const hi = hiP && hiP.Duty <= 100 && hiP.UpT > 0 && hiP.UpT < 255 ? hiP.UpT : 100;
      p.UpT = Math.max(lo, Math.min(hi, TX(x)));
      if (P[drag - 1].DownT >= p.UpT && drag - 1 >= 0) P[drag - 1].DownT = Math.max(0, p.UpT - 2);
    }
    drawCurve(); drawPts();
  };
  svg.onpointerup = svg.onpointercancel = e => {
    if (curveDrag != null && svg.hasPointerCapture(e.pointerId)) svg.releasePointerCapture(e.pointerId);
    curveDrag = null;
  };
}
function drawPts() {
  const tb = $("#pts"); tb.innerHTML = "";
  const P = edit[fanKind];
  const head = h("tr", {}, h("th", {}, t("Level")), ...P.map((_, i) => h("th", {}, i)));
  const row = (label, f, help) => h("tr", {}, h("th", { title: help }, label), ...P.map((p, i) => {
    const unused = p.Duty > 100 || (i > 0 && (p.UpT >= 255 || p.UpT === 0));
    const inp = h("input", { type: "number", min: 0, max: 255, value: p[f], disabled: f === "UpT" && i === 0 });
    inp.addEventListener("change", () => { p[f] = Math.max(0, Math.min(255, parseInt(inp.value || "0", 10))); drawCurve(); drawPts(); });
    return h("td", { class: unused ? "na" : "" }, inp);
  }));
  tb.append(head, row(t("On, °C"), "UpT", t("Temperature to enter this level (255 — unused)")),
    row(t("Off, °C"), "DownT", t("Temperature to return to the previous level")),
    row(t("Speed, %"), "Duty", t("Fan speed (255 — level unused)")));
}
$("#respective").addEventListener("change", e => { if (edit) edit.FanControlRespective = e.target.checked; });
$("#btn-table-save").addEventListener("click", () => act(async () => {
  for (const k of ["CPU", "GPU"]) {
    let prev = null;                       // previous active level; levels after the first unused one are ignored
    for (let i = 0; i < 16; i++) {
      const p = edit[k][i];
      if (p.Duty > 100 || (i > 0 && (p.UpT >= 255 || p.UpT === 0))) break;
      if (prev !== null && p.UpT < prev) throw new Error(t("{0}: level temperatures must not decrease (level {1})", k, i));
      prev = p.UpT;
    }
  }
  await api("table/" + curTable, { CPU: edit.CPU, GPU: edit.GPU, FanControlRespective: edit.FanControlRespective }, "PUT"); edit = null;
}, t("Table saved")));
$("#btn-table-restore").addEventListener("click", () => { if (confirm(t("Restore the factory curve for “{0}”?", TABLE_LABEL[curTable]))) act(async () => { await api(`table/${curTable}/restore`, {}); edit = null; }, t("Factory table restored")); });

function profileOfTable(t) { return `Mode${t[1]}_Profile${t[3]}`; }
function renderPL() {
  const p = S.profiles[profileOfTable(curTable)]; const box = $("#pl-edit"); box.innerHTML = "";
  if (!p) return;
  const c = p.CPU;
  const fld = (label, key) => {
    const en = h("input", { type: "checkbox", "data-k": key + "_Enabled" }); en.checked = !!c[key + "_Enabled"];
    const v = h("input", { type: "number", min: 5, max: 250, value: c[key], "data-k": key });
    return h("div", { class: "kpi" }, h("div", { class: "k" }, label), h("div", { class: "row" }, en, v, h("span", { class: "muted" }, t("W"))));
  };
  box.append(fld(t("PL1 on AC"), "PL1"), fld(t("PL2 on AC"), "PL2"), fld(t("PL1 on battery"), "PL1_dc"), fld(t("PL2 on battery"), "PL2_dc"));
}
$("#btn-pl-save").addEventListener("click", () => {
  const CPU = {};
  $$("#pl-edit input").forEach(i => { CPU[i.dataset.k] = i.type === "checkbox" ? i.checked : parseInt(i.value || "0", 10); });
  act(() => api("profiles/" + profileOfTable(curTable), { CPU }, "PUT"), t("Power limits applied"));
});

// ---------------------------------------------------------------- lighting
let kbSel = { effect: 4, light: 4, speed: 2, direction: 0, colors: [[255, 0, 0]], circular: false };
let userBuf = Array.from({ length: 126 }, () => [0, 0, 0]);
function renderLight() {
  const k = S.keyboard;
  renderLightbar();
  $("#rgb-ui").classList.toggle("hidden", k.kind !== "rgb");
  $("#single-ui").classList.toggle("hidden", k.kind !== "single");
  $("#none-ui").classList.toggle("hidden", k.kind !== "none");
  $("#kb-power").checked = !!k.power; $("#kb-power").disabled = k.kind === "none";
  $("#light-sub").textContent = k.kind === "rgb" ? t("ITE controller {0}, firmware {1}", k.device.pid, k.device.fw) : k.kind === "single" ? t("Single-colour backlight (EC controlled)") : t("No backlight found");
  if (k.kind === "single") { $("#kb-level").value = k.level; $("#kb-level").nextElementSibling.textContent = k.level; }
  if (k.kind !== "rgb") return;
  if (k.effect) { kbSel = { ...kbSel, effect: k.effect.idx, light: k.effect.light, speed: k.effect.speed, direction: k.effect.direction, circular: k.effect.circular }; if (k.effect.colors?.length) kbSel.colors = k.effect.colors; if (k.effect.user) userBuf = k.effect.user; }
  const eb = $("#effects"); eb.innerHTML = "";
  for (const [id, name] of Object.entries(k.effects)) {
    const na = (k.unsupported_effects || []).includes(+id);
    eb.append(h("div", { class: `eff${+id === kbSel.effect ? " on" : ""}${na ? " na" : ""}`, title: na ? (+id === 13 ? t("Music mode needs audio capture — not supported") : t("Light bar only effect")) : "",
      onclick: () => { if (na) return toast(t("This effect is not available for this keyboard"), true); kbSel.effect = +id; applyKb(); } },
      h("div", { class: "sw8" }), t(EFFECT_NAME[name] || name)));
  }
  for (const [id, key] of [["kb-light", "light"], ["kb-speed", "speed"]]) { $("#" + id).value = kbSel[key]; $("#" + id).nextElementSibling.textContent = kbSel[key]; }
  $("#kb-dir").value = kbSel.direction; $("#kb-multi").checked = kbSel.circular;
  const sw = $("#swatches"); sw.innerHTML = "";
  for (const c of k.default_colors) {
    const on = !kbSel.circular && kbSel.colors[0] && kbSel.colors[0].join() === c.join();
    sw.append(h("div", { class: "swatch" + (on ? " on" : ""), style: `background:rgb(${c})`, onclick: () => { kbSel.colors = [c]; kbSel.circular = false; applyKb(); } }));
  }
  $("#usermode-card").classList.toggle("hidden", kbSel.effect !== 14);
  $("#alphabet-row").classList.toggle("hidden", kbSel.effect !== 20);
  if (k.effect?.alphabet) $("#kb-alpha").value = k.effect.alphabet;
  drawKbGrid();
}
function applyKb() {
  const body = { ...kbSel };
  if (kbSel.circular) body.colors = S.keyboard.default_colors;
  if (kbSel.effect === 14) body.user = userBuf;
  if (kbSel.effect === 20) body.alphabet = $("#kb-alpha").value || "HELLO";
  act(() => api("keyboard/effect", body));
}
$("#kb-power").addEventListener("change", e => act(() => api("keyboard/power", { on: e.target.checked })));

// ---------------------------------------------------------------- light bar (chassis)
const LB_EFFECT_NAME = { static: "Static colour", breathing: "Breathing", breathing_multi: "Breathing, multicolour", wave: "Wave",
  cycle: "Colour cycle", rainbow: "Rainbow", colorbreath: "Colour breathing", colorwave: "Colour wave" };
const LB_ZONE_NAME = { hinge: "Rear (hinge)", base: "Base", logo: "Logo" };
let lbZone = null;
function renderLightbar() {
  const lb = S.keyboard && S.keyboard.lightbar;
  $("#nav-lightbar").classList.toggle("hidden", !lb);
  $("#lb-ui").classList.toggle("hidden", !lb);
  $("#lb-none").classList.toggle("hidden", !!lb);
  if (!lb) { $("#lb-sub").textContent = ""; return; }
  const zones = Object.keys(lb.zones);
  if (!zones.includes(lbZone)) lbZone = zones[0];
  const z = lb.zones[lbZone];
  $("#lb-sub").textContent = t("ITE controller {0}, firmware {1}", lb.device.pid, lb.device.fw);
  const seg = $("#lb-zones"); seg.innerHTML = "";
  if (zones.length > 1) for (const k of zones) seg.append(h("button", { class: k === lbZone ? "on" : "", onclick: () => { lbZone = k; renderLightbar(); } }, t(LB_ZONE_NAME[k] || k)));
  $("#lb-power").checked = z.power !== false;
  const sel = $("#lb-effect"); sel.innerHTML = "";
  for (const e of lb.effects) { const o = h("option", { value: e }, t(LB_EFFECT_NAME[e] || e)); if (e === z.effect) o.selected = true; sel.append(o); }
  for (const k of ["light", "speed"]) { $("#lb-" + k).value = z[k]; $("#lb-" + k).nextElementSibling.textContent = z[k]; }
  const sw = $("#lb-swatches"); sw.innerHTML = "";
  for (const c of S.keyboard.default_colors.concat([[255, 255, 255]])) {
    const on = z.colors && z.colors.length === 1 && z.colors[0].join() === c.join();
    sw.append(h("div", { class: "swatch" + (on ? " on" : ""), style: `background:rgb(${c})`, onclick: () => lbSet({ colors: [c] }) }));
  }
}
function lbSet(body) { act(() => api("lightbar", { zone: lbZone, ...body })); }
$("#lb-power").addEventListener("change", e => lbSet({ power: e.target.checked }));
$("#lb-effect").addEventListener("change", e => lbSet({ effect: e.target.value }));
for (const k of ["light", "speed"]) {
  $("#lb-" + k).addEventListener("input", e => { e.target.nextElementSibling.textContent = e.target.value; });
  $("#lb-" + k).addEventListener("change", e => lbSet({ [k]: +e.target.value }));
}
$("#lb-custom").addEventListener("change", e => lbSet({ colors: [hex2rgb(e.target.value)] }));
for (const [id, key] of [["kb-light", "light"], ["kb-speed", "speed"]]) {
  $("#" + id).addEventListener("input", e => { e.target.nextElementSibling.textContent = e.target.value; });
  $("#" + id).addEventListener("change", e => { kbSel[key] = +e.target.value; applyKb(); });
}
$("#kb-level").addEventListener("input", e => { e.target.nextElementSibling.textContent = e.target.value; });
$("#kb-level").addEventListener("change", e => act(() => api("keyboard/level", { level: +e.target.value })));
$("#kb-dir").addEventListener("change", e => { kbSel.direction = +e.target.value; applyKb(); });
$("#kb-multi").addEventListener("change", e => { kbSel.circular = e.target.checked; applyKb(); });
$("#kb-alpha").addEventListener("change", () => applyKb());
$("#kb-custom").addEventListener("change", e => { kbSel.colors = [hex2rgb(e.target.value)]; kbSel.circular = false; applyKb(); });
function hex2rgb(x) { const n = parseInt(x.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
let painting = false;
function drawKbGrid() {
  const g = $("#kbgrid"); g.innerHTML = "";
  userBuf.forEach((c, i) => {
    const k = h("div", { class: "key", style: `background:rgb(${c})`, "data-i": i, title: t("row {0}, key {1}", Math.floor(i / 21) + 1, i % 21 + 1) });
    g.append(k);
  });
  g.onpointerdown = e => { painting = true; paint(e); };
  g.onpointerover = e => { if (painting) paint(e); };
  window.onpointerup = () => { painting = false; };
}
function paint(e) {
  const k = e.target.closest(".key"); if (!k) return;
  const c = hex2rgb($("#brush").value); userBuf[+k.dataset.i] = c; k.style.background = `rgb(${c})`;
}
$("#um-fill").addEventListener("click", () => { const c = hex2rgb($("#brush").value); userBuf = userBuf.map(() => c); drawKbGrid(); });
$("#um-clear").addEventListener("click", () => { userBuf = userBuf.map(() => [0, 0, 0]); drawKbGrid(); });
$("#um-apply").addEventListener("click", () => { kbSel.effect = 14; applyKb(); });

// ---------------------------------------------------------------- battery
const BAT_MODES = [
  { id: 0, name: "Full capacity mode", desc: "Full charge. Best when you often run on battery for a long time." },
  { id: 1, name: "Balanced mode", desc: "Suitable for short periods without the charger." },
  { id: 2, name: "Stationary mode", desc: "For a laptop that is rarely used without the charger." },
];
function renderBattery() {
  const b = S.battery; const box = $("#bat-modes"); box.innerHTML = "";
  for (const m of BAT_MODES) box.append(h("div", { class: "choice" + (b.health_mode === m.id ? " on" : ""), onclick: () => act(() => api("battery", { health_mode: m.id }), t(m.name)) }, h("h4", {}, t(m.name)), h("p", {}, t(m.desc))));
  $("#lim-up").value = b.limit_up; $("#lim-up").nextElementSibling.textContent = b.limit_up + "%";
  $("#lim-down").value = b.limit_down; $("#lim-down").nextElementSibling.textContent = b.limit_down + "%";
  $("#typec-card").classList.toggle("hidden", !b.typec_priority_support);
  $("#typec").checked = !!b.typec_priority;
  updateBatStats();
}
function updateBatStats() {
  if (!S) return;
  const b = S.battery, m = lastMonitor?.battery || {}; const box = $("#bat-stats"); box.innerHTML = "";
  const kpi = (k, v) => h("div", { class: "card kpi" }, h("div", { class: "k" }, k), h("div", { class: "v" }, v));
  box.append(kpi(t("Current charge level"), m.percent != null ? m.percent + "%" : "—"),
    kpi(t("Status"), batStatus(m.status) || "—"),
    kpi(t("Battery health"), m.health != null ? m.health + "%" : "—"),
    kpi(t("Charge cycles"), m.cycle_count ?? b.cycle_count));
}
for (const id of ["lim-up", "lim-down"]) $("#" + id).addEventListener("input", e => { e.target.nextElementSibling.textContent = e.target.value + "%"; });
$("#btn-lim").addEventListener("click", () => act(() => api("battery", { limit_up: +$("#lim-up").value, limit_down: +$("#lim-down").value }), t("Charge limits applied")));
$("#typec").addEventListener("change", e => act(() => api("battery", { typec_priority: e.target.checked })));

// ---------------------------------------------------------------- switches
function renderSwitches() {
  const s = S.settings; const L = $("#switch-list"); L.innerHTML = "";
  const item = (title, desc, key, value, opts = {}) => {
    const inp = h("input", { type: "checkbox", disabled: opts.disabled }); inp.checked = !!value;
    inp.addEventListener("change", () => {
      if (opts.confirm && !confirm(opts.confirm)) { inp.checked = !inp.checked; return; }
      act(() => api("setting", { key, value: inp.checked }), opts.ok);
    });
    L.append(h("div", { class: "item" }, h("div", {}, h("h4", {}, t(title)), h("p", {}, t(desc))), h("label", { class: "sw" }, inp, h("span"))));
  };
  item("Windows key lock", "Disable the Super (Windows) key on the keyboard.", "winkey_lock", s.winkey_lock);
  item("Fn Key Lock", "F1–F12 functions without pressing Fn (primary/secondary function set).", "fn_lock", s.fn_lock);
  item("USB power in sleep", "When the computer is off or asleep, the USB port keeps charging devices.", "usb_charger", s.usb_charger);
  item("Touchpad", "Turn the touchpad on or off.", "touchpad_enabled", s.touchpad_enabled);
  item("Touchpad toggle", "Button/gesture on the touchpad itself that turns it on and off.", "touchpad_toggle", s.touchpad_toggle);
  item("Power on with AC", "The laptop turns on when the power adapter is connected.", "ac_recovery", s.ac_recovery);
  if (s.dgpu_direct !== null) item("NVIDIA Optimus off (discrete GPU direct mode)", "The internal display is wired directly to the discrete GPU. Restart required.", "dgpu_direct", s.dgpu_direct, { confirm: t("The MUX switch takes effect after a restart. Continue?"), ok: t("The change takes effect after a restart") });
  if (s.webcam !== null && s.webcam !== undefined) item("Webcam", "When off, the built-in camera is disconnected from the USB bus and no program can use it.", "webcam", s.webcam);
  if (s.wifi !== null) item("Wi-Fi", "Wireless network (rfkill).", "wifi", s.wifi);
  if (s.bluetooth !== null) item("Bluetooth", "Bluetooth adapter (rfkill).", "bluetooth", s.bluetooth);
  item("On-screen notifications", "Show a notification when the mode changes and hotkeys are pressed.", "osd", s.osd);
  item("Debug logging", "Write detailed messages to the service log (for bug reports).", "debug", s.debug);
  const sel = h("select", {}, ...[[0, t("Never")], [10, t("{0} seconds", 10)], [30, t("{0} seconds", 30)], [60, t("1 minute")], [300, t("{0} minutes", 5)], [600, t("{0} minutes", 10)]].map(([v, txt]) => { const o = h("option", { value: v }, txt); if (+s.kb_timeout === v) o.selected = true; return o; }));
  sel.addEventListener("change", () => act(() => api("setting", { key: "kb_timeout", value: +sel.value })));
  L.append(h("div", { class: "item" }, h("div", {}, h("h4", {}, t("Keyboard backlight auto-off")), h("p", {}, t("Turn the backlight off after inactivity and back on when a key is pressed."))), sel));
  if (S.platform.rgb_lightbar || s.lightbar_on) L.append(h("div", { class: "item" }, h("div", {}, h("h4", {}, t("Light bar")), h("p", {}, t("Click to turn the LED bar on/off."))), h("button", { class: "btn ghost", onclick: () => act(() => api("setting", { key: "lightbar_trigger", value: true })) }, s.lightbar_on ? t("Turn off") : t("Turn on"))));
}

// ---------------------------------------------------------------- binding
function renderBinding() {
  const tb = $("#bind-table"); tb.innerHTML = "";
  const rules = S.app_binding || [];
  tb.append(h("tr", {}, h("th", {}, t("Process")), h("th", {}, t("Mode")), h("th", {}, t("Active")), h("th", {})));
  if (!rules.length) tb.append(h("tr", {}, h("td", { colspan: 4, class: "muted" }, t("No rules yet"))));
  rules.forEach((r, i) => {
    const en = h("input", { type: "checkbox" }); en.checked = r.enabled !== false;
    en.addEventListener("change", () => { rules[i].enabled = en.checked; saveRules(rules); });
    tb.append(h("tr", {}, h("td", {}, r.process), h("td", {}, MODES[r.mode] ? t(MODES[r.mode].name) : ""), h("td", {}, en),
      h("td", {}, h("button", { class: "btn ghost", onclick: () => { rules.splice(i, 1); saveRules(rules); } }, t("Delete")))));
  });
}
function saveRules(rules) { act(() => api("appbinding", { rules })); }
$("#bind-add").addEventListener("click", () => {
  const p = $("#bind-proc").value.trim(); if (!p) return;
  const rules = [...(S.app_binding || []), { process: p, mode: +$("#bind-mode").value, enabled: true }];
  $("#bind-proc").value = ""; saveRules(rules);
});

// ---------------------------------------------------------------- info
function renderInfo() {
  const i = S.info, p = S.platform;
  const dl = (el, rows) => { el.innerHTML = ""; for (const [k, v] of rows) el.append(h("dt", {}, k), h("dd", {}, v ?? "—")); };
  const lc = S.liquid || {};
  dl($("#info-dev"), [[t("Manufacturer"), i.vendor], [t("Model"), i.product], [t("Board"), i.board], ["BIOS", i.bios ? `${i.bios}${i.bios_date ? ` (${i.bios_date})` : ""}` : null], ["EC", i.ec],
    [t("Processor"), i.cpu], [t("Memory"), `${(i.memory.total_mb / 1024).toFixed(1)} ${t("GB")}`], [t(p.os === "windows" ? "Operating system" : "Linux kernel"), i.kernel]]);
  dl($("#info-svc"), [[t("Project (Project ID)"), `${p.project_name} (0x${p.project_id.toString(16).toUpperCase()})`], [t("EC access"), p.ec_backend],
    [t("Hotkeys"), p.hotkeys ? (p.os === "windows" ? "WMI (AcpiTest_EventULong)" : t("uwcc kernel module")) : t("EC polling (no module)")], ["NVRAM (UniWillVariable)", p.nvram ? t("available") : t("unavailable")],
    ["RamFan 1.5", p.ramfan15 ? t("yes") : t("no")], [t("Turbo mode"), p.turbo_support ? t("supported") : t("no")], [t("NVIDIA graphics"), p.nv_gpu ? t("yes") : t("no")],
    [t("Platform"), p.amd ? "AMD" : "Intel"], [t("Power adapter"), `${p.adapter_watt} ${t("W")}`],
    [t("Liquid cooling (EC)"), lc.ec_support ? (lc.ec_table ? t("supported, EC targets") : t("supported")) : t("not declared")]]);
  const d = $("#info-disks"); d.innerHTML = "";
  for (const x of i.disks.devices) d.append(h("div", { class: "row between", style: "padding:6px 0;border-bottom:1px solid var(--line)" },
    h("span", {}, `${x.name} · ${x.model || ""}`), h("span", { class: "muted" }, `${x.size_gb} ${t("GB")}${x.temp != null ? ` · ${x.temp}°C` : ""}${x.rotational ? " · HDD" : " · SSD"}`)));
  const w = []; if (!p.ramfan15) w.push(t("The controller does not report RamFan 1.5 support — fan control may not work on this model."));
  if (p.ec_backend === "mock") w.push(t("The service runs in simulation mode (--mock): changes are not applied to hardware."));
  $("#info-warn").classList.toggle("hidden", !w.length); $("#info-warn").innerHTML = ""; for (const x of w) $("#info-warn").append(h("p", {}, "⚠ " + x));
}


// ---------------------------------------------------------------- liquid cooling
const LC_MODES = [
  { id: "auto", name: "Automatic", desc: "Fan and pump follow the CPU/GPU temperature." },
  { id: "laptop", name: "Follow the laptop", desc: "Office 40 %, Gaming 60 %, Turbo and Custom 90 %; pump 11 V." },
  { id: "ec", name: "Controller", desc: "Targets published by the laptop's EC (as in the original software)." },
  { id: "low", name: "Low", desc: "Fan 25 %, pump 7 V. Quiet." },
  { id: "medium", name: "Medium", desc: "Fan 50 %, pump 8 V." },
  { id: "high", name: "High", desc: "Fan 90 %, pump 11 V. Maximum cooling." },
  { id: "manual", name: "Manual", desc: "Set fan speed and pump voltage yourself." },
  { id: "off", name: "Off", desc: "Fan and pump stopped, lighting stays." },
];
const LC_FX = { static: "Static", breathe: "Breathe", rainbow: "Rainbow", breathe_rainbow: "Breathing rainbow",
  spiral: "Spiral", rotating_rainbow: "Rotating rainbow", color_wave: "Colour wave" };
const LC_COLORS = [[255, 0, 0], [255, 96, 0], [255, 200, 0], [0, 255, 0], [0, 128, 0], [0, 255, 255], [0, 80, 255], [160, 0, 255], [255, 0, 160], [255, 255, 255]];
const FLOW = { ok: "Normal", fault: "No flow!", starting: "Starting…", unknown: "Unknown", idle: "Pump stopped", priming: "Filling…" };
let lcTiers = null, lcScanning = false;
function rgbHex(c) { return "#" + c.map(x => x.toString(16).padStart(2, "0")).join(""); }
function lcPost(op, body, ok) { return act(() => api("lc/" + op, body || {}), ok); }

function renderLiquid() {
  const L = S.liquid; if (!L) return;
  const pill = $("#lc-pill");
  pill.classList.toggle("hidden", !L.connected);
  if (L.connected) { pill.textContent = `💧 ${L.pump ? L.pump + " V" : t("pump off")} · ${t("fan")} ${L.fan ?? "—"}%`; pill.className = "lc-pill " + (L.flow === "fault" ? "bad" : "ok"); }
  $("#lc-na").classList.toggle("hidden", L.available);
  $("#lc-ui").classList.toggle("hidden", !L.available);
  if (!L.available) return;
  const c = L.config, busy = ["scanning", "connecting"].includes(L.status) || lcScanning;
  $("#lc-state").className = "lc-state" + (L.connected ? " on" : busy ? " busy" : "");
  $("#lc-title").textContent = L.connected ? L.name : L.status === "connecting" ? t("Connecting to {0}…", c.name || c.address) : busy ? t("Searching…") : t("Not connected");
  const sub = [];
  if (L.connected) {
    sub.push(L.generation ? `XMG Oasis ${L.generation}` : L.model || "");
    sub.push(t("firmware {0}", L.fw || "?"));
    sub.push(c.address);
  } else if (c.address) {
    sub.push(t("Remembered: {0}", c.name || c.address));
    sub.push(c.enabled ? (L.suspended ? t("paused for sleep") : t("reconnects automatically")) : t("auto-connect off"));
    if (L.error) sub.push(t("last error: {0}", errText(L.error)));
  }
  $("#lc-sub").textContent = sub.filter(Boolean).join(" · ");
  $("#lc-disc").classList.toggle("hidden", !L.connected && !c.enabled);
  $("#lc-forget").classList.toggle("hidden", !c.address);
  $("#lc-scan").textContent = L.connected ? t("Search") : (c.address && !c.enabled ? t("Search") : t("Search"));
  $("#lc-hint").classList.toggle("hidden", L.connected || !!(L.scan || []).length);
  // scan results
  const f = $("#lc-found"); f.innerHTML = "";
  for (const d of L.scan || []) {
    const cur = L.connected && d.address === c.address;
    f.append(h("div", { class: "lc-dev" }, h("div", {}, h("b", {}, d.name), h("div", { class: "muted tiny", style: "margin:0" }, `${d.address} · RSSI ${d.rssi ?? "?"} dBm`)),
      cur ? h("span", { class: "muted", style: "margin:0" }, t("Connected")) :
        h("button", { class: "btn", onclick: () => lcPost("connect", { address: d.address }, t("Connected to {0}", d.name)) }, t("Connect"))));
  }
  // live values
  const live = $("#lc-live"); live.innerHTML = "";
  const kpi = (k, v, cls) => h("div", { class: "card kpi" }, h("div", { class: "k" }, k), h("div", { class: "v " + (cls || "") }, v));
  const dim = !L.connected;
  live.append(kpi(t("Cooler fan"), L.connected && L.fan != null ? `${L.fan}%` : "—"),
    kpi(t("Pump"), L.connected && L.pump != null ? (L.pump ? `${L.pump} V` : t("off")) : "—"),
    kpi(t("Coolant flow"), L.connected ? t(FLOW[L.flow] || L.flow) + (L.guard ? " · " + t("guard 11 V") : "") : "—", L.connected ? "flow-" + L.flow : ""),
    kpi(c.mode === "ec" && L.ec_target ? t("Source") : t("Temperature (tier)"),
      c.mode === "ec" && L.ec_target ? t("EC targets") : L.temp != null ? `${L.temp}°C${L.tier != null && ["auto", "ec"].includes(c.mode) ? ` (${L.tier + 1})` : ""}` : "—"));
  // modes
  const mb = $("#lc-modes"); mb.innerHTML = "";
  for (const m of LC_MODES) {
    if (m.id === "ec" && !L.ec_table) continue;
    mb.append(h("div", { class: "choice" + (c.mode === m.id ? " on" : ""), onclick: () => lcPost("config", { mode: m.id }) }, h("h4", {}, t(m.name)), h("p", {}, t(m.desc))));
  }
  $("#lc-manual").classList.toggle("hidden", c.mode !== "manual");
  $("#lc-fan").value = c.fan; $("#lc-fan").nextElementSibling.textContent = c.fan + "%";
  $("#lc-pump").value = c.pump;
  // tiers
  $("#lc-tiers-card").classList.toggle("hidden", !["auto", "ec"].includes(c.mode));
  if (!lcTiers) lcTiers = JSON.parse(JSON.stringify(c.tiers));
  drawTiers(L);
  // lighting
  $("#lc-rgb-on").checked = !!c.rgb.on;
  const fx = $("#lc-fx"); fx.innerHTML = "";
  const mk1 = L.connected && L.model !== "LCT22002";
  for (const [id, name] of Object.entries(LC_FX)) {
    const na = mk1 && L.mk2_only.includes(id);
    fx.append(h("div", { class: `eff${c.rgb.mode === id ? " on" : ""}${na ? " na" : ""}`, title: L.mk2_only.includes(id) ? t("Mk2 (LCT22002) only") : "",
      onclick: () => { if (na) return toast(t("This lighting effect needs an Mk2 (LCT22002) cooler"), true); lcPost("config", { rgb: { on: true, mode: id } }); } },
      h("div", { class: "sw8", style: id === "static" || id === "breathe" ? `background:${rgbHex(c.rgb.color)}` : "" }), t(name) + (L.mk2_only.includes(id) ? " ²" : "")));
  }
  const sw = $("#lc-swatches"); sw.innerHTML = "";
  for (const col of LC_COLORS) sw.append(h("div", { class: "swatch" + (col.join() === c.rgb.color.join() ? " on" : ""), style: `background:rgb(${col})`,
    onclick: () => lcPost("config", { rgb: { on: true, color: col } }) }));
  $("#lc-color").value = rgbHex(c.rgb.color);
  // priming + options
  const pr = L.priming;
  $("#lc-prime-bar").style.width = pr != null ? `${Math.round(pr / 8 * 100)}%` : "0";
  $("#lc-prime").textContent = pr != null ? t("Stop ({0}/8)", pr) : t("Start");
  $("#lc-prime").disabled = dim;
  $("#lc-guard").checked = c.flow_guard !== false;
  $("#lc-notify").checked = !!c.notify_flow; $("#lc-bfan").checked = !!c.boost_fan; $("#lc-bpump").checked = !!c.boost_pump;
}
function drawTiers(L) {
  const tb = $("#lc-tiers"); tb.innerHTML = "";
  const n = lcTiers.length;
  const head = h("tr", {}, h("th", {}, t("Tier")), ...lcTiers.map((_, i) => h("th", { class: L && L.tier === i && ["auto", "ec"].includes(L.config.mode) && L.connected ? "cur" : "" }, i + 1)));
  const row = (label, key, build) => h("tr", {}, h("th", {}, label), ...lcTiers.map((tr, i) => h("td", {}, build(tr, i))));
  const num = (tr, key, min, max) => { const e = h("input", { type: "number", min, max, value: tr[key] }); e.addEventListener("change", () => { tr[key] = +e.value; }); return e; };
  tb.append(head,
    row(t("Below, °C"), "below", (tr, i) => i === n - 1 ? h("span", { class: "muted" }, "∞") : num(tr, "below", 20, 110)),
    row(t("Fan, %"), "fan", tr => num(tr, "fan", 0, 100)),
    row(t("Pump, V"), "pump", tr => { const e = h("select", {}, ...[7, 8, 11, 12].map(v => { const o = h("option", { value: v }, v); if (tr.pump === v) o.selected = true; return o; })); e.addEventListener("change", () => { tr.pump = +e.value; }); return e; }));
}
$("#lc-scan").addEventListener("click", async () => {
  lcScanning = true; renderLiquid();
  try { const r = await api("lc/scan", {}); if (!r.devices.length) toast(t("No cooler found. Is it powered on and is Bluetooth enabled?"), true); }
  catch (e) { toast(t("Error: {0}", errText(e.message)), true); }
  lcScanning = false; await refresh();
});
$("#lc-disc").addEventListener("click", () => lcPost("disconnect", {}, t("Cooler disconnected")));
$("#lc-forget").addEventListener("click", () => { if (confirm(t("Forget this cooler? Automatic reconnection will stop."))) lcPost("disconnect", { forget: true }); });
$("#lc-fan").addEventListener("input", e => { e.target.nextElementSibling.textContent = e.target.value + "%"; });
$("#lc-fan").addEventListener("change", e => lcPost("config", { mode: "manual", fan: +e.target.value }));
$("#lc-pump").addEventListener("change", e => {
  const v = +e.target.value;
  if (v === 12 && !confirm(t("12 V is not used by the OEM software and may shorten pump life. Continue?"))) { e.target.value = S.liquid.config.pump; return; }
  if (v === 0 && !confirm(t("Stop the pump? The coolant will not circulate."))) { e.target.value = S.liquid.config.pump; return; }
  lcPost("config", { mode: "manual", pump: v });
});
$("#lc-tiers-save").addEventListener("click", () => act(async () => { await api("lc/config", { tiers: lcTiers }); lcTiers = null; }, t("Tiers saved")));
$("#lc-tiers-reset").addEventListener("click", () => { lcTiers = JSON.parse(JSON.stringify(S.liquid.default_tiers)); drawTiers(S.liquid); });
$("#lc-rgb-on").addEventListener("change", e => lcPost("config", { rgb: { on: e.target.checked } }));
$("#lc-color").addEventListener("change", e => lcPost("config", { rgb: { on: true, color: hex2rgb(e.target.value) } }));
$("#lc-prime").addEventListener("click", () => {
  if (S.liquid.priming != null) return lcPost("prime", { stop: true });
  if (confirm(t("Start the coolant filling cycle (about 70 seconds)?"))) lcPost("prime", {});
});
for (const [id, key] of [["lc-guard", "flow_guard"], ["lc-notify", "notify_flow"], ["lc-bfan", "boost_fan"], ["lc-bpump", "boost_pump"]])
  $("#" + id).addEventListener("change", e => lcPost("config", { [key]: e.target.checked }));

// ---------------------------------------------------------------- history (last hour)
const HIST = {
  temp: { name: "Temperature", unit: "°C", max: 100, lines: [["ct", "CPU", "var(--cpu)"], ["gt", "GPU", "var(--gpu)"]] },
  load: { name: "Load", unit: "%", max: 100, lines: [["cl", "CPU", "var(--cpu)"], ["gl", "GPU", "var(--gpu)"]] },
  cpow: { name: "CPU power", unit: "W", max: 0, lines: [["cp", "CPU package", "var(--cpu)"]], nodata: "CPU package power is not available on this computer",
    marks: [["pl1", "PL1", "#f5a524"], ["pl2", "PL2", "#ff6b6b"], ["pl4", "PL4", "#c084fc"]] },
  gpow: { name: "GPU power", unit: "W", max: 0, lines: [["gp", "NVIDIA GPU", "var(--gpu)"]], nodata: "GPU power is not available (no NVIDIA GPU, or it is asleep)",
    marks: [["gpl", "GPU power limit", "#f5a524"]] },
  total: { name: "Total power", unit: "W", max: 0, lines: [["tp", "CPU + GPU", "var(--acc)"], ["bp", "From battery", "#f5a524"]],
    nodata: "no data", marks: [["adapter", "Power adapter", "#ff6b6b"]] },
  fans: { name: "Fans", unit: "rpm", max: 0, lines: [["cf", "CPU", "var(--cpu)"], ["gf", "GPU", "var(--gpu)"]] },
  cooler: { name: "Cooler", unit: "%", max: 100, lines: [["lf", "Cooler fan", "var(--acc)"], ["lpx", "Pump (V × 8)", "var(--warn)"]] },
};
let histKey = "temp", histData = [], histT = 0;
function renderHistSeg() {
  const seg = $("#hist-seg"); seg.innerHTML = "";
  for (const [k, d] of Object.entries(HIST)) seg.append(h("button", { class: k === histKey ? "on" : "", onclick: () => { histKey = k; renderHistSeg(); drawHistory(); } }, t(d.name)));
}
async function loadHistory(force) {
  if (!force && Date.now() - histT < 20000) return drawHistory();
  try { histData = await api("history"); histT = Date.now(); histData.forEach(p => { p.lpx = p.lp != null ? p.lp * 8 : null; }); } catch (_) {}
  drawHistory();
}
function drawHistory() {
  const svg = $("#hist-chart"), W = 800, H = 180, d = HIST[histKey];
  const now = Date.now() / 1000, t0 = now - 3600;
  let max = d.max;
  const marks = d.marks || [];
  if (histKey === "total") histData.forEach(p => { p.adapter = S && S.platform && S.platform.adapter_watt || null; });
  if (!max) {
    max = 10;
    for (const p of histData) for (const [k] of d.lines) if (p[k] > max) max = p[k];
    // keep the limit marks in view, but not a 330 W adapter line over a 20 W curve
    for (const p of histData) for (const [k] of marks) if (p[k] > max && p[k] < max * 3) max = p[k];
    max = Math.ceil(max * 1.1 / 10) * 10;
  }
  let g = "";
  for (const f of [0.25, 0.5, 0.75]) { const y = H - f * H; g += `<line x1="0" x2="${W}" y1="${y}" y2="${y}" stroke="#1f2830"/><text x="4" y="${y - 3}" fill="#55636e" font-size="10">${Math.round(max * f)} ${t(d.unit)}</text>`; }
  for (let m = 0; m <= 60; m += 15) { const x = m === 60 ? W - 4 : (m / 60) * W + 2; g += `<text x="${x}" y="${H - 3}" fill="#55636e" font-size="10" text-anchor="${m === 60 ? "end" : "start"}">${m === 60 ? t("now") : "−" + (60 - m) + " " + t("min")}</text>`; }
  for (const [k, , color] of d.lines) {
    let path = "", pen = false, prevT = null;
    for (const p of histData) {
      const v = p[k];
      if (v == null || (prevT && p.t - prevT > 20)) pen = false;
      prevT = p.t;
      if (v == null) continue;
      const x = Math.max(0, (p.t - t0) / 3600 * W), y = H - Math.min(1, v / max) * H;
      path += (pen ? " L" : " M") + x.toFixed(1) + "," + y.toFixed(1); pen = true;
    }
    if (path) g += `<path d="${path}" fill="none" stroke="${color}" stroke-width="1.8"/>`;
  }
  for (const [k, n, color] of marks) {            // limits: dashed step line + label at the latest value
    let path = "", last = null, lastX = 0;
    for (const p of histData) {
      const v = p[k]; if (v == null || v > max) { last = null; continue; }
      const x = Math.max(0, (p.t - t0) / 3600 * W), y = H - v / max * H;
      path += (last == null ? " M" : ` L${x.toFixed(1)},${(H - last / max * H).toFixed(1)} L`) + x.toFixed(1) + "," + y.toFixed(1);
      last = v; lastX = x;
    }
    if (path) g += `<path d="${path}" fill="none" stroke="${color}" stroke-width="1.2" stroke-dasharray="6 4" opacity=".9"/>` +
      `<text x="${Math.min(lastX, W - 4)}" y="${H - last / max * H - 4}" fill="${color}" font-size="10" text-anchor="end">${t(n)} ${last} ${t("W")}</text>`;
  }
  const hasData = histData.some(p => d.lines.some(([k]) => p[k] != null));
  const msg = !histData.length ? t("collecting data…") : !hasData ? t(d.nodata || "no data") : "";
  svg.innerHTML = msg ? g + `<text x="${W / 2}" y="${H / 2}" fill="#55636e" font-size="13" text-anchor="middle">${msg}</text>` : g;
  if (hasData) {                                  // latest / average / max of the visible series
    const st = d.lines.map(([k, n]) => {
      const v = histData.map(p => p[k]).filter(x => x != null);
      if (!v.length) return "";
      const avg = v.reduce((a, b) => a + b, 0) / v.length;
      return `${t(n)}: ${t("now")} ${v[v.length - 1]} · ${t("avg")} ${Math.round(avg * 10) / 10} · ${t("max")} ${Math.max(...v)} ${t(d.unit)}`;
    }).filter(Boolean);
    for (const [k, n] of marks) {
      const v = histData.map(p => p[k]).filter(x => x != null);
      if (v.length) st.push(`${t(n)}: ${v[v.length - 1]} ${t("W")}`);
    }
    $("#hist-stats").textContent = st.join("  |  ");
  } else $("#hist-stats").textContent = "";
  const lg = $("#hist-legend"); lg.innerHTML = "";
  for (const [, n, color] of d.lines) lg.append(h("span", { class: "lg", style: `--c:${color}` }, t(n)));
  for (const [k, n, color] of marks) if (histData.some(p => p[k] != null)) lg.append(h("span", { class: "lg dash", style: `--c:${color}` }, t(n)));
}

function downloadHistory(fmt) {
  // served by uwccd with Content-Disposition: works in Edge (Windows) and in the WebKitGTK window (Linux)
  const a = h("a", { href: `/api/history/export?format=${fmt}&token=${encodeURIComponent(TOKEN)}`, download: "" });
  document.body.append(a); a.click(); a.remove();
  toast(t("Export started — the file goes to your Downloads folder"));
}
function downloadChartPng() {
  const svg = $("#hist-chart"), W = 1600, H = 360, d = HIST[histKey];
  const xml = new XMLSerializer().serializeToString(svg).replace(/var\(--cpu\)/g, getComputedStyle(document.body).getPropertyValue("--cpu").trim() || "#2fd3b5")
    .replace(/var\(--gpu\)/g, getComputedStyle(document.body).getPropertyValue("--gpu").trim() || "#7aa2ff")
    .replace(/var\(--acc\)/g, "#2fd3b5").replace(/var\(--warn\)/g, "#f5a524");
  const img = new Image();
  img.onload = () => {
    const c = document.createElement("canvas"); c.width = W; c.height = H + 40;
    const x = c.getContext("2d"); x.fillStyle = "#0e1215"; x.fillRect(0, 0, c.width, c.height);
    x.fillStyle = "#c9d3da"; x.font = "16px sans-serif";
    x.fillText(`${t(d.name)} — ${t("Last hour")} — ${new Date().toLocaleString()}`, 12, 26);
    x.drawImage(img, 0, 40, W, H);
    c.toBlob(b => {
      const a = h("a", { href: URL.createObjectURL(b), download: `uwcc-${histKey}-${Date.now()}.png` });
      document.body.append(a); a.click(); a.remove();
    }, "image/png");
  };
  img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(xml.replace("<svg", `<svg width="${W}" height="${H}"`));
}
$("#hist-export").addEventListener("change", e => {
  const v = e.target.value; e.target.value = "";
  if (v === "png") downloadChartPng(); else if (v) downloadHistory(v);
});

// ---------------------------------------------------------------- automation page
function renderAuto() {
  const a = S.automation || {}; if (!S.automation) return;
  const modes = MODES.filter(m => (m.id !== 3 || S.power.custom_support) && (m.id !== 2 || S.power.turbo_support));
  const fill = (sel, val, withPrev) => {
    sel.innerHTML = "";
    const opts = [["keep", t("Don't change")], ...(withPrev ? [["previous", t("The mode before unplugging")]] : []), ...modes.map(m => [String(m.id), t(m.name)])];
    for (const [v, n] of opts) { const o = h("option", { value: v }, n); if (String(val) === v) o.selected = true; sel.append(o); }
    sel.disabled = !S.platform.fan_control;
  };
  fill($("#au-ac"), a.mode_on_ac, true); fill($("#au-bat"), a.mode_on_battery, false);
  $("#au-kb").checked = !!a.kb_off_on_battery; $("#au-ppd").checked = !!a.ppd_sync;
  $("#au-alerts").checked = !!a.alerts; $("#au-boost").checked = !!a.overheat_boost; $("#au-boost").disabled = !S.platform.fan_control;
  if (document.activeElement !== $("#au-cpu")) $("#au-cpu").value = a.cpu_alert;
  if (document.activeElement !== $("#au-gpu")) $("#au-gpu").value = a.gpu_alert;
}
const setKey = (key, value) => act(() => api("setting", { key, value }));
$("#au-ac").addEventListener("change", e => setKey("mode_on_ac", isNaN(+e.target.value) ? e.target.value : +e.target.value));
$("#au-bat").addEventListener("change", e => setKey("mode_on_battery", isNaN(+e.target.value) ? e.target.value : +e.target.value));
for (const [id, key] of [["au-kb", "kb_off_on_battery"], ["au-ppd", "ppd_sync"], ["au-alerts", "alerts"], ["au-boost", "overheat_boost"]])
  $("#" + id).addEventListener("change", e => setKey(key, e.target.checked));
for (const [id, key] of [["au-cpu", "cpu_alert"], ["au-gpu", "gpu_alert"]])
  $("#" + id).addEventListener("change", e => setKey(key, +e.target.value));

// ---------------------------------------------------------------- discrete GPU users
async function renderGpuUsers() {
  if (!S || !S.platform.nv_gpu) { $("#gpu-card").classList.add("hidden"); return; }
  let g; try { g = await api("gpu"); } catch (_) { return; }
  $("#gpu-card").classList.toggle("hidden", !g.present);
  const box = $("#gpu-users"); box.innerHTML = "";
  const st = { active: t("awake"), suspended: t("asleep (saving power)") }[g.state] || g.state || "—";
  box.append(h("div", { class: "gpu-proc" }, h("b", {}, t("State")), h("span", { class: g.state === "active" ? "flow-starting" : "flow-ok" }, st)));
  if (!g.users.length) box.append(h("p", { class: "muted", style: "margin:8px 0 0" }, t("No program uses the discrete GPU")));
  for (const u of g.users) box.append(h("div", { class: "gpu-proc" }, h("span", {}, `${u.name} · PID ${u.pid}`), h("code", { title: u.cmd }, u.cmd)));
}
$("#gpu-refresh").addEventListener("click", renderGpuUsers);
$$("#nav a").forEach(a => a.addEventListener("click", () => {
  if (a.dataset.page === "info") renderGpuUsers();
  if (a.dataset.page === "monitor") loadHistory();
}));
setInterval(() => { if ($("#page-monitor").classList.contains("active")) loadHistory(true); }, 30000);

// ---------------------------------------------------------------- live events
let connState = "wait";
function paintConn() {
  $("#conn").className = "conn" + (connState === "ok" ? " ok" : "");
  $("#conn span:last-child").textContent = t({ ok: "Service connected", err: "No connection to the service" }[connState] || "Connecting…");
}
function connect() {
  const es = new EventSource("/api/events?token=" + encodeURIComponent(TOKEN));
  es.onopen = () => { connState = "ok"; paintConn(); };
  es.onerror = () => { connState = "err"; paintConn(); };
  let pending = null;
  es.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.type === "monitor") return onMonitor(m.data);
    if (m.type === "mode" && m.data.osd) osd(m.data.mode === 3 ? `Custom · ${slotName(S?.profiles?.["Mode4_Profile" + ((m.data.slot || 0) + 1)], (m.data.slot || 0) + 1)}` : (MODES[m.data.mode]?.osd || ""));
    if (m.type === "overheat") toast(t("{0} at {1} °C for 30 seconds", m.data.sensor === "gpu" ? t("GPU") : t("CPU"), m.data.temp), true);
    if (m.type === "overheat_boost") toast(t("Fan Boost turned on because of overheating"), true);
    if (m.type === "fanboost" && m.data.osd) osd(m.data.on ? "FanBoostOn" : "FanBoostOff");
    if (m.type === "lc" && m.data.event === "flow_fault") toast(t("Liquid cooler: no coolant flow! Check the tubes and the coolant level."), true);
    if (m.type === "lc" && m.data.event === "disconnected" && m.data.unexpected) toast(t("Liquid cooler disconnected — reconnecting automatically"), true);
    clearTimeout(pending); pending = setTimeout(() => refresh().catch(() => {}), 150);
  };
}
(async () => {
  setLang((() => { try { return localStorage.getItem("uwcc-lang"); } catch (_) { return null; } })() || "en", false);
  if (!TOKEN) {
    document.body.innerHTML = `<div style="padding:40px;font:16px system-ui;color:#eee">${t("Open Control Center from the application menu (command <b>uwcc</b>) — an access key for the service is required.")}</div>`;
    return;
  }
  try { await refresh(); } catch (e) { toast(t("Service unavailable: {0}", e.message), true); }
  connect();
})();
