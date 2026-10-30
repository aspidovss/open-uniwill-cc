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
  if (!r.ok) { const e = new Error(j.error || r.statusText); e.status = r.status; e.data = j; throw e; }
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
// The result of an action is shown on the button that started it ("✓ Profile applied" / an error next to it),
// so it is visible where the user clicked; other actions (switches, menus) use the toast at the top.
let lastBtn = null, lastBtnAt = 0;
document.addEventListener("click", e => {
  const b = e.target.closest && e.target.closest("button.btn");
  if (b) { lastBtn = b; lastBtnAt = Date.now(); }
}, true);
function clearBtnErr(b) { const n = b && b.nextElementSibling; if (n && n.classList.contains("btn-err")) n.remove(); }
document.addEventListener("input", e => {               // a changed value makes an old error stale
  const c = e.target.closest && e.target.closest(".card"); if (c) c.querySelectorAll(".btn-err").forEach(x => x.remove());
}, true);
async function act(fn, ok) {
  const btn = Date.now() - lastBtnAt < 300 ? lastBtn : null;
  lastBtn = null;
  let label = null;
  if (btn) {
    clearBtnErr(btn); clearTimeout(btn._doneTimer);
    if (btn._label != null) { btn.innerHTML = btn._label; btn.classList.remove("done"); }
    label = btn._label = btn.innerHTML;
    btn.style.minWidth = btn.offsetWidth + "px"; btn.disabled = true; btn.classList.add("busy");
    btn._busyTimer = setTimeout(() => { if (btn.classList.contains("busy")) btn.textContent = t("Working…"); }, 250);
  }
  const restore = () => {
    if (!btn) return;
    clearTimeout(btn._busyTimer); btn.disabled = false; btn.classList.remove("busy"); btn.innerHTML = label;
  };
  try {
    await fn();
    restore();
    if (ok) {
      if (btn && btn.isConnected) {
        btn.textContent = "✓ " + (ok.length <= 28 ? ok : t("Done")); btn.classList.add("done");
        btn._doneTimer = setTimeout(() => { btn.innerHTML = label; btn._label = null; btn.classList.remove("done"); btn.style.minWidth = ""; }, 2500);
      } else toast(ok);
    } else if (btn) { btn._label = null; btn.style.minWidth = ""; }
    await refresh();
  } catch (e) {
    restore();
    if (btn) { btn._label = null; btn.style.minWidth = ""; }
    if (e.status === 409 && e.message === "busy") { toast(t("Please wait — the settings are still being applied")); return; }
    const msg = e.message.includes("software") ? t("This effect is not available for this keyboard") : t("Error: {0}", errText(e.message));
    if (btn && btn.isConnected) btn.after(h("span", { class: "btn-err", role: "alert" }, msg));
    else toast(msg, true);
  }
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
  if (typeof helpCur !== "undefined" && helpCur && $("#page-help").classList.contains("active")) openHelp(helpCur.id);
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
  $("#brand-sub").textContent = S.platform.display_name || S.platform.project_name;
  if (S.ec_access && S.ec_access.reason === "clevo_only") {      // Control Center 3.0 / Clevo laptop: no Uniwill EC
    $("#brand-sub").textContent = "Clevo · Control Center 3.0";
    const pm = (S.clevo && S.clevo.state || {}).power_mode;
    pill.textContent = pm ? t((CLEVO_POWER.find(x => x[0] === pm) || [, pm])[1]) : "—"; pill.className = "modepill";
  }
  renderModes(); renderFanPage(); renderLiquid(); renderLight(); renderBattery(); renderSwitches(); renderBinding(); renderInfo(); renderAuto(); renderAbout(); renderReportCard();
  renderHistSeg(); drawHistory();
  renderClevo(); renderDriver(); renderEcBanner(); applyFeatures(); renderBusy(S.busy || []); renderMonOff(); setupCollapsible();
}

// ---------------------------------------------------------------- monitor
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
  if (m.monitoring && m.monitoring !== "full") { lastMonitor = null; renderMonOff(m.monitoring); return; }
  renderMonOff("full");
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
  $("#st-mem").innerHTML = ""; $("#st-mem").append(h("h3", {}, t("Memory")), h("div", { class: "big" }, `${m.memory.usage}%`), h("div", { class: "sub" }, t("{0} of {1} GB", (m.memory.used_mb / 1024).toFixed(1), (m.memory.total_mb / 1024).toFixed(1))));
  $("#st-net").innerHTML = ""; $("#st-net").append(h("h3", {}, t("Network")), h("div", { class: "big" }, `↓ ${fmtRate(m.net.down_kbs)}`), h("div", { class: "sub" }, `↑ ${fmtRate(m.net.up_kbs)}`));
  const b = m.battery; $("#st-bat").innerHTML = "";
  $("#st-bat").append(h("h3", {}, t("Battery")), h("div", { class: "big" }, b.present ? `${b.percent}%` : t("none")),
    h("div", { class: "sub" }, b.present ? `${batStatus(b.status)}${b.remaining_min ? " · " + t("{0} h {1} min", Math.floor(b.remaining_min / 60), b.remaining_min % 60) : ""}${m.ac ? " · " + t("on AC") : ""}` : ""));
  lastMonitor = m; updateBatStats();
  if ($("#page-fans") && $("#page-fans").classList.contains("active")) drawCurveNow();
  if ($("#page-monitor").classList.contains("active")) loadHistory();
}
let lastMonitor = null;
function fmtRate(k) { return k > 1024 ? `${(k / 1024).toFixed(1)} ${t("MB/s")}` : `${k} ${t("KB/s")}`; }
function batStatus(s) { return { Charging: t("Charging"), Discharging: t("Discharging"), Full: t("Fully charged"), "Not charging": t("Not charging") }[s] || s || ""; }
// liquid cooler summary on the Monitor page (the full controls are on the Liquid cooling page)
function renderMonLc() {
  const box = $("#mon-lc-body"); if (!box || !S) return;
  const L = S.liquid || {}, c = L.config || {};
  box.innerHTML = "";
  if (!L.available) {
    box.append(h("p", { class: "muted" }, t("Bluetooth support for the liquid cooler is not available on this computer.")));
    return;
  }
  if (!L.connected) {
    box.append(h("div", { class: "lc-mini-state" }, h("span", { class: "dot off" }), h("b", {}, t("Not connected"))),
      h("p", { class: "muted tiny" }, c.address ? t("Last cooler: {0}", c.name || c.address) : t("Turn the cooler on and connect it on the Liquid cooling page.")));
    return;
  }
  const mode = LC_MODES.find(x => x.id === c.mode);
  box.append(h("div", { class: "lc-mini-state" }, h("span", { class: "dot " + (L.flow === "fault" ? "bad" : "on") }), h("b", {}, L.name || t("Liquid cooling")),
    h("span", { class: "muted tiny" }, mode ? t(mode.name) : "")));
  const dl = h("dl", { class: "kv" });
  const temp = c.mode === "ec" && L.ec_target ? t("EC targets")
    : L.temp != null ? `${L.temp_avg ?? L.temp}°C${L.curve_key && ["auto", "laptop", "ec"].includes(c.mode) ? ` · ${t(LC_CURVE_NAME[L.curve_key] || L.curve_key)}` : ""}` : "—";
  for (const [k, v, cls] of [[t("Pump"), L.pump != null ? (L.pump ? `${L.pump} V` : t("off")) : "—"],
                              [t("Cooler fan"), L.fan != null ? `${L.fan}%` : "—"],
                              [t("Coolant flow"), t(FLOW[L.flow] || L.flow || "—") + (L.guard ? " · " + t("guard 11 V") : ""), "flow-" + L.flow],
                              [t("Temperature (curve)"), temp]])
    dl.append(h("dt", {}, k), h("dd", { class: cls || "" }, v));
  box.append(dl);
  if (["auto", "ec"].includes(c.mode) && (L.pending || L.pump_idle))
    box.append(h("p", { class: "muted tiny", style: "margin:6px 0 0" },
      [L.pending ? t(L.pending.dir === "up" ? "Faster in {0} s if the temperature holds" : "Slower in {0} s if the temperature holds", L.pending.left) : "",
       L.pump_idle ? t("Pump stopped: cool") : ""].filter(Boolean).join(" · ")));
}
$("#mon-lc-open").addEventListener("click", () => $(`#nav a[data-page="liquid"]`)?.click());

// ---------------------------------------------------------------- modes
function fanDisabledNote(el) {
  el.innerHTML = "";
  el.append(h("div", { class: "card warn" }, h("h3", {}, t("Mode control is unavailable")),
    h("p", { class: "muted" }, t("This laptop's controller does not report RamFan 1.5 support, and the original software uses a different algorithm on such machines. To avoid writing wrong values to the EC, modes and fan curves are disabled. Monitoring, lighting and switches work."))));
}
function renderModes() {
  renderPerf();
  const box = $("#mode-cards"); box.innerHTML = "";
  if (!S.platform.fan_control) { fanDisabledNote(box); box.style.display = "block"; return; }
  box.style.display = "";
  const modes = MODES.filter(m => m.id !== 3 || S.power.custom_support);
  box.classList.toggle("four", modes.length === 4);
  for (const m of modes) {
    const dis = m.id === 2 && !S.power.turbo_support;
    box.append(h("div", { class: `mode${S.power.mode === m.id ? " on" : ""}${dis ? " dis" : ""}`, onclick: () => act(() => withBusy(t(m.name), () => api("mode", { mode: m.id })), t(m.name)) },
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
      seg.append(h("button", { class: i === idx ? "on" : "", onclick: () => act(() => withBusy(label, () => api("profile", { mode, index: i })), label) }, label));
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
let pe = null, dbStatus = null;
(async () => { try { dbStatus = await api("dynamic-boost"); } catch (_) {} })();
function renderProfileEditor(force) {
  const name = S.power.current_profile, prof = S.profiles[name], L = S.power.limits || {};
  if (!prof) return;
  if (!force && pe && pe.Name === name && $("#pe-rows").contains(document.activeElement)) return;   // user is editing
  if (!pe || pe.Name !== name) pe = JSON.parse(JSON.stringify(prof));
  const custom = name.startsWith("Mode4");
  $("#pe-title").textContent = custom ? t("Custom slot: {0}", slotName(prof, +name.slice(-1))) : t("Profile settings: {0}", tableLabel(prof.FAN.TableName));
  $("#pe-note").textContent = t("The values are applied on AC power; on battery the controller's own limits are used.") +
    (L.source === "ec-defaults" ? " " + t("The firmware limit table could not be read, limits are taken from the controller defaults.") : "") +
    (L.source === "config" ? " " + t("WMI path: limits are approximate — taken from the platform profile and the WMI settings in EC Manager.") + " " +
      t("Through WMI the extra graphics power is reached only in the stock Turbo mode; Dynamic Boost here adds power only while the processor leaves room.") : "");
  $("#pe-reset").textContent = custom ? t("Reset slot to factory") : t("Reset profile to factory");
  const rows = $("#pe-rows"); rows.innerHTML = "";
  const row = (title, sub, ctrl, out) => { const el = h("div", { class: "pe-row" }, h("div", { class: "lbl" }, h("b", {}, title), h("small", {}, sub)), h("div", { class: "val" }, ctrl), out || h("span")); rows.append(el); return el; };
  const slider = (sect, key, min, max, unit) => {
    if (max > min) pe[sect][key] = Math.min(Math.max(pe[sect][key], min), max);
    const o = h("output", {}, `${pe[sect][key]} ${unit}`);
    const r = h("input", { type: "range", min, max: Math.max(min, max), step: 1, value: Math.min(Math.max(pe[sect][key], min), Math.max(min, max)) });
    r.addEventListener("input", () => { pe[sect][key] = +r.value; o.textContent = `${r.value} ${unit}`; });
    return [r, o];
  };
  const toggle = (sect, key, after) => {
    const obj = sect ? pe[sect] : pe;
    const c = h("input", { type: "checkbox" }); c.checked = !!obj[key];
    c.addEventListener("change", () => { obj[key] = c.checked ? 1 : 0; if (after) after(); });
    return h("label", { class: "sw" }, c, h("span"));
  };
  if (custom) {
    const inp = h("input", { type: "text", maxlength: 24, value: slotName(prof, +name.slice(-1)) });
    inp.addEventListener("input", () => { pe.CustomizeName = inp.value; });
    row(t("Slot name"), t("Shown here, on the fan page and in notifications"), inp);
  }
  const W = t("W");
  // PL1 <= PL2 <= PL4: raising a lower limit pushes the higher ones up, a higher one cannot go below the lower one
  const plKeys = ["PL1", "PL2", "PL4"], plMax = { PL1: Math.min(L.pl1_max, L.pl2_max, L.pl4_max), PL2: Math.min(L.pl2_max, L.pl4_max), PL4: L.pl4_max };
  const plUI = {};
  const plSync = (changed) => {
    const i = plKeys.indexOf(changed), c = pe.CPU;
    for (let j = i + 1; j < 3; j++) c[plKeys[j]] = Math.max(c[plKeys[j]], c[plKeys[j - 1]]);
    if (i > 0) c[changed] = Math.max(c[changed], c[plKeys[i - 1]]);
    for (const k of plKeys) { plUI[k][0].value = c[k]; plUI[k][1].textContent = `${c[k]} ${W}`; }
  };
  for (const k of plKeys) {
    plUI[k] = slider("CPU", k, L.pl_min, plMax[k] >= L.pl_min ? plMax[k] : L[k.toLowerCase() + "_max"], W);
    plUI[k][0].addEventListener("input", () => plSync(k));
  }
  pe.CPU.PL2 = Math.max(pe.CPU.PL2, pe.CPU.PL1); pe.CPU.PL4 = Math.max(pe.CPU.PL4, pe.CPU.PL2);
  plSync("PL1");
  row(t("Long-term power limit (PL1)"), t("The power the processor holds under a long load"), ...plUI.PL1);
  row(t("Short-term power limit (PL2)"), t("For short bursts; not lower than PL1"), ...plUI.PL2);
  row(t("Peak power limit (PL4)"), t("The most the processor may draw for an instant; not lower than PL2"), ...plUI.PL4);
  let r, o;
  if (L.tcc_max > 0 && L.tjmax && !S.platform.amd) {
    // shown as a temperature (like "Temperature Limit" in the original); stored as TCC offset = Tjmax - limit
    const tj = L.tjmax, lo = tj - L.tcc_max;
    pe.CPU.TccOffset = Math.min(Math.max(pe.CPU.TccOffset, 0), L.tcc_max);
    const o2 = h("output", {}, `${tj - pe.CPU.TccOffset} °C`);
    const r2 = h("input", { type: "range", min: lo, max: tj, step: 1, value: tj - pe.CPU.TccOffset });
    r2.addEventListener("input", () => { pe.CPU.TccOffset = tj - +r2.value; o2.textContent = `${r2.value} °C`; });
    row(t("CPU temperature limit"), t("The processor slows down to stay at or below this temperature (maximum {0} °C). Lower = cooler and quieter, less performance.", tj),
      h("div", { class: "row", style: "flex:1" }, toggle("CPU", "TccOffsetSwitch"), r2), o2);
  } else if (L.tcc_max > 0) {
    [r, o] = slider("CPU", "TccOffset", 0, L.tcc_max, "°C");
    row(t("Lower the throttle temperature (TCC offset)"), t("The processor starts to cut its clock this many degrees below its maximum"), h("div", { class: "row", style: "flex:1" }, toggle("CPU", "TccOffsetSwitch"), r), o);
  }
  if (S.platform.nv_gpu && L.gpu_temp) {
    const gt = L.gpu_temp;
    if (pe.GPU.TargetTemperature == null) pe.GPU.TargetTemperature = gt.default;
    [r, o] = slider("GPU", "TargetTemperature", gt.min, gt.max, "°C");
    row(t("GPU temperature limit"), t("The graphics card lowers its clock to stay at this temperature (driver default {0} °C)", gt.default),
      h("div", { class: "row", style: "flex:1" }, toggle("GPU", "TargetTemperatureSwitch"), r), o);
  }
  if (S.platform.nv_gpu && (L.ctgp_support || L.db_support)) {
    if (L.ctgp_support) {
      [r, o] = slider("GPU", "ConfigurableTGPTarget", L.tgp_default, L.tgp_max + (pe.GPU.DynamicBoostSwitch ? 0 : L.db_max), W);
      row(t("Graphics power target (cTGP)"), t("The total power the graphics card may use"), h("div", { class: "row", style: "flex:1" }, toggle("GPU", "ConfigurableTGPSwitch"), r), o).dataset.feature = "gpu_power";
    }
    if (L.db_support) {
      [r, o] = slider("GPU", "DynamicBoost", 0, L.db_max, W);
      row(t("Dynamic Boost"), t("Lets the graphics card take power from the processor"), h("div", { class: "row", style: "flex:1" }, toggle("GPU", "DynamicBoostSwitch", () => renderProfileEditor(true)), r), o).dataset.feature = "gpu_power";
      if (dbStatus && dbStatus.service && !dbStatus.active) {
        const msg = dbStatus.present ? t("{0} is not running — Dynamic Boost has no effect until it is started.", dbStatus.service)
          : t("{0} is not installed — Dynamic Boost has no effect. Install it with the NVIDIA driver.", dbStatus.service);
        rows.append(h("div", { class: "pe-row" }, h("div", { class: "lbl" }, h("small", { class: "warn-text" }, msg)), h("div", { class: "val" },
          dbStatus.can_enable ? h("button", { class: "btn ghost", onclick: () => act(async () => { dbStatus = await api("dynamic-boost/enable", {}); renderProfileEditor(); }, t("Started")) }, t("Start")) : h("span")), h("span")));
      }
    }
  }
  if (typeof applyFeatures === "function" && S) applyFeatures();
}
$("#pe-apply").addEventListener("click", () => {
  if (!pe) return;
  const c = pe.CPU;
  const L = S.power.limits || {};
  if (c.PL2 < c.PL1) c.PL2 = c.PL1;
  if (c.PL4 < c.PL2) c.PL4 = c.PL2;
  const body = { CPU: { PL1: c.PL1, PL2: c.PL2, PL4: c.PL4, TccOffsetSwitch: c.TccOffsetSwitch, TccOffset: c.TccOffset },
    GPU: { ConfigurableTGPSwitch: pe.GPU.ConfigurableTGPSwitch, ConfigurableTGPTarget: pe.GPU.ConfigurableTGPTarget,
      DynamicBoostSwitch: pe.GPU.DynamicBoostSwitch, DynamicBoost: pe.GPU.DynamicBoost } };
  if (L.gpu_temp && S.platform.nv_gpu) Object.assign(body.GPU, { TargetTemperatureSwitch: pe.GPU.TargetTemperatureSwitch ? 1 : 0, TargetTemperature: pe.GPU.TargetTemperature });
  if (!S.platform.nv_gpu) delete body.GPU;
  if (pe.Name.startsWith("Mode4")) body.CustomizeName = pe.CustomizeName;
  act(async () => { await api("profiles/" + pe.Name, body, "PUT"); pe = null; }, t("Profile applied"));
});
$("#pe-reset").addEventListener("click", () => {
  if (!pe || !confirm(t("Reset “{0}” to the factory values? Its power limits and fan curve are replaced.", pe.Name.startsWith("Mode4") ? slotName(pe, +pe.Name.slice(-1)) : tableLabel(pe.FAN.TableName)))) return;
  act(async () => { await api("profile-reset/" + pe.Name, {}); pe = null; edit = null; }, t("Factory values restored"));
});

// ---------------------------------------------------------------- super performance + RAM overclocking (any mode)
function renderPerf() {
  const st = S.settings || {}, sp = S.power.super_performance !== undefined;
  $("#perf-card").classList.toggle("hidden", !sp && !st.mem_oc_support);
  $("#sp-row").classList.toggle("hidden", !sp);
  $("#super-perf").checked = !!S.power.super_performance;
  $("#mem-row").classList.toggle("hidden", !st.mem_oc_support);
  $("#mem-oc").checked = !!st.mem_oc;
  const ms = $("#mem-oc-state");
  ms.textContent = st.mem_oc_pending ? t("Restart to apply") : "";
  ms.className = "tiny warn-text";
}
$("#super-perf").addEventListener("change", e => act(() => api("setting", { key: "super_performance", value: e.target.checked }),
  e.target.checked ? t("Super performance on") : t("Super performance off")));
$("#mem-oc").addEventListener("change", e => act(() => api("setting", { key: "mem_oc", value: e.target.checked }),
  e.target.checked ? t("RAM overclocking is applied after a restart") : t("RAM overclocking is switched off after a restart")));
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
  // one line: the mode name once, then its slots as numbers (the full name is the tooltip)
  let group = null;
  for (const n of list) {
    const m = n[1], i = +n[3];
    if (m !== group) {
      group = m;
      seg.append(h("span", { class: "seg-label" }, m === "4" && isStd() ? t("Custom") : t(MODE_OF_PREFIX[m] || "?")));
    }
    seg.append(h("button", { class: (n === curTable ? "on" : "") + (n === S.power.current_table ? " active" : ""), title: TABLE_LABEL[n],
      onclick: () => { curTable = n; edit = null; renderFanPage(); } }, String(i)));
  }
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
  let dl = "";
  const dp = curveDrag != null ? pts.find(p => p.i === curveDrag) : null;
  if (dp) {                                       // while dragging: the point's temperature and speed next to it
    const x = CX(Math.max(20, dp.i === 0 ? 20 : dp.UpT)), y = CY(dp.Duty), right = x < 170, down = y < 45;
    dl = `<text class="draglbl" x="${right ? x + 12 : x - 12}" y="${down ? y + 28 : y - 14}" text-anchor="${right ? "start" : "end"}">${dp.i ? dp.UpT + " °C" : t("start")} · ${dp.Duty} %</text>`;
  }
  svg.innerHTML = g + `<path d="${path}" fill="none" stroke="${col}" stroke-width="2.5"/>` + circles + dl;
  drawCurveNow();
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
      const was = p.UpT;
      p.UpT = Math.max(lo, Math.min(hi, TX(x)));
      fanFollowDown(P, drag, was);
    }
    drawCurve(); drawPts();
  };
  svg.onpointerup = svg.onpointercancel = e => {
    if (curveDrag != null && svg.hasPointerCapture(e.pointerId)) svg.releasePointerCapture(e.pointerId);
    const was = curveDrag; curveDrag = null;
    if (was != null) drawCurve();
  };
}
// red dot: the fan's current temperature and speed, on the table that is active now (needs full monitoring)
function drawCurveNow() {
  const svg = $("#curve"); if (!svg) return;
  svg.querySelectorAll(".now").forEach(x => x.remove());
  const m = lastMonitor;
  if (!m || !S || curTable !== S.power.current_table || curveDrag != null) return;
  const gpu = fanKind === "GPU";
  const temp = gpu ? (m.gpu && !m.gpu.asleep ? m.gpu.temp : null) : m.cpu && m.cpu.temp;
  const duty = gpu ? m.fans.gpu_duty : m.fans.cpu_duty, rpm = gpu ? m.fans.gpu_rpm : m.fans.cpu_rpm;
  if (temp == null || duty == null) return;
  // the dot lies on the curve at this sensor's temperature; the label has the real speed. When the fan runs clearly
  // faster than its own curve, the EC drives it by the other side (on many models both fans follow the hotter one).
  const pts = activePts(); let lvl = pts[0];
  for (const p of pts) if (p.i === 0 || p.UpT <= temp) lvl = p;
  const own = lvl ? lvl.Duty : duty;
  const x = CX(Math.max(20, Math.min(100, temp))), y = CY(Math.max(0, Math.min(100, own)));
  const by = duty > own + 3 ? " " + t("(driven by {0})", gpu ? "CPU" : "GPU") : "";
  const label = `${temp} °C · ${rpm != null ? rpm + " " + t("rpm") : duty + " %"}${by}`;
  const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  c.setAttribute("class", "now"); c.setAttribute("r", "6"); c.setAttribute("cx", x); c.setAttribute("cy", y);
  const tt = document.createElementNS("http://www.w3.org/2000/svg", "title");
  tt.textContent = t("Now: {0} °C · {1} %", temp, duty) + (rpm != null ? ` · ${rpm} ${t("rpm")}` : "") + by; c.append(tt);
  const tx = document.createElementNS("http://www.w3.org/2000/svg", "text"), left = x > 470, up = y > 246;
  tx.setAttribute("class", "now nowlbl"); tx.setAttribute("x", left ? x - 10 : x + 10); tx.setAttribute("y", up ? y - 12 : y + 22);
  tx.setAttribute("text-anchor", left ? "end" : "start"); tx.textContent = label;
  svg.append(c, tx);
}
function drawPts() {
  const tb = $("#pts"); tb.innerHTML = "";
  const P = edit[fanKind];
  const head = h("tr", {}, h("th", {}, t("Level")), ...P.map((_, i) => h("th", {}, i)));
  const row = (label, f, help) => h("tr", {}, h("th", { title: help }, label), ...P.map((p, i) => {
    const unused = p.Duty > 100 || (i > 0 && (p.UpT >= 255 || p.UpT === 0));
    const inp = h("input", { type: "number", min: 0, max: 255, value: p[f], disabled: f === "UpT" && i === 0 });
    inp.addEventListener("change", () => {
      const was = p[f]; p[f] = Math.max(0, Math.min(255, parseInt(inp.value || "0", 10)));
      if (f === "UpT" && i > 0) fanFollowDown(P, i, was);
      drawCurve(); drawPts();
    });
    return h("td", { class: unused ? "na" : "" }, inp);
  }));
  tb.append(head, row(t("On, °C"), "UpT", t("Temperature to enter this level (255 — unused)")),
    ...(fanShowDown ? [row(t("Off, °C"), "DownT", t("Temperature to return to the previous level"))] : []),
    row(t("Speed, %"), "Duty", t("Fan speed (255 — level unused)")));
  $("#pts-down").checked = fanShowDown;
}
// "Off, °C" (DownT of level i) is where the fan drops back from level i+1 to level i. It is not edited by hand any more:
// it follows the next level's "On" and keeps its distance to it (factory tables: equal, or a wider gap at level 0).
let fanShowDown = false;
try { fanShowDown = !!localStorage.getItem("uwcc-fan-down"); } catch (_) {}
$("#pts-down").addEventListener("change", e => {
  fanShowDown = e.target.checked; try { localStorage.setItem("uwcc-fan-down", fanShowDown ? "1" : ""); } catch (_) {}
  if (edit) drawPts();
});
function fanFollowDown(P, j, wasUp) {
  const prev = P[j - 1]; if (!prev) return;
  const gap = prev.DownT > 0 && prev.DownT < 255 && prev.DownT <= wasUp && wasUp < 255 ? wasUp - prev.DownT : 0;
  prev.DownT = P[j].UpT >= 255 ? 255 : Math.max(0, P[j].UpT - gap);
}
function fanFixDown(P) {                   // before Save: every active level returns at or below the next level's "On"
  const act = P.map((p, i) => i).filter(i => P[i].Duty <= 100 && (i === 0 || (P[i].UpT > 0 && P[i].UpT < 255)));
  act.forEach((i, k) => {
    const nx = act[k + 1];
    if (nx === undefined) P[i].DownT = 255;
    else if (P[i].DownT >= 255 || P[i].DownT > P[nx].UpT) P[i].DownT = P[nx].UpT;
  });
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
  fanFixDown(edit.CPU); fanFixDown(edit.GPU);
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
  if (k.effect) {
    const e = k.effect;
    kbSel = { ...kbSel, effect: e.idx, light: e.light };
    for (const key of ["speed", "direction", "circular"]) if (e[key] !== undefined) kbSel[key] = e[key];
    if (e.colors?.length) kbSel.colors = e.colors; if (e.user) userBuf = e.user;
    if (e.fx) { fxParams[e.idx] = e.fx; kbSel.fx = e.fx; }
  }
  const eb = $("#effects"); eb.innerHTML = "";
  const fb = k.feedback || {};
  for (const [id, name] of Object.entries(k.effects)) {
    const grey = (k.unsupported_effects || []).includes(+id);
    const untested = grey && (k.untested_effects || []).includes(+id);    // greyed, but may be tried
    const na = grey && !untested;
    const why = grey ? (+id === 13 ? t("Music mode needs audio capture — not supported") : k.four_zone ? t("Not available on this keyboard")
      : (+id === 14 || +id === 15) ? t("Not supported by this keyboard firmware") : t("Light bar only effect")) : "";
    const verdict = fb[id] ? (fb[id].works ? " ✓" : " ✕") : "";
    const title = untested ? why + " — " + t("not checked on this keyboard; click to try") + (verdict ? " · " + t(fb[id].works ? "you said: works" : "you said: does not work") : "") : why;
    eb.append(h("div", { class: `eff${+id === kbSel.effect ? " on" : ""}${na ? " na" : ""}${untested ? (k.untested_unlocked ? " untested" : " na untested") : ""}`, title,
      onclick: () => {
        if (na) return toast(t("This effect is not available for this keyboard"), true);
        if (untested) return tryUntested(+id, name);
        if (+id === 2 && kbSel.effect !== 2) kbSel.circular = true;      // Wave: all palette colours by default
        kbSel.effect = +id; hideKbFeedback(); applyKb();
      } },
      h("div", { class: "sw8" }), t(EFFECT_NAME[name] || name) + verdict));
  }
  $("#kb-unlock").checked = !!k.untested_unlocked;
  $("#kb-unlock-row").classList.toggle("hidden", !(k.untested_effects || []).length);
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
  renderFx(k);
}
function applyKb() {
  if (kbSel.effect >= 100) return act(() => api("keyboard/effect", { effect: kbSel.effect, light: kbSel.light, fx: kbSel.fx || fxDefaults(kbSel.effect) }));
  const body = { ...kbSel };
  delete body.fx;
  if ((S.keyboard.untested_effects || []).includes(kbSel.effect)) body.untested = true;
  if (kbSel.circular) body.colors = S.keyboard.default_colors;
  if (kbSel.effect === 14) body.user = userBuf;
  if (kbSel.effect === 20) body.alphabet = $("#kb-alpha").value || "HELLO";
  act(() => api("keyboard/effect", body));
}
$("#kb-power").addEventListener("change", e => act(() => api("keyboard/power", { on: e.target.checked })));

// -- untested effects: unlock (switch), ask before the first try, then "does it work?"
function askUntested(name) {          // -> "once" | "always" | null
  return new Promise(res => {
    const close = v => { box.remove(); res(v); };
    const box = h("div", { class: "eula", role: "dialog", "aria-modal": "true" },
      h("div", { class: "eula-card ask-card" },
        h("h3", {}, t("Try “{0}”?", t(EFFECT_NAME[name] || name))),
        h("p", {}, t("This effect is not offered for this keyboard by the original Control Center and has not been checked on it. The keyboard may draw it, ignore it or show something else; nothing is stored in the controller — choose another effect or switch the backlight off and on to go back.")),
        h("div", { class: "row end wrap" },
          h("button", { class: "btn ghost", onclick: () => close(null) }, t("Cancel")),
          h("button", { class: "btn ghost", onclick: () => close("always") }, t("Yes, do not ask again")),
          h("button", { class: "btn", onclick: () => close("once") }, t("Try it")))));
    box.addEventListener("keydown", e => { if (e.key === "Escape") close(null); });
    document.body.append(box); box.querySelector(".btn:last-child").focus();
  });
}
async function tryUntested(id, name) {
  const k = S.keyboard;
  if (k.untested_ask) {
    const a = await askUntested(name);
    if (!a) return;
    if (a === "always") await api("setting", { key: "kb_untested_no_ask", value: true }).catch(() => {});
  }
  kbSel.effect = id; applyKb();
  showKbFeedback(id, name);
}
function showKbFeedback(id, name) {
  const bar = $("#kb-feedback"); bar.innerHTML = "";
  const answer = works => act(async () => { await api("keyboard/feedback", { effect: id, works }); hideKbFeedback(); },
    t("Thank you — the answer is kept for the diagnostic report"));
  bar.append(h("span", {}, t("Does “{0}” work on this keyboard?", t(EFFECT_NAME[name] || name))),
    h("button", { class: "btn sm", onclick: () => answer(true) }, "✓ " + t("Yes")),
    h("button", { class: "btn ghost sm", onclick: () => answer(false) }, "✕ " + t("No")),
    h("button", { class: "btn ghost sm", onclick: hideKbFeedback }, t("Later")));
  bar.classList.remove("hidden");
}
function hideKbFeedback() { $("#kb-feedback").classList.add("hidden"); }
$("#kb-unlock").addEventListener("change", e => act(() => api("setting", { key: "kb_unlock_effects", value: e.target.checked }),
  e.target.checked ? t("Untested effects unlocked") : t("Untested effects locked again")));

// ---------------------------------------------------------------- BetterRGB effects (drawn by the service)
const fxParams = {};                         // effect id -> the parameters last used
const FX_LABEL = { speed: "Speed", smooth: "Smoothness", random: "Random colours", colors: "Colours", angle: "Angle, °",
  density: "Density", duration: "Afterglow", reverse: "Reverse direction", width: "Width", concurrent: "Strikes at once",
  color_count: "Number of colours", style: "Style", layout: "Layout", zones: "Zones", scale: "Scale", blur: "Blur",
  response: "Response" };
const FX_CHOICE = { short: "short", medium: "medium", long: "long", streaks: "streaks", columns: "columns", lasers: "lasers",
  ripples: "ripples", horizontal: "horizontal (rows)", vertical: "vertical (columns)" };
const FX_TRANS = { off: "Off", fade: "Fade", ripple_center: "Ripple from the centre", ripple_edges: "Ripple from the edges",
  ripple_top: "Wipe from the top", ripple_bottom: "Wipe from the bottom", ripple_left: "Wipe from the left", ripple_right: "Wipe from the right",
  snake_main_out_in: "Twin spiral ↘, inwards", snake_main_in_out: "Twin spiral ↘, outwards", snake_anti_out_in: "Twin spiral ↙, inwards",
  snake_anti_in_out: "Twin spiral ↙, outwards" };
const FX_BAR = { off: "Nothing", battery: "Battery charge", volume: "Volume", mic: "Microphone level (Windows)", cpu: "CPU load",
  gpu: "GPU load", audio: "Playback level (Windows)" };
const FX_DIR = { left_to_right: "left to right", right_to_left: "right to left", edges_to_center: "from the edges to the centre",
  center_to_edges: "from the centre to the edges" };
function fxDefaults(id) {
  const c = S.keyboard.fx_effects[id]; const p = {};
  for (const q of c.params) p[q.key] = JSON.parse(JSON.stringify(q.default));
  return p;
}
const rgb2hex = c => "#" + c.map(v => Math.max(0, Math.min(255, v | 0)).toString(16).padStart(2, "0")).join("");
function renderFx(k) {
  const fb = $("#fx-effects"); fb.innerHTML = "";
  for (const [id, c] of Object.entries(k.fx_effects || {})) {
    const off = c.needs.includes("screen") && !k.fx_screen_allowed;          // Linux: Screen ambient is off by default
    const tip = off ? t("Off on Linux by default — turn it on below in BetterRGB engine") : c.needs.includes("keys") ? t("Reacts to key presses") : c.needs.includes("screen") ? t("Follows the colours of the screen") : "";
    fb.append(h("div", { class: `eff${+id === kbSel.effect ? " on" : ""}${off ? " na" : ""}`, title: tip,
      onclick: () => {
        if (off) return toast(t("Screen ambient is off on Linux — turn it on in BetterRGB engine"), true);
        kbSel.effect = +id; kbSel.fx = fxParams[id] || fxDefaults(id); applyKb();
      } },
      h("div", { class: "sw8" }), t(c.name)));
  }
  const isFx = kbSel.effect >= 100 && k.fx_effects && k.fx_effects[kbSel.effect];
  $("#fx-card").classList.toggle("hidden", !isFx);
  for (const id of ["kb-speed-row", "kb-dir-row", "kb-colour-card"]) $("#" + id).classList.toggle("hidden", !!isFx);
  if (isFx) drawFxParams(k);
  renderFxEngine(k);
}
function drawFxParams(k) {
  const c = k.fx_effects[kbSel.effect];
  const p = kbSel.fx = { ...fxDefaults(kbSel.effect), ...(kbSel.fx || {}) };
  const box = $("#fx-params"); box.innerHTML = "";
  const needs = $("#fx-needs");
  const note = c.needs.includes("keys") ? (S.platform.os === "windows" ? t("Reacts to key presses: the Control Center tray program sends them to the service while this effect runs (nothing is stored).")
      : t("Reacts to key presses: the service reads them from the keyboard while this effect runs (nothing is stored)."))
    : c.needs.includes("screen") ? (S.platform.os === "windows" ? t("Follows the screen: the tray program sends a 64×24 picture of the main screen 15 times a second while this effect runs (it is not stored).")
      : t("Follows the screen: the session agent sends a 64×24 picture of the screen while this effect runs (X11 only; not on Wayland; it is not stored)."))
    : "";
  needs.textContent = note; needs.classList.toggle("hidden", !note);
  if (k.four_zone) { needs.textContent = (note ? note + " " : "") + t("On a four-zone keyboard each zone shows the average of its keys."); needs.classList.remove("hidden"); }
  const send = () => { fxParams[kbSel.effect] = p; applyKb(); };
  for (const q of c.params) {
    const label = t(FX_LABEL[q.key] || q.key);
    if (q.kind === "int") {
      const inp = h("input", { type: "range", min: q.min, max: q.max, step: 1, value: p[q.key] });
      const out = h("output", {}, String(p[q.key]));
      inp.addEventListener("input", () => { out.textContent = inp.value; });
      inp.addEventListener("change", () => { p[q.key] = +inp.value; send(); });
      box.append(h("label", { class: "slider" }, h("span", {}, label), inp, out));
    } else if (q.kind === "bool") {
      const inp = h("input", { type: "checkbox" }); inp.checked = !!p[q.key];
      inp.addEventListener("change", () => { p[q.key] = inp.checked; send(); });
      box.append(h("label", { class: "chk" }, inp, h("span", {}, " " + label)));
    } else if (q.kind === "choice") {
      const sel = h("select", {}, ...q.options.map(o => { const e = h("option", { value: o }, t(FX_CHOICE[o] || o)); if (o === p[q.key]) e.selected = true; return e; }));
      sel.addEventListener("change", () => { p[q.key] = sel.value; send(); });
      box.append(h("label", { class: "slider" }, h("span", {}, label), sel));
    } else if (q.kind === "colors") {
      if (q.key === "colors" && p.random) continue;                    // random colours: the colour is not used
      const n = p.color_count ? Math.min(q.max, p.color_count) : p.zones ? Math.min(q.max, p.zones) : q.max;
      const cols = p[q.key] = (p[q.key] || []).slice(0, q.max);
      while (cols.length < q.max) cols.push([255, 255, 255]);
      const row = h("div", { class: "row wrap" }, h("span", { class: "muted tiny" }, label));
      for (let i = 0; i < n; i++) {
        const inp = h("input", { type: "color", value: rgb2hex(cols[i]) });
        inp.addEventListener("change", () => { cols[i] = hex2rgb(inp.value); send(); });
        row.append(inp);
      }
      box.append(row);
    }
  }
}
function fxCfg(body) { return act(() => api("keyboard/fx/config", body)); }
function renderFxEngine(k) {
  const c = k.fx_config; if (!c) return;
  const setRange = (id, v) => { const e = $("#" + id); if (document.activeElement === e) return; e.value = v; e.nextElementSibling.textContent = v; };
  setRange("fx-fps-ac", c.fps_ac); setRange("fx-fps-bat", c.fps_battery); setRange("fx-trans-ms", c.transition_ms);
  const fill = (id, list, names, cur) => { const sel = $("#" + id); sel.innerHTML = ""; for (const v of list) { const o = h("option", { value: v }, t(names[v] || v)); if (v === cur) o.selected = true; sel.append(o); } };
  fill("fx-trans", k.fx_transitions, FX_TRANS, c.transition);
  fill("fx-bar-mode", k.fx_bar_modes, FX_BAR, c.bar.mode);
  fill("fx-bar-dir", k.fx_bar_directions, FX_DIR, c.bar.direction);
  $("#fx-bar-start").value = rgb2hex(c.bar.start); $("#fx-bar-end").value = rgb2hex(c.bar.end);
  $$("#fx-bar-audio input").forEach(i => { i.value = rgb2hex(c.bar.audio[+i.dataset.a]); });
  $("#fx-bar-audio").classList.toggle("hidden", c.bar.mode !== "audio");
  $("#fx-bar-box").classList.toggle("hidden", !!k.four_zone);
  $("#fx-screen-row").classList.toggle("hidden", !k.fx_screen_switch);
  $("#fx-screen").checked = !!k.fx_screen_allowed;
  const g = c.gains;
  $("#fx-gains").textContent = g.every(x => x === 1000) ? t("Calibration: none (neutral)") : t("Calibration: red {0} %, green {1} %, blue {2} %", g[0] / 10, g[1] / 10, g[2] / 10);
  const cal = !!(k.fx && k.fx.calibrating);
  $("#fx-cal-idle").classList.toggle("hidden", cal); $("#fx-cal-run").classList.toggle("hidden", !cal);
  $("#fx-status").textContent = k.fx ? t("Running: {0} — {1} of {2} frames per second", t(k.fx.name), k.fx.fps ?? "—", k.fx.target_fps ?? "—")
    : t("No BetterRGB effect is running — the settings apply when one is chosen.");
}
for (const [id, key] of [["fx-fps-ac", "fps_ac"], ["fx-fps-bat", "fps_battery"], ["fx-trans-ms", "transition_ms"]]) {
  $("#" + id).addEventListener("input", e => { e.target.nextElementSibling.textContent = e.target.value; });
  $("#" + id).addEventListener("change", e => fxCfg({ [key]: +e.target.value }));
}
$("#fx-trans").addEventListener("change", e => fxCfg({ transition: e.target.value }));
$("#fx-screen").addEventListener("change", e => act(() => api("setting", { key: "kb_fx_screen", value: e.target.checked })));
$("#fx-bar-mode").addEventListener("change", e => fxCfg({ bar: { mode: e.target.value } }));
$("#fx-bar-dir").addEventListener("change", e => fxCfg({ bar: { direction: e.target.value } }));
$("#fx-bar-start").addEventListener("change", e => fxCfg({ bar: { start: hex2rgb(e.target.value) } }));
$("#fx-bar-end").addEventListener("change", e => fxCfg({ bar: { end: hex2rgb(e.target.value) } }));
$$("#fx-bar-audio input").forEach(i => i.addEventListener("change", () => fxCfg({ bar: { audio: $$("#fx-bar-audio input").map(x => hex2rgb(x.value)) } })));
$("#fx-cal-start").addEventListener("click", () => act(() => api("keyboard/fx/calibrate", { action: "start" }), t("The keys show raw white now — pick the colour you see")));
$("#fx-cal-apply").addEventListener("click", () => act(() => api("keyboard/fx/calibrate", { action: "apply", observed: hex2rgb($("#fx-cal-color").value) }), t("Calibration saved")));
$("#fx-cal-cancel").addEventListener("click", () => act(() => api("keyboard/fx/calibrate", { action: "cancel" })));
$("#fx-cal-reset").addEventListener("click", () => act(() => api("keyboard/fx/calibrate", { action: "reset" }), t("Calibration reset")));

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
// ---------------------------------------------------------------- Control Center 3.0 / Clevo (experimental, uwccd/clevo)
const CLEVO_POWER = [["quiet", "Silent", "Low noise, lower performance"], ["powersave", "Power saving", "Longest battery time"],
  ["performance", "Performance", "Highest performance"], ["entertainment", "Entertainment", "Balanced"]];
const CLEVO_FAN = { auto: "Automatic", max: "Maximum", maxq: "Max-Q", custom: "Custom" };
const CLEVO_FX = { random: "Random", breathe: "Breathing", cycle: "Cycle", wave: "Wave", dance: "Dance", tempo: "Tempo", flash: "Flashing" };
const CLEVO_FAN_NAME = { cpu: "Processor fan", gpu1: "Graphics card fan", gpu2: "Graphics card fan 2" };
const CLEVO_SLEEP = [[0, "Never"], [15, "15 s"], [30, "30 s"], [60, "1 min"], [180, "3 min"], [300, "5 min"], [600, "10 min"]];
let clevoTimer = null, clevoCurve = null;
function clevoCmd(body, ok) { return act(() => api("clevo", body), ok); }
function clevoFans(c) {
  const box = h("div", { class: "clevo-fans", id: "clevo-fans" });
  for (const f of c.fans || []) box.append(h("div", { class: "clevo-fan" }, h("small", {}, t(CLEVO_FAN_NAME[f.fan] || f.fan)),
    h("b", {}, `${f.rpm} ${t("rpm")}`), h("small", {}, `${f.duty}% · ${f.temp != null ? f.temp + " °C" : "—"}`)));
  if (c.fans_error) box.append(h("p", { class: "muted" }, c.fans_error));
  return box;
}
async function clevoPoll() {
  if (!$("#page-clevo").classList.contains("active") || !S || !S.clevo || !S.clevo.present) return;
  try { const c = await api("clevo"); const old = $("#clevo-fans"); if (old) old.replaceWith(clevoFans(c)); } catch (_) {}
}
function renderClevo() {
  const c = S.clevo || {}, on = !!c.present;
  $("#nav-clevo").classList.toggle("hidden", !on); $("#nav-clevo-group").classList.toggle("hidden", !on);
  if (!clevoTimer) clevoTimer = setInterval(clevoPoll, 2000);
  const root = $("#clevo-root"); if (!root) return;
  root.innerHTML = "";
  if (!on) { $("#clevo-sub").textContent = ""; root.append(h("div", { class: "card" }, h("p", {}, t("No Control Center 3.0 / Clevo interface on this laptop.")))); return; }
  const st = c.state || {}, kb = st.kb || {}, caps = c.caps || {}, locked = !c.writes;
  $("#clevo-sub").replaceChildren(t("Separate module for laptops with Control Center 3.x · via {0}", c.transport === "windows-cc3-driver" ? t("the Control Center 3 driver") : c.transport === "uwcc-module" ? t("the uwcc kernel module") : c.transport),
    c.ec_version ? ` · EC ${c.ec_version}` : "", h("span", { class: "clevo-exp" }, t("experimental")));
  const sw = (checked, fn) => h("label", { class: "sw" }, h("input", { type: "checkbox", ...(checked ? { checked: true } : {}), onchange: e => fn(e.target.checked) }), h("span"));
  // access
  root.append(h("div", { class: "card warn" }, h("h3", {}, t("Experimental commands")),
    h("p", { class: "muted" }, t("These functions talk to the firmware the way Control Center 3 does. They were written from the interface description and have not been tested on a Clevo laptop yet. The firmware does not report the current power mode, fan mode or backlight, so the values below are the ones last set here.")),
    h("div", { class: "clevo-row" }, h("span", {}, t("Allow commands")), sw(c.writes, v => act(() => api("setting", { key: "clevo_writes", value: v })))),
    h("div", { class: "clevo-row" }, h("span", {}, t("Send the saved settings at start")), sw(c.restore, v => act(() => api("setting", { key: "clevo_restore", value: v })))),
    h("p", { class: "muted tiny" }, t("Close Control Center 3 while using this page: both programs would send commands. Its driver must stay installed (Windows)."))));
  // power modes
  if (caps.power_modes !== false) {
    const box = h("div", { class: "choices clevo-cmd" });
    for (const [id, name, desc] of CLEVO_POWER) box.append(h("div", { class: "choice" + (st.power_mode === id ? " on" : ""), onclick: () => clevoCmd({ action: "power_mode", mode: id }, t(name)) }, h("h4", {}, t(name)), h("p", {}, t(desc))));
    root.append(h("div", { class: "card" + (locked ? " locked" : "") }, h("h3", {}, t("Power mode")), box));
  }
  // fans
  const fc = h("div", { class: "card" + (locked ? " locked" : "") }, h("h3", {}, t("Fans")), clevoFans(c));
  const seg = h("div", { class: "seg clevo-cmd" });
  for (const m of c.fan_modes || []) seg.append(h("button", { class: st.fan_mode === m ? "on" : "", onclick: () => clevoCmd({ action: "fan_mode", mode: m }, t(CLEVO_FAN[m] || m)) }, t(CLEVO_FAN[m] || m)));
  fc.append(h("div", { class: "clevo-row" }, h("span", {}, t("Fan mode")), seg));
  if (caps.fan_offset !== false) {
    const out = h("output", {}, `${st.fan_offset ?? 0}%`);
    fc.append(h("div", { class: "clevo-row clevo-cmd" }, h("span", {}, t("Fan offset")),
      h("input", { type: "range", min: 0, max: 100, step: 5, value: st.fan_offset ?? 0, oninput: e => { out.textContent = e.target.value + "%"; }, onchange: e => clevoCmd({ action: "fan_offset", value: +e.target.value }) }), out));
  }
  const tbl = (c.fan_table || {}).curves || {};
  if ((c.fan_modes || []).includes("custom") && Object.keys(tbl).length) {
    clevoCurve = clevoCurve || JSON.parse(JSON.stringify(st.curve || Object.fromEntries(Object.entries(tbl).map(([k, v]) => [k, v.slice(0, 3)]))));
    const g = h("div", { class: "clevo-curve clevo-cmd" }, h("span"), ...[1, 2, 3].map(i => h("span", { class: "muted" }, t("Point {0}: °C / %", i))));
    for (const fan of Object.keys(tbl)) {
      const pts = clevoCurve[fan] || tbl[fan].slice(0, 3);
      clevoCurve[fan] = pts;
      g.append(h("span", {}, t(CLEVO_FAN_NAME[fan] || fan)));
      pts.forEach((p, i) => g.append(h("span", {}, ...[0, 1].map(k => h("input", { type: "number", min: 0, max: k ? 100 : 99, value: p[k], disabled: i === 0, title: i === 0 ? t("Factory point") : "",
        onchange: e => { pts[i][k] = +e.target.value; } })))));
    }
    fc.append(h("h4", {}, t("Custom curve")), h("p", { class: "muted tiny" }, t("The first point is the factory one; above the third point the fan rises to 100 % at 100 °C.")), g,
      h("div", { class: "row clevo-cmd" }, h("button", { class: "btn", onclick: () => clevoCmd({ action: "curve", curves: clevoCurve }, t("Curve applied")) }, t("Apply curve")),
        h("button", { class: "btn ghost", onclick: () => { clevoCurve = null; clevoCmd({ action: "fan_defaults" }, t("Factory curve")); } }, t("Factory curve"))));
  }
  if (caps.anti_dust) fc.append(h("div", { class: "row clevo-cmd", style: "margin-top:10px" }, h("button", { class: "btn ghost", onclick: () => clevoCmd({ action: "anti_dust" }, t("Anti-dust started")) }, t("Anti-dust cycle"))));
  root.append(fc);
  // keyboard
  const kc = h("div", { class: "card" + (locked ? " locked" : "") }, h("h3", {}, t("Keyboard backlight")),
    h("div", { class: "clevo-row clevo-cmd" }, h("span", {}, t("Backlight")), sw(kb.on !== false, v => clevoCmd({ action: "kb_power", on: v }))));
  const cur = kb.color || [255, 255, 255], hex = "#" + cur.map(x => x.toString(16).padStart(2, "0")).join("");
  const sws = h("div", { class: "swatches" });
  for (const col of [[255, 0, 0], [255, 120, 0], [255, 255, 0], [0, 255, 0], [0, 255, 255], [0, 0, 255], [160, 0, 255], [255, 255, 255]])
    sws.append(h("div", { class: "swatch" + (!kb.effect && cur.join() === col.join() ? " on" : ""), style: `background:rgb(${col})`, onclick: () => clevoCmd({ action: "kb_color", color: col }) }));
  kc.append(h("div", { class: "clevo-row clevo-cmd" }, h("span", {}, t("Colour")), sws,
    h("input", { type: "color", value: hex, onchange: e => clevoCmd({ action: "kb_color", color: e.target.value }) })));
  const bo = h("output", {}, kb.brightness ?? "—");
  kc.append(h("div", { class: "clevo-row clevo-cmd" }, h("span", {}, t("Brightness")),
    h("input", { type: "range", min: 0, max: 255, step: 5, value: kb.brightness ?? 255, oninput: e => { bo.textContent = e.target.value; }, onchange: e => clevoCmd({ action: "kb_brightness", value: +e.target.value }) }), bo));
  const fx = h("select", { onchange: e => e.target.value && clevoCmd({ action: "kb_effect", effect: e.target.value }) }, h("option", { value: "" }, t("— single colour —")));
  for (const id of c.kb_effects || []) fx.append(h("option", { value: id, ...(kb.effect === id ? { selected: true } : {}) }, t(CLEVO_FX[id] || id)));
  kc.append(h("div", { class: "clevo-row clevo-cmd" }, h("span", {}, t("Firmware effect")), fx));
  const sl = h("select", { onchange: e => clevoCmd({ action: "kb_sleep", seconds: +e.target.value }) });
  for (const [v, n] of CLEVO_SLEEP) sl.append(h("option", { value: v, ...((kb.sleep ?? 0) === v ? { selected: true } : {}) }, t(n)));
  kc.append(h("div", { class: "clevo-row clevo-cmd" }, h("span", {}, t("Turn off after")), sl));
  kc.append(h("div", { class: "clevo-row clevo-cmd" }, h("span", {}, t("Colour cycle at power-on")), sw(!kb.boot_effect_off, v => clevoCmd({ action: "boot_effect", off: !v }))));
  root.append(kc);
  // capabilities
  const dl = h("dl", { class: "kv" });
  for (const [k, v] of Object.entries(c.caps_raw || {})) dl.append(h("dt", {}, `DCHU ${k}`), h("dd", {}, "0x" + (v >>> 0).toString(16).toUpperCase().padStart(8, "0")));
  dl.append(h("dt", {}, t("Capabilities")), h("dd", {}, Object.entries(caps).filter(([, v]) => v).map(([k]) => k).join(", ") || "—"));
  root.append(h("div", { class: "card" }, h("h3", {}, t("Firmware capabilities")), dl,
    h("p", { class: "muted tiny" }, t("A diagnostic report (Information) includes these values: it helps to test this module."))));
}
$(`#nav a[data-page="clevo"]`)?.addEventListener("click", () => setTimeout(clevoPoll, 50));

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
  item("Record sensor history", "Charts on the Monitor page: 15 minutes every 2 s, an hour every 5 s, 24 hours as per-minute averages (kept on disk). Turn off to stop recording.", "history_record", s.history_record);
  item("Check for updates automatically", "Once a day the service asks GitHub for the latest release of open-uniwill-cc. Nothing else is sent.", "update_check", s.update_check);
  if (S.keyboard && S.keyboard.picture_modes_switch) {
    const c = h("input", { type: "checkbox" }); c.checked = !S.keyboard.picture_modes_blocked;
    c.addEventListener("change", () => act(() => api("setting", { key: "kb_picture_modes", value: c.checked })));
    L.append(h("div", { class: "item" }, h("div", {}, h("h4", {}, t("Per-key keyboard pictures")),
      h("p", {}, t("Single colour, User mode, Gaming and the software effects (Neon, Stack, Impact, Alphabet) are drawn key by key, as in the original Control Center. Turn off if the keyboard ignores them: single colour then uses the firmware effect and the others are hidden."))), h("label", { class: "sw" }, c, h("span"))));
  }
  if (S.power && S.power.limits && S.power.limits.tjmax && !S.platform.amd)
    item("Extended CPU temperature limit range", "Allow a CPU temperature limit down to 60 °C in the profiles (default: down to 85 °C).", "tcc_extended", s.tcc_extended);
  if (S.power && S.power.manager) {
    const auto = S.platform.commercial ? "cml" : "std";
    const names = { cml: t("Commercial (_CML): Office / Gaming / Turbo"), std: t("RamFan 1.5: Office / Gaming / Turbo / Custom") };
    const fm = h("select", {}, ...[["auto", t("Automatic by project — {0}", names[auto])], ["cml", names.cml], ["std", names.std]]
      .map(([v, txt]) => { const o = h("option", { value: v }, txt); if ((s.fan_manager || "auto") === v) o.selected = true; return o; }));
    fm.addEventListener("change", () => {
      if (!confirm(t("Change the fan manager? The service restarts; fan control is handed to the laptop for a few seconds."))) { fm.value = s.fan_manager || "auto"; return; }
      act(() => api("setting", { key: "fan_manager", value: fm.value }), t("The service is restarting…"));
    });
    L.append(h("div", { class: "item" }, h("div", {}, h("h4", {}, t("Fan manager")),
      h("p", {}, t("How modes, profiles and fan tables are driven. The original Control Center picks it by the project; change it only if modes or fan curves do not work on your laptop. Now running: {0}.", names[S.power.manager] || S.power.manager))), fm));
  }
  const sel = h("select", {}, ...[[0, t("Never")], [10, t("{0} seconds", 10)], [30, t("{0} seconds", 30)], [60, t("1 minute")], [300, t("{0} minutes", 5)], [600, t("{0} minutes", 10)]].map(([v, txt]) => { const o = h("option", { value: v }, txt); if (+s.kb_timeout === v) o.selected = true; return o; }));
  sel.addEventListener("change", () => act(() => api("setting", { key: "kb_timeout", value: +sel.value })));
  L.append(h("div", { class: "item" }, h("div", {}, h("h4", {}, t("Keyboard backlight auto-off")), h("p", {}, t("Turn the backlight off after inactivity and back on when a key is pressed."))), sel));
  // EC light bar trigger (older models); hidden when the light bar is an ITE device with its own page
  if ((S.platform.rgb_lightbar || s.lightbar_on) && !(S.keyboard && S.keyboard.lightbar)) L.append(h("div", { class: "item" }, h("div", {}, h("h4", {}, t("Light bar")), h("p", {}, t("Click to turn the LED bar on/off."))), h("button", { class: "btn ghost", onclick: () => act(() => api("setting", { key: "lightbar_trigger", value: true })) }, s.lightbar_on ? t("Turn off") : t("Turn on"))));
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
$("#rep-debug").addEventListener("change", e => act(() => api("setting", { key: "debug", value: e.target.checked }),
  e.target.checked ? t("Debug logging on") : t("Debug logging off")));
function renderInfo() {
  if (S.settings) $("#rep-debug").checked = !!S.settings.debug;
  const i = S.info, p = S.platform;
  const dl = (el, rows) => { el.innerHTML = ""; for (const [k, v] of rows) el.append(h("dt", {}, k), h("dd", {}, v ?? "—")); };
  const lc = S.liquid || {};
  dl($("#info-dev"), [[t("Manufacturer"), i.vendor], [t("Model"), i.product], [t("Board"), i.board], ["BIOS", i.bios ? `${i.bios}${i.bios_date ? ` (${i.bios_date})` : ""}` : null], ["EC", i.ec],
    [t("Processor"), i.cpu], [t("Memory"), `${(i.memory.total_mb / 1024).toFixed(1)} ${t("GB")}`], [t(p.os === "windows" ? "Operating system" : "Linux kernel"), i.kernel]]);
  dl($("#info-svc"), [[t("Project (Project ID)"), `${p.display_name || p.project_name} (0x${p.project_id.toString(16).toUpperCase()})`], [t("Support"), t({ tested: "tested", known: "known platform", experimental: "experimental" }[p.support] || "—")], [t("EC access"), p.ec_backend],
    [t("Hotkeys"), p.hotkeys ? (p.os === "windows" ? "WMI (AcpiTest_EventULong)" : t("uwcc kernel module")) : t("EC polling (no module)")], ["NVRAM (UniWillVariable)", p.nvram ? t("available") : t("unavailable")],
    [h("span", { title: t("Fan control of the EC firmware (name from the original Uniwill service): fan curves in the EC memory, Custom mode, power limits. Without it the program does not control the fans."), class: "has-tip" }, "RamFan 1.5 ⓘ"), p.ramfan15 ? t("yes") : t("no")], [t("Turbo mode"), p.turbo_support ? t("supported") : t("no")], [t("NVIDIA graphics"), p.nv_gpu ? t("yes") : t("no")],
    [t("Platform"), p.amd ? "AMD" : "Intel"], [t("Power adapter"), `${p.adapter_watt} ${t("W")}`],
    [t("Liquid cooling (EC)"), lc.ec_support ? (lc.ec_table ? t("supported, EC targets") : t("supported")) : t("not declared")]]);
  const d = $("#info-disks"); d.innerHTML = "";
  for (const x of i.disks.devices) d.append(h("div", { class: "row between", style: "padding:6px 0;border-bottom:1px solid var(--line)" },
    h("span", {}, `${x.name} · ${x.model || ""}`), h("span", { class: "muted" }, `${x.size_gb} ${t("GB")}${x.temp != null ? ` · ${x.temp}°C` : ""}${x.rotational ? " · HDD" : " · SSD"}`)));
  const w = []; if (!p.ramfan15) w.push(t("The controller does not report RamFan 1.5 support — fan control may not work on this model."));
  if (p.support === "experimental") w.push(t("This laptop has not been tested with Open Uniwill CC yet. Modes and fans usually work the same way, but please check them carefully and send a diagnostic report (below on this page) — it helps to mark the model as supported."));
  if (p.ec_backend === "mock") w.push(t("The service runs in simulation mode (--mock): changes are not applied to hardware."));
  $("#info-warn").classList.toggle("hidden", !w.length); $("#info-warn").innerHTML = ""; for (const x of w) $("#info-warn").append(h("p", {}, "⚠ " + x));
}


// ---------------------------------------------------------------- liquid cooling
// first row: modes that compute the speeds; second row: fixed presets (from high to off)
const LC_MODES = [
  { id: "auto", row: 1, name: "Automatic", desc: "Fan and pump follow the curves by the CPU/GPU temperature." },
  { id: "laptop", row: 1, name: "Follow the laptop", desc: "The common curve or the own curve of the laptop's mode (Office, Gaming, Turbo, Custom)." },
  { id: "ec", row: 1, name: "Controller", desc: "Targets published by the laptop's EC (as in the original software)." },
  { id: "manual", row: 1, name: "Manual", desc: "Set fan speed and pump voltage yourself." },
  { id: "high", row: 2, name: "High", desc: "Fan 90 %, pump 11 V. Maximum cooling." },
  { id: "medium", row: 2, name: "Medium", desc: "Fan 50 %, pump 8 V." },
  { id: "low", row: 2, name: "Low", desc: "Fan 25 %, pump 7 V. Quiet." },
  { id: "off", row: 2, name: "Off", desc: "Fan and pump stopped, lighting stays." },
];
const LC_CURVE_NAME = { common: "Common", office: "Office", gaming: "Gaming", turbo: "Turbo", custom: "Custom" };
const LC_PROFILE_NAME = { default: "Default", quiet: "Quiet", balanced: "Balanced", performance: "Performance" };
const LC_FX = { static: "Static", breathe: "Breathe", rainbow: "Rainbow", breathe_rainbow: "Breathing rainbow",
  spiral: "Spiral", rotating_rainbow: "Rotating rainbow", color_wave: "Colour wave" };
const LC_COLORS = [[255, 0, 0], [255, 96, 0], [255, 200, 0], [0, 255, 0], [0, 128, 0], [0, 255, 255], [0, 80, 255], [160, 0, 255], [255, 0, 160], [255, 255, 255]];
const FLOW = { ok: "Normal", fault: "No flow!", starting: "Starting…", unknown: "Unknown", idle: "Pump stopped", priming: "Filling…" };
let lcScanning = false, lcTab = "common", lcDrag = null;
function rgbHex(c) { return "#" + c.map(x => x.toString(16).padStart(2, "0")).join(""); }
function lcPost(op, body, ok) { return act(() => api("lc/" + op, body || {}), ok); }

function renderLiquid() {
  renderMonLc();
  const L = S.liquid; if (!L) return;
  const pill = $("#lc-pill");
  pill.classList.toggle("hidden", !L.connected);
  if (L.connected) { pill.textContent = `💧 ${L.pump ? L.pump + " V" : t("pump off")} · ${t("fan")} ${L.fan ?? "—"}%`; pill.className = "lc-pill " + (L.flow === "fault" ? "bad" : "ok"); }
  $("#lc-na").classList.toggle("hidden", L.available);
  $("#lc-ui").classList.toggle("hidden", !L.available);
  if (!L.available) return;
  let nt = $("#lc-notemps");
  if (!nt) { nt = h("div", { class: "ec-banner", id: "lc-notemps" }); $("#lc-ui").prepend(nt); }
  nt.classList.toggle("hidden", !L.no_temps);
  if (L.no_temps) nt.textContent = t("All monitoring is off (EC Manager): no temperatures are read, so the automatic mode runs the fixed “{0}” preset.", t({ low: "Low", medium: "Medium", high: "High" }[L.no_temps_preset] || L.no_temps_preset));
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
    kpi(c.mode === "ec" && L.ec_target ? t("Source") : t("Temperature (curve)"),
      c.mode === "ec" && L.ec_target ? t("EC targets") : L.temp != null ? `${L.temp_avg ?? L.temp}°C${L.curve_key && ["auto", "laptop", "ec"].includes(c.mode) ? ` · ${t(LC_CURVE_NAME[L.curve_key] || L.curve_key)}` : ""}` : "—"));
  if (L.connected && ["auto", "laptop", "ec"].includes(c.mode) && (L.pending || L.pump_idle))
    live.append(h("p", { class: "muted tiny", style: "grid-column:1/-1;margin:0" },
      [L.pending ? t(L.pending.dir === "up" ? "Faster in {0} s if the temperature holds" : "Slower in {0} s if the temperature holds", L.pending.left) : "",
       L.pump_idle ? t("Pump stopped: cool") : ""].filter(Boolean).join(" · ")));
  // modes
  const mb = $("#lc-modes"); mb.innerHTML = "";
  for (const m of LC_MODES) {
    if (m.id === "ec" && !L.ec_table) continue;
    mb.append(h("div", { class: "choice" + (c.mode === m.id ? " on" : ""), style: `grid-row:${m.row}`, onclick: () => lcPost("config", { mode: m.id }) }, h("h4", {}, t(m.name)), h("p", {}, t(m.desc))));
  }
  $("#lc-manual").classList.toggle("hidden", c.mode !== "manual");
  $("#lc-fan").value = c.fan; $("#lc-fan").nextElementSibling.textContent = c.fan + "%";
  $("#lc-pump").value = c.pump;
  // curves (Automatic, Follow the laptop; Controller falls back to the common curve)
  $("#lc-curves-card").classList.toggle("hidden", !["auto", "laptop", "ec"].includes(c.mode));
  if (!lcDrag) drawCurves(L);
  if (!$("#lc-calm").contains(document.activeElement)) drawCalm(L);
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
  const hw = S.hwoc || {};
  $("#lc-hwoc-box").classList.toggle("hidden", !hw.supported);
  $("#lc-hwoc").checked = !!hw.enabled;
  const reason = { "off": "", "cooler not connected": t("waiting for the cooler"), "waiting for coolant flow": t("waiting for coolant flow"),
    "no coolant flow": t("no coolant flow — off"), "not supported on this laptop": "" }[hw.reason] ?? (hw.reason || "");
  $("#lc-hwoc-state").textContent = !hw.enabled ? "" : hw.active
    ? t("Active: EC liquid-cooling table{0}, power level {1}", hw.table_loaded === false ? " " + t("(the EC did not confirm it)") : "", hw.level ?? "—")
    : reason;
  $("#lc-notify").checked = !!c.notify_flow; $("#lc-bfan").checked = !!c.boost_fan; $("#lc-bpump").checked = !!c.boost_pump;
  // own pump voltage limits
  $("#lc-pcustom").checked = !!L.pump_custom;
  const pv = $("#lc-pvolts"); pv.innerHTML = "";
  for (const v of L.all_voltages || []) {
    const on = (L.pump_custom ? c.pump_running : [7, 8, 11]).includes(v);
    const box = h("input", { type: "checkbox", ...(on ? { checked: true } : {}), ...(L.pump_custom ? {} : { disabled: true }) });
    box.addEventListener("change", () => {
      const cur = new Set(c.pump_running || []); box.checked ? cur.add(v) : cur.delete(v);
      if (!cur.size) { box.checked = true; return toast(t("At least one voltage must stay"), true); }
      lcPost("config", { pump_limits: { levels: [...cur] } });
    });
    pv.append(h("label", { class: "chk" + (v === 12 ? " warn-text" : "") }, box, ` ${v} V`));
  }
  const run = L.pump_running || [];
  $("#lc-prange").textContent = run.length ? t("Allowed: {0} V (from {1} to {2} V)", run.join(" / "), run[0], run[run.length - 1]) : "";
  const ms = $("#lc-pump");                          // Manual: only the allowed voltages
  for (const o of ms.options) { const v = +o.value; o.hidden = o.disabled = !!v && !run.includes(v); }
}
// ---- curve editors: fan curve (points, linear) and pump steps (7 / 8 / 11 V)
let lcPick = null;                                   // a profile picked in the list and shown before Apply
const LCX0 = 20, LCX1 = 100;                                   // temperature axis, °C
function lcCurrentLaptopKey() { return ({ 0: "office", 1: "gaming", 2: "turbo", 3: "custom" })[S.power && S.power.mode]; }
function lcSet(L, key) { const cs = L.curves[key]; return cs || L.curves.common; }
function lcPostCurve(key, set) { return act(() => api("lc/config", { curves: { [key]: set } })); }
function drawCurves(L) {
  const c = L.config, laptop = c.mode === "laptop";
  if (!laptop || !L.curve_keys.includes(lcTab)) lcTab = laptop ? lcTab : "common";
  // profile row
  const sel = $("#lc-prof"); sel.innerHTML = "";
  if (lcPick && (lcPick === L.profile || !L.profiles.some(p => p.id === lcPick))) lcPick = null;
  if (!L.profile) sel.append(h("option", { value: "" }, t("— own settings —")));
  for (const p of L.profiles) {
    const nm = p.builtin ? t(LC_PROFILE_NAME[p.id] || p.name) : p.name;
    const o = h("option", { value: p.id }, nm + (p.id === L.profile && L.profile_modified ? " · " + t("changed") : ""));
    if (p.id === (lcPick || L.profile)) o.selected = true; sel.append(o);
  }
  if (!sel.value && sel.options.length) sel.selectedIndex = 0;
  const cur = L.profiles.find(p => p.id === sel.value);
  const pick = lcPick ? L.profiles.find(p => p.id === lcPick) : null;   // chosen in the list, not applied yet: shown
  $("#lc-prof-save").disabled = !cur || cur.builtin; $("#lc-prof-remove").disabled = !cur || cur.builtin;
  $("#lc-prof-apply").disabled = !cur;
  // tabs (Follow the laptop)
  const tabs = $("#lc-curve-tabs"); tabs.classList.toggle("hidden", !laptop); tabs.innerHTML = "";
  const now = lcCurrentLaptopKey();
  if (laptop) for (const k of L.curve_keys) tabs.append(h("button", { class: k === lcTab ? "on" : "", onclick: () => { lcTab = k; drawCurves(S.liquid); } },
    t(LC_CURVE_NAME[k]) + (k === now ? " ●" : "") + (k !== "common" && L.curves[k] ? " ✎" : "")));
  const own = laptop && lcTab !== "common";
  $("#lc-own-row").classList.toggle("hidden", !own);
  $("#lc-own").checked = own && !!(pick ? pick.curves : L.curves)[lcTab]; $("#lc-own").disabled = !!pick;
  $("#lc-own-label").textContent = t("Own curve for the mode “{0}” (otherwise the common curve)", t(LC_CURVE_NAME[lcTab] || lcTab));
  $("#lc-curves-title").textContent = laptop ? t("Curves — Follow the laptop") : c.mode === "ec" ? t("Curves — view only (Controller: used when the EC publishes no targets)") : t("Curves — Automatic");
  $("#lc-curves-hint").textContent = laptop ? t("The cooler uses the curve of the laptop's current mode (●) if it has its own (✎), otherwise the common curve. The common curve is also the curve of the Automatic mode.")
    : t("The fan follows the curve between its points. Pump: one point per allowed voltage — drag it to the temperature it starts at (a step down waits until 3 °C below it); drag Off to the right to stop the pump below that temperature (Stop the pump when it is cool).");
  const src = pick ? pick.curves : L.curves;
  const key = own && src[lcTab] ? lcTab : "common";
  const set = JSON.parse(JSON.stringify(src[key] || src.common));
  const viewOnly = c.mode === "ec";                  // Controller: the EC drives the cooler, the curves are only shown
  const readonly = (own && !src[lcTab]) || viewOnly || (pick ? "preview" : false);
  if (pick) $("#lc-curves-hint").textContent = t("Preview of the profile “{0}”: press Apply to use it.", sel.options[sel.selectedIndex].textContent);
  const active = !pick && L.connected && ["auto", "laptop", "ec"].includes(c.mode) && L.curve_key === key ? L : null;
  const ed = $("#lc-editors"); ed.innerHTML = "";
  ed.append(lcFanEditor(set, key, readonly, active), lcPumpEditor(set, key, readonly, active));
  $("#lc-flat").disabled = readonly;
  for (const id of ["lc-prof", "lc-prof-apply", "lc-prof-save", "lc-prof-copy", "lc-prof-remove"]) if (viewOnly) $("#" + id).disabled = true;
  if (!viewOnly) { $("#lc-prof").disabled = false; $("#lc-prof-copy").disabled = !!pick; }
  $("#lc-flat").onclick = () => {
    const v = prompt(t("Fan duty for the whole curve, %"), String(set.fan[set.fan.length - 1][1]));
    if (v === null) return; const n = Math.max(0, Math.min(100, parseInt(v, 10) || 0));
    lcPostCurve(key, { fan: [[LCX0, n], [LCX1, n]], pump: set.pump });
  };
}
$("#lc-own").addEventListener("change", e => {
  const L = S.liquid; lcPostCurve(lcTab, e.target.checked ? JSON.parse(JSON.stringify(L.curves.common)) : null);
});
function lcSvg(w, hgt) { const e = document.createElementNS("http://www.w3.org/2000/svg", "svg"); e.setAttribute("viewBox", `0 0 ${w} ${hgt}`); e.setAttribute("class", "curve lc-curve"); return e; }
function lcEl(tag, attrs, text) { const e = document.createElementNS("http://www.w3.org/2000/svg", tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); if (text != null) e.textContent = text; return e; }
// same look as the laptop fan curve (Fan settings): 640-wide box, grid, 11 px labels, filled points
function lcAxes(svg, P, yTicks) {
  const g = lcEl("g", { class: "grid" });
  for (let x = LCX0; x <= LCX1; x += 10) {
    const px = P.x(x); g.append(lcEl("line", { x1: px, x2: px, y1: P.top, y2: P.bot }), lcEl("text", { x: px - 8, y: P.bot + 18 }, `${x}°`));
  }
  for (const [v, lab] of yTicks) { const py = P.y(v); g.append(lcEl("line", { x1: P.left, x2: P.right, y1: py, y2: py }), lcEl("text", { x: 14, y: py + 4 }, lab)); }
  svg.append(g);
}
function lcNowLabel(svg, x, y, label, right, bot, flip) {  // text under the red dot (rising curves pass above-right of it)
  const left = x > right - 150, up = (y > bot - 24) !== !!flip;
  svg.append(lcEl("text", { x: left ? x - 10 : x + 10, y: up ? y - 12 : y + 22, class: "nowlbl", "text-anchor": left ? "end" : "start" }, label));
}
function lcCross(svg, P, temp, yv, label, flip) {      // the current point: a red dot with temperature · value
  if (temp == null || yv == null) return;
  const x = P.x(Math.max(LCX0, Math.min(LCX1, temp))), y = P.y(yv);
  const d = lcEl("circle", { cx: x, cy: y, r: 6, class: "crossdot" });
  d.append(lcEl("title", {}, label)); svg.append(d);
  lcNowLabel(svg, x, y, label, P.right, P.bot, flip);
}
// The red dots follow the temperature source: CPU only / GPU only (the CPU while the GPU sleeps) / both — two dots.
// The sensor that drives the cooler shows the cooler's real output; the other one shows its point on the curve.
function lcSensorDots(L) {
  const src = (lcCalm && lcCalm.temp_source) || L.config.temp_source || "max", m = lastMonitor;
  const cpu = m && m.cpu && m.cpu.temp != null ? m.cpu.temp : null;
  const gpu = m && m.gpu && !m.gpu.asleep && m.gpu.temp != null ? m.gpu.temp : null;
  let dots = [];
  if (src === "cpu" || (src === "gpu" && gpu == null)) dots = cpu != null ? [{ who: "CPU", temp: cpu }] : [];
  else if (src === "gpu") dots = [{ who: "GPU", temp: gpu }];
  else dots = [cpu != null && { who: "CPU", temp: cpu }, gpu != null && { who: "GPU", temp: gpu }].filter(Boolean);
  if (!dots.length) return L.temp_avg != null ? [{ who: "", temp: L.temp_avg, main: true }] : [];
  dots.reduce((a, b) => (b.temp > a.temp ? b : a)).main = true;
  return dots;
}
function lcFanAt(set, tc) {
  const f = set.fan; if (tc <= f[0][0]) return f[0][1]; if (tc >= f[f.length - 1][0]) return f[f.length - 1][1];
  for (let i = 1; i < f.length; i++) if (tc <= f[i][0]) return Math.round(f[i - 1][1] + (f[i][1] - f[i - 1][1]) * (tc - f[i - 1][0]) / (f[i][0] - f[i - 1][0]));
  return f[f.length - 1][1];
}
function lcPumpAt(set, tc) { let v = set.pump[0][1]; for (const [t0, v0] of set.pump.slice(1)) if (tc >= t0) v = v0; return v; }
function lcDragLabel(g, P, x, y, text) {          // while dragging: the point's values next to it
  const right = x < P.left + 150, down = y < P.top + 30;     // above-left: the curves rise to the right
  g.append(lcEl("text", { x: right ? x + 12 : x - 12, y: down ? y + 28 : y - 14, class: "draglbl", "text-anchor": right ? "start" : "end" }, text));
}
function lcPlot(w, hgt, ymin, ymax) {
  const P = { left: 62, right: 606, top: 20, bot: hgt - 30 };
  P.x = tc => P.left + (tc - LCX0) / (LCX1 - LCX0) * (P.right - P.left);
  P.y = v => P.bot - (v - ymin) / (ymax - ymin) * (P.bot - P.top);
  P.tx = px => Math.round(LCX0 + (px - P.left) / (P.right - P.left) * (LCX1 - LCX0));
  P.vy = py => ymin + (P.bot - py) / (P.bot - P.top) * (ymax - ymin);
  return P;
}
function lcPointer(svg, e) { const r = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal; return [(e.clientX - r.left) / r.width * vb.width, (e.clientY - r.top) / r.height * vb.height]; }
function lcFanEditor(set, key, readonly, L) {
  const W = 640, H = 230, P = lcPlot(W, H, 0, 100), svg = lcSvg(W, H), pts = set.fan;
  lcAxes(svg, P, [[0, "0%"], [25, "25%"], [50, "50%"], [75, "75%"], [100, "100%"]]);
  const path = lcEl("polyline", { class: "line" + (readonly === true ? " ro" : "") }); svg.append(path);
  const dots = lcEl("g", {}); svg.append(dots);
  const redraw = () => {
    const xs = [[LCX0, pts[0][1]], ...pts.map(p => [Math.max(LCX0, p[0]), p[1]]), [LCX1, pts[pts.length - 1][1]]];
    path.setAttribute("points", xs.map(([a, b]) => `${P.x(a)},${P.y(b)}`).join(" "));
    dots.innerHTML = "";
    pts.forEach((p, i) => {
      const d = lcEl("circle", { cx: P.x(Math.max(LCX0, p[0])), cy: P.y(p[1]), r: 7, class: "pt" + (readonly === true ? " ro" : readonly ? " pv" : "") });
      d.dataset.i = i;
      d.append(lcEl("title", {}, `${p[0]} °C · ${p[1]} %`));
      dots.append(d);
    });
    if (lcDrag && lcDrag.svg === svg && pts[lcDrag.i]) {
      const p = pts[lcDrag.i]; lcDragLabel(dots, P, P.x(Math.max(LCX0, p[0])), P.y(p[1]), `${p[0]} °C · ${p[1]} %`);
    }
  };
  redraw();
  // the dots are redrawn on every move: the svg itself holds the pointer (as in the laptop fan curve)
  if (!readonly) {
    svg.addEventListener("pointerdown", ev => {
      const c = ev.target.closest && ev.target.closest(".pt"); if (!c) return;
      ev.preventDefault(); svg.setPointerCapture(ev.pointerId); lcDrag = { i: +c.dataset.i, svg };
    });
    svg.addEventListener("pointermove", ev => {
      if (!lcDrag) return;
      const i = lcDrag.i, p = pts[i], [mx, my] = lcPointer(svg, ev);
      const lo = i ? pts[i - 1][0] + 1 : LCX0, hi = i < pts.length - 1 ? pts[i + 1][0] - 1 : LCX1;
      const dlo = i ? pts[i - 1][1] : 0, dhi = i < pts.length - 1 ? pts[i + 1][1] : 100;
      p[0] = Math.max(lo, Math.min(hi, P.tx(mx))); p[1] = Math.max(dlo, Math.min(dhi, Math.round(P.vy(my))));
      redraw();
    });
    const end = ev => { if (!lcDrag) return; if (svg.hasPointerCapture(ev.pointerId)) svg.releasePointerCapture(ev.pointerId); lcDrag = null; lcPostCurve(key, set); };
    svg.addEventListener("pointerup", end); svg.addEventListener("pointercancel", end);
    dots.addEventListener("dblclick", ev => {
      const c = ev.target.closest && ev.target.closest(".pt"); if (!c) return;
      ev.stopPropagation(); if (pts.length > 2) { pts.splice(+c.dataset.i, 1); lcPostCurve(key, set); }
    });
  }
  if (!readonly) svg.addEventListener("dblclick", ev => {
    if (pts.length >= S.liquid.max_fan_points) return toast(t("At most {0} points", S.liquid.max_fan_points), true);
    const [mx] = lcPointer(svg, ev); const tc = Math.max(LCX0, Math.min(LCX1, P.tx(mx)));
    if (pts.some(p => p[0] === tc)) return;
    const k = pts.findIndex(p => p[0] > tc), ins = k < 0 ? pts.length : k;
    const prev = pts[ins - 1], next = pts[ins];
    const duty = prev && next ? Math.round(prev[1] + (next[1] - prev[1]) * (tc - prev[0]) / (next[0] - prev[0])) : (prev || next)[1];
    pts.splice(ins, 0, [tc, duty]); lcPostCurve(key, set);
  });
  if (L && L.fan != null) lcSensorDots(L).forEach((d, k) => {
    const v = d.main ? L.fan : lcFanAt(set, d.temp);
    lcCross(svg, P, d.temp, v, `${d.who ? d.who + " " : ""}${d.temp} °C · ${v} %`, k > 0);
  });
  return h("div", { class: "lc-ed" }, h("h4", {}, t("Cooler fan")), svg);
}
// Pump: one point per allowed voltage (7 / 8 / 11 V, or the own limits), moved only along the temperature: the
// temperature from which the pump runs at that voltage or more. A voltage whose point sits on the next one is not used.
// The Off point is "Stop the pump when it is cool": at the left edge it is off; dragged right (30..85 °C) the pump
// stops below that temperature and starts again a few degrees above it.
function lcPumpSlots(st, run) {                  // curve steps -> start temperature of every allowed voltage
  const steps = st.filter(s0 => s0[1]);
  const slots = run.map(v => { const s0 = steps.find(x => x[1] >= v); return s0 ? Math.max(LCX0, s0[0]) : LCX1; });
  slots[0] = LCX0;
  for (let k = 1; k < slots.length; k++) slots[k] = Math.max(slots[k], slots[k - 1]);
  return slots;
}
function lcSlotsToSteps(slots, run) {            // start temperatures -> curve steps (unused voltages dropped)
  const out = [];
  run.forEach((v, k) => { if (k === run.length - 1 || slots[k + 1] > slots[k]) out.push([out.length ? slots[k] : 0, v]); });
  return out;
}
function lcPumpEditor(set, key, readonly, L) {
  const W = 640, H = 230, run = S.liquid.pump_running || [7, 8, 11], lv = [0, ...run];
  const P = lcPlot(W, H, 0, lv.length - 1), svg = lcSvg(W, H), yi = v => Math.max(0, lv.indexOf(v));
  const slots = lcPumpSlots(set.pump, run);
  const calm = lcCalm || { pump_idle: { ...(S.liquid.config.pump_idle || {}) } }, pi = calm.pump_idle;
  let off = pi.enabled ? pi.off_below : null;
  lcAxes(svg, P, lv.map((v, i) => [i, v ? `${v} V` : t("Off")]));
  const path = lcEl("polyline", { class: "line pump" + (readonly === true ? " ro" : "") }); svg.append(path);
  const dots = lcEl("g", {}); svg.append(dots);
  const ro = readonly === true ? " ro" : readonly ? " pv" : "";
  const redraw = () => {
    const xs = [];
    const o = off != null ? off : LCX0;
    if (off != null) xs.push([LCX0, 0], [o, 0]);
    run.forEach((v, k) => {
      const a = Math.max(slots[k], o), b = k < run.length - 1 ? Math.max(slots[k + 1], o) : LCX1;
      if (b > a || k === run.length - 1) { if (xs.length) xs.push([a, xs[xs.length - 1][1]]); xs.push([a, k + 1], [b, k + 1]); }
    });
    path.setAttribute("points", xs.map(([a, b]) => `${P.x(a)},${P.y(b)}`).join(" "));
    dots.innerHTML = "";
    const od = lcEl("circle", { cx: P.x(o), cy: P.y(0), r: 7, class: "pt gpu pt-off" + (off == null ? " idle" : "") + ro });
    od.dataset.i = "off";
    od.append(lcEl("title", {}, off == null ? t("Off: drag to the right to stop the pump when it is cool")
      : t("Off below {0} °C, on again from {1} °C (Stop the pump when it is cool)", off, pi.on_above)));
    if (off != null) dots.append(lcEl("text", { x: P.x(o) + 10, y: P.y(0) - 10 }, `${off}°`));
    dots.append(od);
    run.forEach((v, k) => {
      const x = Math.max(k ? slots[k] : LCX0, o);
      const d = lcEl("circle", { cx: P.x(x), cy: P.y(k + 1), r: 7, class: "pt gpu" + (k ? "" : " fixed") + ro });
      d.dataset.i = k;
      d.append(lcEl("title", {}, k ? `${v} V ${t("from")} ${slots[k]} °C` : `${v} V ${t("from the start")}`));
      if (k && slots[k] > Math.max(LCX0, o) && slots[k] < LCX1 && !(lcDrag && lcDrag.svg === svg && +lcDrag.i === k)) dots.append(lcEl("text", { x: P.x(x) - 10, y: P.y(k + 1) - 10, "text-anchor": "end" }, `${slots[k]}°`));
      dots.append(d);
    });
    if (lcDrag && lcDrag.svg === svg) {
      if (lcDrag.i === "off") lcDragLabel(dots, P, P.x(o), P.y(0), off == null ? t("Off: never") : t("Off below {0} °C", off));
      else { const k = +lcDrag.i; lcDragLabel(dots, P, P.x(Math.max(slots[k], o)), P.y(k + 1), `${t("from")} ${slots[k]} °C · ${run[k]} V`); }
    }
  };
  redraw();
  const postIdle = () => {
    const was = S.liquid.config.pump_idle || {}, gap = Math.max(2, (pi.on_above ?? 55) - (pi.off_below ?? 50));
    const nx = off == null ? { ...pi, enabled: false }
      : { ...pi, enabled: true, off_below: off, on_above: Math.min(95, off + gap) };
    Object.assign(pi, nx); if (lcCalm) lcCalm.pump_idle = pi;
    if (nx.enabled !== !!was.enabled || nx.off_below !== was.off_below || nx.on_above !== was.on_above)
      lcPost("config", { pump_idle: nx }).then(() => drawCalm(S.liquid));
  };
  if (!readonly) {
    svg.addEventListener("pointerdown", ev => {
      const c = ev.target.closest && ev.target.closest(".pt"); if (!c || c.dataset.i === "0") return;
      ev.preventDefault(); svg.setPointerCapture(ev.pointerId); lcDrag = { i: c.dataset.i, svg };
    });
    svg.addEventListener("pointermove", ev => {
      if (!lcDrag) return;
      const [mx] = lcPointer(svg, ev), tc = Math.max(LCX0, Math.min(LCX1, P.tx(mx)));
      if (lcDrag.i === "off") off = tc < 30 ? null : Math.min(85, tc);
      else {
        const k = +lcDrag.i, hi = k < run.length - 1 ? slots[k + 1] : LCX1;
        slots[k] = Math.max(slots[k - 1], Math.min(hi, tc));
      }
      redraw();
    });
    const end = ev => {
      if (!lcDrag) return; if (svg.hasPointerCapture(ev.pointerId)) svg.releasePointerCapture(ev.pointerId);
      const which = lcDrag.i; lcDrag = null;
      if (which === "off") postIdle(); else { set.pump = lcSlotsToSteps(slots, run); lcPostCurve(key, set); }
    };
    svg.addEventListener("pointerup", end); svg.addEventListener("pointercancel", end);
  }
  if (L && L.pump != null) lcSensorDots(L).forEach((d, k) => {
    const v = d.main ? L.pump : off != null && d.temp < off ? 0 : lcPumpAt(set, d.temp);
    lcCross(svg, P, d.temp, Math.max(0, yi(v)), `${d.who ? d.who + " " : ""}${d.temp} °C · ${v ? v + " V" : t("off")}`, k > 0);
  });
  return h("div", { class: "lc-ed" }, h("h4", {}, t("Pump")), svg);
}
$("#lc-prof").addEventListener("change", e => { lcPick = e.target.value || null; drawCurves(S.liquid); });
const lcProf = (action, extra, ok) => { const id = $("#lc-prof").value; lcPick = null; return lcPost("profile", { action, id, ...(extra || {}) }, ok); };
$("#lc-prof-apply").addEventListener("click", () => lcProf("apply", {}, t("Profile applied")));
$("#lc-prof-save").addEventListener("click", () => lcProf("save", {}, t("Saved")));
$("#lc-prof-copy").addEventListener("click", () => {
  const n = prompt(t("Name of the new cooler profile"), ""); if (n && n.trim()) lcProf("copy", { name: n.trim() }, t("Profile saved"));
});
$("#lc-prof-remove").addEventListener("click", () => { if (confirm(t("Remove this cooler profile?"))) lcProf("remove", {}, t("Removed")); });
// delays, smoothing, temperature source, pump stop when cool (auto / Controller modes)
let lcCalm = null;
function drawCalm(L) {
  const c = L.config;
  if (!lcCalm) lcCalm = { temp_source: c.temp_source || "max", delay_up: c.delay_up ?? 10, delay_down: c.delay_down ?? 30,
    smooth: c.smooth !== false, pump_idle: { ...(c.pump_idle || {}) } };
  const k = lcCalm, pi = k.pump_idle, box = $("#lc-calm"); box.innerHTML = "";
  const num = (obj, key, min, max, unit) => {
    const e = h("input", { type: "number", min, max, value: obj[key], class: "num" });
    e.addEventListener("change", () => { obj[key] = +e.value; });
    return h("span", { class: "row", style: "gap:6px;flex:none" }, e, h("span", { class: "muted" }, unit));
  };
  const chk = (obj, key, label, after) => {
    const e = h("input", { type: "checkbox" }); e.checked = !!obj[key];
    e.addEventListener("change", () => { obj[key] = e.checked; if (after) after(); });
    return h("label", { class: "chk" }, e, " ", h("span", {}, label));
  };
  const line = (label, ...ctrl) => h("div", { class: "calm-row" }, h("span", {}, label), h("div", { class: "row wrap", style: "gap:10px" }, ...ctrl));
  const src = h("select", {}, ...[["max", "Hotter of CPU and GPU"], ["cpu", "CPU"], ["gpu", "GPU only"]].map(([v, n]) => {
    const o = h("option", { value: v }, t(n)); if (k.temp_source === v) o.selected = true; return o; }));
  src.addEventListener("change", () => { k.temp_source = src.value; if (!lcDrag) drawCurves(S.liquid); });
  box.append(
    h("h4", {}, t("Behaviour")),
    line(t("Temperature"), src, h("span", { class: "muted tiny" }, t("GPU only: while the graphics card sleeps, the CPU is used"))),
    line(t("Raise the speed after"), num(k, "delay_up", 0, 300, t("s")), h("span", { class: "muted tiny" }, t("at once from 95 °C or when the curve asks 25 % more"))),
    line(t("Lower the speed after"), num(k, "delay_down", 0, 300, t("s"))),
    chk(k, "smooth", t("Smooth: average the temperature over 10 s, change the fan by 10 % and the pump by one voltage step at a time")),
    h("h4", {}, t("Stop the pump when it is cool")),
    chk(pi, "enabled", t("Stop the pump at low load (the cooler fan keeps following the curve)"), () => drawCalm(L)));
  if (pi.enabled) box.append(
    line(t("Stop below"), num(pi, "off_below", 30, 85, "°C"), h("span", { class: "muted" }, t("for")), num(pi, "off_after", 10, 900, t("s"))),
    line(t("Start again above"), num(pi, "on_above", 32, 95, "°C"), h("span", { class: "muted" }, t("for")), num(pi, "on_after", 0, 120, t("s"))),
    line(t("Run at least"), num(pi, "min_run", 0, 1800, t("s")), h("span", { class: "muted tiny" }, t("after each start, so the pump does not cycle"))));
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
  if (v === 12 && !confirm(t("12 V is not used by the OEM software and may shorten pump life. Continue?"))) { e.target.value = S.liquid.config.pump; return; }   // only with own limits
  if (v === 0 && !confirm(t("Stop the pump? The coolant will not circulate."))) { e.target.value = S.liquid.config.pump; return; }
  lcPost("config", { mode: "manual", pump: v });
});
$("#lc-calm-save").addEventListener("click", () => act(async () => {
  await api("lc/config", { ...(lcCalm || {}) }); lcCalm = null;
}, t("Saved")));
$("#lc-calm-reset").addEventListener("click", () => {
  lcCalm = { temp_source: "max", delay_up: 10, delay_down: 30, smooth: true, pump_idle: { ...(S.liquid.config.pump_idle || {}), enabled: false } };
  drawCalm(S.liquid);
});
$("#lc-pcustom").addEventListener("change", e => {
  if (e.target.checked) {
    if (!confirm(t("Own pump voltage limits: a voltage outside 7–11 V can damage the pump — too low and it may stop moving the coolant, too high and it wears out faster (the OEM software never uses 12 V). Do you understand the risks and want to continue?"))) { e.target.checked = false; return; }
    lcPost("config", { pump_limits: { custom: true, accept_risks: true } }, t("Own pump limits on"));
  } else lcPost("config", { pump_limits: { custom: false } }, t("Pump limits: 7–11 V"));
});
$("#lc-rgb-on").addEventListener("change", e => lcPost("config", { rgb: { on: e.target.checked } }));
$("#lc-color").addEventListener("change", e => lcPost("config", { rgb: { on: true, color: hex2rgb(e.target.value) } }));
$("#lc-prime").addEventListener("click", () => {
  if (S.liquid.priming != null) return lcPost("prime", { stop: true });
  if (confirm(t("Start the coolant filling cycle (about 70 seconds)?"))) lcPost("prime", {});
});
$("#lc-hwoc").addEventListener("change", e => act(() => api("setting", { key: "lc_hwoc", value: e.target.checked }),
  e.target.checked ? t("Liquid cooling power boost on") : t("Liquid cooling power boost off")));
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
  clock: { name: "Clocks", unit: "MHz", max: 0, lines: [["cm", "CPU", "var(--cpu)"], ["gm", "GPU", "var(--gpu)"]],
    nodata: "no data" },
  fans: { name: "Fans", unit: "rpm", max: 0, lines: [["cf", "CPU", "var(--cpu)"], ["gf", "GPU", "var(--gpu)"]] },
  cooler: { name: "Cooler", unit: "%", max: 100, lines: [["lf", "Cooler fan", "var(--acc)"], ["lpx", "Pump (V × 8)", "var(--warn)"]] },
};
const HIST_RANGES = [[60, "1 min"], [300, "5 min"], [900, "15 min"], [3600, "1 hour"], [86400, "24 hours"]];
let histKey = "temp", histData = [], histT = 0, histNow = Date.now() / 1000, histPin = null, histBase = "", histMax = 1;
let histZoom = null;                     // {t0, t1}: a period chosen by dragging across the chart (refresh paused)
let histRange = 3600;
try { const r = +localStorage.getItem("uwcc-hist-range"); if (HIST_RANGES.some(x => x[0] === r)) histRange = r; } catch (_) {}
const histStep = () => histRange <= 900 ? 2 : histRange <= 3600 ? 5 : 60;
const HIST_W = 800, HIST_H = 180;
function renderHistSeg() {
  const seg = $("#hist-seg"); seg.innerHTML = "";
  for (const [k, d] of Object.entries(HIST)) seg.append(h("button", { class: k === histKey ? "on" : "", onclick: () => { histKey = k; renderHistSeg(); drawHistory(); } }, t(d.name)));
  $("#hist-export-btn").title = t("Export");
  const rs = $("#hist-range"); rs.innerHTML = "";
  for (const [sec, name] of HIST_RANGES) rs.append(h("button", { class: sec === histRange ? "on" : "", onclick: () => {
    histRange = sec; try { localStorage.setItem("uwcc-hist-range", sec); } catch (_) {}
    histZoom = null; unpinHistory(false); renderHistSeg(); loadHistory(true);
  } }, t(name)));
}
async function loadHistory(force) {
  if (histPin || histZoom) return drawHistory();           // paused on a point / on a zoomed period
  const age = histRange <= 900 ? 1900 : histRange <= 3600 ? 9000 : 55000;
  if (!force && Date.now() - histT < age) return drawHistory();
  try {
    histData = await api("history?range=" + histRange); histT = Date.now(); histNow = Date.now() / 1000;
    histData.forEach(p => { p.lpx = p.lp != null ? p.lp * 8 : null; });
  } catch (_) {}
  drawHistory();
}
function relLabel(sec) {
  if (sec <= 0) return t("now");
  return sec < 60 ? `−${sec} ${t("s")}` : sec < 3600 ? `−${Math.round(sec / 60)} ${t("min")}` : `−${Math.round(sec / 3600)} ${t("h")}`;
}
const histV0 = () => histZoom ? histZoom.t0 : histNow - histRange;      // the period on screen
const histSpan = () => histZoom ? histZoom.t1 - histZoom.t0 : histRange;
const histX = tt => (tt - histV0()) / histSpan() * HIST_W;
function histVisible() {                // points of the period on screen, with one neighbour each side for the lines
  if (!histZoom) return histData;
  const a = histData.findIndex(p => p.t >= histZoom.t0);
  if (a < 0) return [];
  let b = histData.length - 1;
  while (b > 0 && histData[b].t > histZoom.t1) b--;
  return histData.slice(Math.max(0, a - 1), Math.min(histData.length, b + 2));
}
const histIn = p => !histZoom || (p.t >= histZoom.t0 && p.t <= histZoom.t1);
const histY = v => HIST_H - Math.min(1, v / histMax) * HIST_H;
function drawHistory() {
  const svg = $("#hist-chart"), W = HIST_W, H = HIST_H, d = HIST[histKey];
  const all = histData, pts = histVisible(), inView = pts.filter(histIn);
  $("#hist-zoom-reset").classList.toggle("hidden", !histZoom);
  let max = d.max;
  const marks = d.marks || [];
  if (histKey === "total") all.forEach(p => { p.adapter = S && S.platform && S.platform.adapter_watt || null; });
  if (!max) {
    max = 10;
    for (const p of inView) for (const [k] of d.lines) if (p[k] > max) max = p[k];
    // keep the limit marks in view, but not a 330 W adapter line over a 20 W curve
    for (const p of inView) for (const [k] of marks) if (p[k] > max && p[k] < max * 3) max = p[k];
    max = Math.ceil(max * 1.1 / 10) * 10;
  }
  histMax = max;
  let g = "";
  for (const f of [0.25, 0.5, 0.75]) { const y = H - f * H; g += `<line x1="0" x2="${W}" y1="${y}" y2="${y}" stroke="#1f2830"/><text x="4" y="${y - 3}" fill="#55636e" font-size="10">${Math.round(max * f)} ${t(d.unit)}</text>`; }
  const nt = histZoom ? 4 : { 60: 4, 300: 5, 900: 3, 3600: 4, 86400: 4 }[histRange] || 4;
  for (let i = 0; i <= nt; i++) {
    const x = i === nt ? W - 4 : (i / nt) * W + 2;
    const label = histZoom ? new Date((histV0() + histSpan() * i / nt) * 1000).toLocaleTimeString()
      : relLabel(Math.round(histRange * (1 - i / nt)));
    g += `<text x="${x}" y="${H - 3}" fill="#55636e" font-size="10" text-anchor="${i === nt ? "end" : "start"}">${label}</text>`;
  }
  const gap = histStep() * 4;
  for (const [k, , color] of d.lines) {
    let path = "", pen = false, prevT = null;
    for (const p of pts) {
      const v = p[k];
      if (v == null || (prevT && p.t - prevT > gap)) pen = false;
      prevT = p.t;
      if (v == null) continue;
      path += (pen ? " L" : " M") + histX(p.t).toFixed(1) + "," + histY(v).toFixed(1); pen = true;
    }
    if (path) g += `<path d="${path}" fill="none" stroke="${color}" stroke-width="1.8" vector-effect="non-scaling-stroke"/>`;
  }
  for (const [k, n, color] of marks) {            // limits: dashed step line + label at the latest value
    let path = "", last = null, lastX = 0;
    for (const p of pts) {
      const v = p[k]; if (v == null || v > max) { last = null; continue; }
      const x = histX(p.t), y = H - v / max * H;
      path += (last == null ? " M" : ` L${x.toFixed(1)},${(H - last / max * H).toFixed(1)} L`) + x.toFixed(1) + "," + y.toFixed(1);
      last = v; lastX = x;
    }
    if (path) g += `<path d="${path}" fill="none" stroke="${color}" stroke-width="1.2" stroke-dasharray="6 4" opacity=".9" vector-effect="non-scaling-stroke"/>` +
      `<text x="${Math.min(lastX, W - 4)}" y="${H - last / max * H - 4}" fill="${color}" font-size="10" text-anchor="end">${t(n)} ${last} ${t("W")}</text>`;
  }
  const recording = !S || !S.settings || S.settings.history_record !== false;
  const hasData = inView.some(p => d.lines.some(([k]) => p[k] != null));
  const msg = !all.length ? (recording ? t("collecting data…") : t("History recording is off (Settings → Switches)")) : !hasData ? t(d.nodata || "no data") : "";
  histBase = msg ? g + `<text x="${W / 2}" y="${H / 2}" fill="#55636e" font-size="13" text-anchor="middle">${msg}</text>` : g;
  svg.innerHTML = histBase + histOverlay(histPin, true);
  histDots(histPin);
  const notes = [];
  if (!recording && all.length) notes.push(t("Recording is off"));
  if (histRange === 86400) notes.push(t("one point per minute (average)"));
  if (histZoom) notes.push(t("zoomed: {0} – {1}", new Date(histZoom.t0 * 1000).toLocaleTimeString(), new Date(histZoom.t1 * 1000).toLocaleTimeString()));
  if (hasData) {                                  // latest / average / max of the visible series
    for (const [k, n] of d.lines) {
      const v = inView.map(p => p[k]).filter(x => x != null);
      const mx = inView.map(p => p[k + "_mx"] ?? p[k]).filter(x => x != null);
      if (!v.length) continue;
      const avg = v.reduce((a, b) => a + b, 0) / v.length;
      notes.push(`${t(n)}: ${histZoom ? t("last") : t("now")} ${v[v.length - 1]} · ${t("avg")} ${Math.round(avg * 10) / 10} · ${t("max")} ${Math.max(...mx)} ${t(d.unit)}`);
    }
    for (const [k, n] of marks) {
      const v = inView.map(p => p[k]).filter(x => x != null);
      if (v.length) notes.push(`${t(n)}: ${v[v.length - 1]} ${t("W")}`);
    }
  }
  $("#hist-stats").textContent = notes.join("  |  ");
  const lg = $("#hist-legend"); lg.innerHTML = "";
  for (const [, n, color] of d.lines) lg.append(h("span", { class: "lg", style: `--c:${color}` }, t(n)));
  for (const [k, n, color] of marks) if (inView.some(p => p[k] != null)) lg.append(h("span", { class: "lg dash", style: `--c:${color}` }, t(n)));
  renderHistDetail();
}
// -- hover / pinned point
function histNearest(evt) {
  const svg = $("#hist-chart"), r = svg.getBoundingClientRect();
  if (!histData.length || !r.width) return null;
  const tt = histV0() + (evt.clientX - r.left) / r.width * histSpan();
  let best = null;
  for (const p of histData) if (histIn(p) && (!best || Math.abs(p.t - tt) < Math.abs(best.t - tt))) best = p;
  return best && Math.abs(best.t - tt) <= Math.max(histStep() * 3, histSpan() / 100) ? best : null;
}
function histDots(...pts) {                     // HTML dots: the SVG is stretched, circles would be ellipses
  const box = $("#hist-dots"); box.innerHTML = "";
  for (const p of pts) if (p) for (const [k, , color] of HIST[histKey].lines) if (p[k] != null)
    box.append(h("span", { style: `left:${histX(p.t) / HIST_W * 100}%;top:${histY(p[k]) / HIST_H * 100}%;background:${color}` }));
}
function histOverlay(p, pinned) {
  if (!p) return "";
  const d = HIST[histKey], x = histX(p.t).toFixed(1);
  let o = `<line x1="${x}" x2="${x}" y1="0" y2="${HIST_H}" stroke="${pinned ? "var(--acc)" : "#8c9aa6"}" stroke-width="1" ${pinned ? "" : 'stroke-dasharray="3 3"'} vector-effect="non-scaling-stroke"/>`;
  return o;
}
const histTime = p => new Date(p.t * 1000).toLocaleTimeString() + (histRange === 86400 ? " · " + new Date(p.t * 1000).toLocaleDateString() : "");
function histTipText(p) {
  const d = HIST[histKey], rows = [histTime(p) + ` (${relLabel(Math.round(histNow - p.t))})`];
  for (const [k, n] of d.lines) if (p[k] != null) rows.push(`${t(n)}: ${p[k]} ${t(d.unit)}` + (p[k + "_mx"] != null ? ` (${t("max")} ${p[k + "_mx"]})` : ""));
  for (const [k, n] of d.marks || []) if (p[k] != null) rows.push(`${t(n)}: ${p[k]} ${t("W")}`);
  return rows;
}
function unpinHistory(reload = true) {
  if (!histPin) return;
  histPin = null; $("#hist-detail").classList.add("hidden");
  if (reload) loadHistory(true);
}
function renderHistDetail() {
  const box = $("#hist-detail"), p = histPin;
  if (!p) { box.classList.add("hidden"); return; }
  const f = (v, u, mx) => v == null ? null : `${v} ${t(u)}` + (mx != null ? ` (${t("max")} ${mx})` : "");
  const groups = [
    [t("CPU"), [[t("Temperature"), f(p.ct, "°C", p.ct_mx)], [t("Load"), f(p.cl, "%")], [t("Clock"), f(p.cm, "MHz")], [t("Power draw"), f(p.cp, "W", p.cp_mx)],
      [t("Power limits"), [p.pl1, p.pl2, p.pl4].some(x => x != null) ? [p.pl1, p.pl2, p.pl4].map(x => x ?? "—").join(" / ") + " " + t("W") : null]]],
    [t("GPU"), [[t("Temperature"), f(p.gt, "°C", p.gt_mx)], [t("Load"), f(p.gl, "%")], [t("Clock"), f(p.gm, "MHz")], [t("Power draw"), f(p.gp, "W", p.gp_mx)], [t("GPU power limit"), f(p.gpl, "W")]]],
    [t("Total power"), [[t("CPU + GPU"), f(p.tp, "W", p.tp_mx)], [t("From battery"), f(p.bp, "W")]]],
    [t("Fans"), [[t("CPU"), f(p.cf, "rpm")], [t("GPU"), f(p.gf, "rpm")], [t("Cooler fan"), f(p.lf, "%")], [t("Pump"), f(p.lp, "V")]]],
  ];
  box.innerHTML = "";
  box.append(h("div", { class: "row between wrap" },
    h("b", {}, histTime(p) + (histRange === 86400 ? " · " + t("average of the minute") : "")),
    h("button", { class: "btn ghost", onclick: () => unpinHistory() }, t("Resume"))));
  const grid = h("div", { class: "hist-detail-grid" });
  for (const [title, rows] of groups) {
    const items = rows.filter(r => r[1] != null);
    if (!items.length) continue;
    const dl = h("dl", { class: "kv" });
    for (const [k, v] of items) dl.append(h("dt", {}, k), h("dd", {}, v));
    grid.append(h("div", {}, h("h4", {}, title), dl));
  }
  box.append(grid);
  box.classList.remove("hidden");
}
function zoomHistory(t0, t1) {
  const inside = histData.filter(p => p.t >= t0 && p.t <= t1).length;
  if (inside < 2) { toast(t("Choose a longer period — it has fewer than two points"), true); drawHistory(); return; }
  histZoom = { t0, t1 };
  if (histPin && !histIn(histPin)) histPin = null;
  drawHistory();
}
function resetHistoryZoom() {
  if (!histZoom) return;
  histZoom = null;
  if (!histPin) loadHistory(true); else drawHistory();
}
$("#hist-zoom-reset").addEventListener("click", resetHistoryZoom);
(() => {
  const svg = $("#hist-chart"), tip = $("#hist-tip");
  let drag = null, dragged = false;                 // drag: {x0, x} (client px) while the mouse button is down
  const timeAt = clientX => { const r = svg.getBoundingClientRect(); return histV0() + Math.min(1, Math.max(0, (clientX - r.left) / r.width)) * histSpan(); };
  svg.addEventListener("mousedown", e => { if (e.button === 0 && histData.length) { drag = { x0: e.clientX, x: e.clientX }; e.preventDefault(); } });
  window.addEventListener("mousemove", e => {
    if (!drag) return;
    drag.x = e.clientX;
    if (Math.abs(drag.x - drag.x0) < 6) return;
    const r = svg.getBoundingClientRect();
    const x0 = Math.max(0, (Math.min(drag.x0, drag.x) - r.left) / r.width * HIST_W);
    const x1 = Math.min(HIST_W, (Math.max(drag.x0, drag.x) - r.left) / r.width * HIST_W);
    svg.innerHTML = histBase + histOverlay(histPin, true) +
      `<rect x="${x0}" y="0" width="${Math.max(0, x1 - x0)}" height="${HIST_H}" fill="var(--acc)" fill-opacity=".13" stroke="var(--acc)" stroke-opacity=".6" vector-effect="non-scaling-stroke"/>`;
    histDots(histPin);
    tip.classList.add("hidden");
  });
  window.addEventListener("mouseup", () => {
    if (!drag) return;
    const d = drag; drag = null;
    if (Math.abs(d.x - d.x0) < 6) return;
    dragged = true;
    setTimeout(() => { dragged = false; }, 0);      // the click that follows the mouseup is not a click on a point
    zoomHistory(timeAt(Math.min(d.x0, d.x)), timeAt(Math.max(d.x0, d.x)));
  });
  svg.addEventListener("dblclick", e => { e.preventDefault(); resetHistoryZoom(); });
  svg.addEventListener("mousemove", e => {
    if (drag && Math.abs(drag.x - drag.x0) >= 6) return;
    const p = histNearest(e);
    svg.innerHTML = histBase + histOverlay(histPin, true) + (p && p !== histPin ? histOverlay(p, false) : "");
    histDots(histPin, p);
    if (!p) { tip.classList.add("hidden"); return; }
    tip.innerHTML = ""; histTipText(p).forEach((r, i) => tip.append(i ? h("div", {}, r) : h("b", {}, r)));
    tip.classList.remove("hidden");
    const wrap = svg.parentElement.getBoundingClientRect(), x = e.clientX - wrap.left;
    tip.style.left = Math.min(Math.max(0, x + 12), wrap.width - tip.offsetWidth) + "px";
    tip.style.top = "8px";
  });
  svg.addEventListener("mouseleave", () => { tip.classList.add("hidden"); svg.innerHTML = histBase + histOverlay(histPin, true); histDots(histPin); });
  svg.addEventListener("click", e => {
    if (dragged) return;
    const p = histNearest(e);
    if (histPin && (!p || p === histPin)) return unpinHistory();
    if (!p) return;
    histPin = p; drawHistory();
  });
  document.addEventListener("keydown", e => {
    if (e.key !== "Escape") return;
    if (histPin) unpinHistory(!histZoom);
    else if (histZoom) resetHistoryZoom();
  });
})();

function downloadHistory(fmt) {
  // served by uwccd with Content-Disposition: works in Edge (Windows) and in the WebKitGTK window (Linux)
  const a = h("a", { href: `/api/history/export?format=${fmt}&range=${histRange}&token=${encodeURIComponent(TOKEN)}`, download: "" });
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
    x.fillText(`${t(d.name)} — ${t((HIST_RANGES.find(r => r[0] === histRange) || [0, "1 hour"])[1])} — ${new Date().toLocaleString()}`, 12, 26);
    x.drawImage(img, 0, 40, W, H);
    c.toBlob(b => {
      const a = h("a", { href: URL.createObjectURL(b), download: `uwcc-${histKey}-${Date.now()}.png` });
      document.body.append(a); a.click(); a.remove();
    }, "image/png");
  };
  img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(xml.replace("<svg", `<svg width="${W}" height="${H}"`));
}
$("#hist-export-btn").addEventListener("click", e => { e.stopPropagation(); $("#hist-export-menu").classList.toggle("hidden"); });
$$("#hist-export-menu button").forEach(b => b.addEventListener("click", () => {
  $("#hist-export-menu").classList.add("hidden");
  if (b.dataset.fmt === "png") downloadChartPng(); else downloadHistory(b.dataset.fmt);
}));
document.addEventListener("click", () => $("#hist-export-menu").classList.add("hidden"));

// ---------------------------------------------------------------- about / updates
function renderAbout() {
  const u = S.update || {};
  const a = (href, text) => h("a", { href, target: "_blank", rel: "noopener" }, text);
  const dl = $("#about-kv"); dl.innerHTML = "";
  const b = u.build || {};
  const ver = [u.current || "—", b.date ? `${t("build")} ${b.date}` : "", b.commit || "", b.source === "checkout" ? "dev" : ""].filter(Boolean).join(" · ");
  const mail = u.contact || "OUCC@aspidov.ru";
  const rows = [[t("Program"), "open-uniwill-cc"], [t("Version"), ver],
    [t("Source code"), a(u.repo || "https://github.com/aspidovss/open-uniwill-cc", (u.repo || "").replace("https://", "") || "github.com/aspidovss/open-uniwill-cc")],
    [t("License"), "MIT (kernel/: GPL-2.0)"], [t("Report a problem"), a((u.repo || "") + "/issues", t("GitHub issues"))],
    [t("Email"), h("a", { href: "mailto:" + mail }, mail)]];
  for (const [k, v] of rows) dl.append(h("dt", {}, k), h("dd", {}, v));
  let txt;
  if (u.error) txt = t("Update check failed: {0}", u.error);
  else if (u.newer) txt = t("Version {0} is available.", u.latest);
  else if (u.checked) txt = t("You have the latest version (checked {0}).", new Date(u.checked * 1000).toLocaleString());
  else txt = u.enabled ? t("Updates are checked automatically once a day.") : t("Automatic update check is off (Settings → Switches).");
  $("#upd-text").innerHTML = "";
  $("#upd-text").append(txt);
  if (u.newer) {
    $("#upd-text").append(" ", a(u.url, t("What's new")));
    if (!u.can_install) $("#upd-text").append(h("br"), t("Linux: download the archive from the release page and run sudo bash install.sh in it."));
  }
  const dlst = u.download || {};
  const busy = ["requested", "downloading"].includes(dlst.state);
  if (u.newer && u.can_install && dlst.state) {
    const msg = {
      requested: t("Starting the download…"),
      downloading: t("Downloading… {0}%", dlst.percent ?? 0),
      verified: t("Downloaded and verified: {0}", dlst.path || ""),
      started: t("The installer is running — confirm the Windows prompt. File: {0}", dlst.path || ""),
      declined: t("The installer is in your Downloads folder, run it to update: {0}", dlst.path || ""),
      error: t("Update failed: {0}", dlst.error || ""),
    }[dlst.state];
    if (msg) $("#upd-text").append(h("br"), h("span", { class: dlst.state === "error" ? "warn-text" : "" }, msg));
  }
  const ib = $("#upd-install");
  ib.classList.toggle("hidden", !(u.newer && u.can_install && u.setup));
  ib.disabled = busy;
}
$("#upd-check").addEventListener("click", () => act(async () => { S.update = await api("update/check", {}); renderAbout(); },
  null));
$("#upd-install").addEventListener("click", () => act(async () => {
  if (!confirm(t("Download version {0} to your Downloads folder, check its checksum and start the installer?", S.update.latest))) return;
  const r = await api("update/download", {});
  if (!r.tray) {                                     // the tray app downloads; without it open the release page
    toast(t("The Control Center tray app is not running — opening the release page."));
    window.open(r.url || S.update.url, "_blank");
  }
}));

// ---------------------------------------------------------------- diagnostic report
const REP_SECTIONS = [["system", "System, BIOS and EC versions"], ["platform", "Platform, modes, fan tables and profiles"],
  ["ec", "EC registers (read only)"], ["bios", "BIOS settings: UniWillVariable, SmartAPC limits"],
  ["acpi", "ACPI tables of the firmware (without the Windows licence tables)"],
  ["firmware", "EC interface devices (ACPI / WMI) and their drivers"],
  ["selfcheck", "Self-check, stage 1 (read only): what works on this laptop, a draft platform profile"],
  ["clevo", "Control Center 3.0 / Clevo: interface, driver, Control Center 3 app, capability words and fan buffers (read only)"],
  ["oem_registry", "Settings and feature flags of the original Control Center (registry, Windows)"],
  ["oem_software", "Services, packages and versions of the original Control Center (Windows)"],
  ["oem_files", "Settings files, tables and logs of the original Control Center (Windows)"],
  ["oem_files_full", "Original Control Center folders complete, programs included (large, up to 400 MB)", false],
  ["power", "Power plans / power profiles"],
  ["lighting", "Keyboard and light bar devices (HID)"], ["nvidia", "NVIDIA: driver, limits, Dynamic Boost"],
  ["sensors", "Sensors and the last 15 minutes of history"], ["original", "Fan tables and profiles of the original Control Center"],
  ["cooler", "Liquid cooler"], ["log", "Service log"], ["settings", "Program settings"]];
const REP_PRIVATE = [["serial", "Serial numbers of the laptop and the board", "to tell firmware batches of one model apart"],
  ["uuid", "System UUID", "to match several reports from one laptop"],
  ["mac", "MAC addresses (network, Bluetooth, cooler)", "for liquid cooler connection problems"],
  ["names", "Computer name and user name in paths", "for problems with paths and permissions"],
  ["apps", "Programs from App binding and processes on the GPU", "for automatic mode switching problems"]];
let repLang = null;
function renderReportCard() {                      // rebuilt only when the language changes; keeps the ticks
  const sec = $("#rep-sections"), pri = $("#rep-private");
  if (repLang === LANG) return;
  repLang = LANG;
  const was = Object.fromEntries($$("#report-card input[data-k]").map(i => [i.dataset.k, i.checked]));
  const box = (k, def) => { const i = h("input", { type: "checkbox", "data-k": k }); i.checked = k in was ? was[k] : def; return i; };
  sec.innerHTML = ""; pri.innerHTML = "";
  for (const [k, n, def = true] of REP_SECTIONS) sec.append(h("label", { class: "chk" }, box(k, def), " ", h("span", {}, t(n))));
  for (const [k, n, why] of REP_PRIVATE) pri.append(h("label", { class: "chk" }, box(k, false), " ",
    h("span", {}, t(n), h("small", { class: "muted" }, " — " + t(why)))));
}
async function makeReport() {
  // the report is built in the background (it can take a minute on Windows); the file is downloaded with a click
  // on a link, so the browser treats every download as one the user asked for
  const pick = sel => $$(sel + " input:checked").map(i => i.dataset.k);
  let sum = {};
  try { sum = await api("report/summary"); } catch (_) {}
  const d = new Date(), z = n => String(n).padStart(2, "0");
  const stamp = `${d.getFullYear()}${z(d.getMonth() + 1)}${z(d.getDate())}-${z(d.getHours())}${z(d.getMinutes())}${z(d.getSeconds())}`;
  const name = `uwcc-report-${String(sum.model || sum.project || "laptop").replace(/[^\w.-]+/g, "-").slice(0, 40)}-${stamp}.zip`;
  const sections = pick("#rep-sections");
  let st = await api("report/start", { sections, private: pick("#rep-private"), name });
  const box = $("#rep-done"); box.classList.remove("hidden");
  const btn = $("#rep-make"); btn.disabled = true;
  try {
    while (st.state === "running") {
      box.innerHTML = "";
      box.append(h("p", {}, h("b", {}, t("Collecting the report… {0} s", Math.round(st.elapsed || 0)))),
        h("p", { class: "muted tiny" }, t("On Windows this takes up to a minute or two. You can leave this page.")));
      await new Promise(r => setTimeout(r, 1000));
      st = await api("report/status");
    }
  } finally { btn.disabled = false; }
  if (st.state !== "done") throw new Error(st.error || "report failed");
  showReport(st, sum);
}
function showReport(st, sum) {
  const name = st.name;
  const repo = (S.update && S.update.repo) || "https://github.com/aspidovss/open-uniwill-cc";
  const mail = (S.update && S.update.contact) || "OUCC@aspidov.ru";
  const lines = Object.entries(sum || {}).filter(([, v]) => typeof v !== "object").map(([k, v]) => `- ${k}: ${v}`).join("\n");
  const title = `Report: ${sum.vendor || ""} ${sum.model || sum.project || ""}`.replace(/\s+/g, " ").trim();
  const body = `${t("Describe the problem or the laptop here.")}\n\n${lines}\n\n${t("Attached: {0}", name)}\n`;
  const issue = `${repo}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`;
  const mailto = `mailto:${mail}?subject=${encodeURIComponent("open-uniwill-cc: " + title)}&body=${encodeURIComponent(body)}`;
  const reveal = async () => { try { const x = await api("reveal", { name }); if (!x.tray) toast(t("The file is in your Downloads folder: {0}", name)); } catch (_) {} };
  const mb = !st.size ? "?" : st.size < 1048576 ? (st.size / 1048576).toFixed(2) : (st.size / 1048576).toFixed(1);
  const box = $("#rep-done"); box.innerHTML = ""; box.classList.remove("hidden");
  const dl = h("a", { class: "btn", href: `/api/report/file?id=${encodeURIComponent(st.id)}&token=${encodeURIComponent(TOKEN)}`, download: name },
    "⤓ " + t("Download the report ({0} MB)", mb));
  box.append(h("p", {}, h("b", {}, "✓ " + t("The report is ready: {0}", name)), " ", h("span", { class: "muted tiny" }, t("collected in {0} s", st.elapsed))),
    h("div", { class: "row wrap" }, dl),
    h("p", { class: "muted tiny", style: "margin-top:10px" }, t("It is saved to your Downloads folder. GitHub and e-mail cannot attach files by themselves: drag the file into the issue or the letter.")),
    h("div", { class: "row wrap" },
      h("button", { class: "btn ghost", onclick: () => { window.open(issue, "_blank"); reveal(); } }, t("Create a GitHub issue")),
      h("button", { class: "btn ghost", onclick: () => { location.href = mailto; reveal(); } }, t("Send by e-mail")),
      h("button", { class: "btn ghost", onclick: reveal }, t("Show the file"))));
}
$("#rep-make").addEventListener("click", () => act(makeReport, t("Report ready")));

// ---------------------------------------------------------------- export / import
function download(url) {
  const a = h("a", { href: url + (url.includes("?") ? "&" : "?") + "token=" + encodeURIComponent(TOKEN), download: "" });
  document.body.append(a); a.click(); a.remove();
  toast(t("Export started — the file goes to your Downloads folder"));
}
async function readJsonFiles(input) {
  const files = [...input.files]; input.value = "";
  const out = [];
  for (const f of files) {
    try { out.push(JSON.parse(await f.text())); } catch (_) { throw new Error(t("{0} is not a JSON file", f.name)); }
  }
  return out.length === 1 ? out[0] : { files: out };
}
async function doImport(data, sections) {
  let res;
  try { res = await api("import", { data, sections }); }
  catch (e) {
    if (!String(e.message).includes("project")) throw e;
    if (!confirm(e.message + "\n\n" + t("Import anyway?"))) return;
    res = await api("import", { data, sections, force: true });
  }
  const parts = [];
  if (res.tables.length) parts.push(t("fan tables: {0}", res.tables.join(", ")));
  if (res.profiles.length) parts.push(t("profiles: {0}", res.profiles.length));
  if (res.settings) parts.push(t("other settings — the service restarts"));
  toast(parts.length ? t("Imported") + ": " + parts.join("; ") : t("Nothing was imported"), !parts.length);
  if (res.skipped.length) console.warn("import skipped", res.skipped);
  edit = null; pe = null;
  if (res.restart) setTimeout(() => location.reload(), 6000);
}
$("#fan-io").addEventListener("change", e => {
  const v = e.target.value; e.target.value = "";
  if (v === "export-one") download(`/api/export?what=fans&table=${curTable}`);
  else if (v === "export-all") download("/api/export?what=fans");
  else if (v === "import") $("#fan-io-file").click();
});
$("#fan-io-file").addEventListener("change", e => act(async () => {
  const data = await readJsonFiles(e.target);
  // one table: load it into the editor as a preview, Save writes it
  const tables = data.tables ? Object.values(data.tables) : (Array.isArray(data.CPU) ? [data] : null);
  if (tables && tables.length === 1 && !data.profiles) {
    const tb = tables[0];
    edit = { ...JSON.parse(JSON.stringify(S.tables[curTable])), CPU: tb.CPU, GPU: tb.GPU || S.tables[curTable].GPU };
    drawCurve(); drawPts();
    return toast(t("Loaded into the editor for “{0}” — check the curve and press Save", TABLE_LABEL[curTable] || curTable));
  }
  if (!confirm(t("Import fan tables from the file? Tables with the same names are replaced."))) return;
  await doImport(data, ["fans"]);
}));
$("#bk-export").addEventListener("click", () => download("/api/export?what=all"));
$("#bk-import").addEventListener("click", () => $("#bk-file").click());
function bkSections() { return ["fans", "profiles", "settings"].filter(k => $("#bk-" + k).checked); }
$("#bk-file").addEventListener("change", e => act(async () => {
  const data = await readJsonFiles(e.target), sec = bkSections();
  if (!sec.length) return toast(t("Choose what to import"), true);
  if (!confirm(t("Replace the current settings with the ones from the file?"))) return;
  await doImport(data, sec);
}));
$("#bk-original").addEventListener("click", () => act(async () => {
  const sec = bkSections().filter(k => k !== "settings");
  if (!confirm(t("Import your fan curves and profiles from the original Control Center? The current ones are replaced."))) return;
  const res = await api("import/original", { sections: sec.length ? sec : ["fans", "profiles"] });
  toast(t("Imported") + ": " + t("fan tables: {0}", res.tables.length) + "; " + t("profiles: {0}", res.profiles.length));
  edit = null; pe = null;
}));
(async () => { try { const o = await api("import/original"); $("#bk-original").classList.toggle("hidden", !o.available); } catch (_) {} })();

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
  renderLoadRules();
}
// ---- automatic profile switching (load rules, 1.6.8)
const AU_METRIC = { cpu_power: "CPU power", gpu_power: "GPU power", total_power: "CPU + GPU power", cpu_temp: "CPU temperature",
  gpu_temp: "GPU temperature", cpu_load: "CPU load", gpu_load: "GPU load" };
const AU_TEMPLATES = [
  ["heavy", "Heavy load → Turbo", { name: "Heavy load", conditions: [{ metric: "total_power", op: ">", value: 120 }], hold: 30, mode: 2, slot: null, back: true, back_after: 60 }],
  ["light", "Light load → Office", { name: "Light load", conditions: [{ metric: "cpu_power", op: "<", value: 15 }], hold: 60, mode: 0, slot: null, back: false, back_after: 60 }],
  ["hot", "Hot → Gaming", { name: "Hot", conditions: [{ metric: "cpu_temp", op: ">", value: 90 }, { metric: "gpu_temp", op: ">", value: 85 }], join: "or", hold: 20, mode: 1, slot: null, back: true, back_after: 120 }],
  ["empty", "Empty rule", { name: "", conditions: [{ metric: "cpu_power", op: ">", value: 50 }], hold: 30, mode: 1, slot: null, back: false, back_after: 60 }],
];
let auRules = null, auDirty = false;
function renderLoadRules() {
  const R = S.load_rules; if (!R) return;
  if (!auDirty || !auRules) auRules = JSON.parse(JSON.stringify(R.rules || []));
  $("#au-rules-mon").classList.toggle("hidden", (S.monitoring || "full") === "full");
  const tpl = $("#au-rule-tpl"); if (!tpl.options.length || tpl.dataset.lang !== LANG) {
    tpl.innerHTML = ""; tpl.dataset.lang = LANG; for (const [id, n] of AU_TEMPLATES) tpl.append(h("option", { value: id }, t(n)));
  }
  const box = $("#au-rules"); if (box.contains(document.activeElement) && document.activeElement.tagName !== "BUTTON") return;
  box.innerHTML = "";
  if (!auRules.length) { box.append(h("p", { class: "muted" }, t("No rules yet"))); return; }
  const modes = MODES.filter(m => (m.id !== 3 || S.power.custom_support) && (m.id !== 2 || S.power.turbo_support));
  const change = () => { auDirty = true; };
  const sel = (opts, val, on) => { const e = h("select", {}, ...opts.map(([v, n]) => { const o = h("option", { value: v }, n); if (String(val) === String(v)) o.selected = true; return o; })); e.addEventListener("change", () => { on(e.value); change(); renderLoadRules(); }); return e; };
  const num = (val, min, max, on) => { const e = h("input", { type: "number", class: "num", min, max, value: val }); e.addEventListener("change", () => { on(+e.value); change(); }); return e; };
  auRules.forEach((r, i) => {
    const active = R.active === i && !auDirty, held = (R.held || {})[i];
    const en = h("input", { type: "checkbox", ...(r.enabled !== false ? { checked: true } : {}) }); en.addEventListener("change", () => { r.enabled = en.checked; change(); });
    const name = h("input", { type: "text", maxlength: 40, value: r.name || "", placeholder: t("Rule {0}", i + 1) }); name.addEventListener("change", () => { r.name = name.value; change(); });
    const move = (d) => { const j = i + d; if (j < 0 || j >= auRules.length) return; [auRules[i], auRules[j]] = [auRules[j], auRules[i]]; change(); renderLoadRules(); };
    const head = h("div", { class: "row between wrap" }, h("div", { class: "row wrap" }, h("label", { class: "chk" }, en), name,
      active ? h("span", { class: "badge-on" }, t("active")) : held != null && !auDirty ? h("span", { class: "muted tiny" }, t("holds {0} of {1} s", held, r.hold)) : ""),
      h("div", { class: "row" }, h("button", { class: "btn ghost sm", title: t("Up"), onclick: () => move(-1) }, "↑"), h("button", { class: "btn ghost sm", title: t("Down"), onclick: () => move(1) }, "↓"),
        h("button", { class: "btn ghost sm", onclick: () => { auRules.splice(i, 1); change(); renderLoadRules(); } }, t("Delete"))));
    const conds = h("div", { class: "au-conds" });
    r.conditions.forEach((c, k) => {
      if (k) conds.append(sel([["and", t("and")], ["or", t("or")]], r.join || "and", v => { r.join = v; }));
      conds.append(h("span", { class: "au-cond" },
        sel(Object.entries(AU_METRIC).map(([v, n]) => [v, t(n)]), c.metric, v => { c.metric = v; }),
        sel([[">", t("above")], ["<", t("below")]], c.op, v => { c.op = v; }),
        num(c.value, 0, 1000, v => { c.value = v; }), h("span", { class: "muted" }, t(R.metrics[c.metric] === "W" ? "W" : R.metrics[c.metric] || "")),
        r.conditions.length > 1 ? h("button", { class: "btn ghost sm", onclick: () => { r.conditions.splice(k, 1); change(); renderLoadRules(); } }, "✕") : ""));
    });
    if (r.conditions.length < 3) conds.append(h("button", { class: "btn ghost sm", onclick: () => { r.conditions.push({ metric: "gpu_power", op: ">", value: 50 }); change(); renderLoadRules(); } }, t("+ condition")));
    const key = { 0: "office", 1: "gaming", 2: "turbo", 3: "custom" }[r.mode], nslots = (S.power.slots || {})[key] || 1;
    const slotOpts = [["", t("current profile")], ...Array.from({ length: nslots }, (_, j) => [j, r.mode === 3 ? slotName(S.profiles["Mode4_Profile" + (j + 1)], j + 1) : t("profile {0}", j + 1)])];
    const act1 = h("div", { class: "row wrap au-line" }, h("span", {}, t("for")), num(r.hold, 1, 3600, v => { r.hold = v; }), h("span", {}, t("s → switch to")),
      sel(modes.map(m => [m.id, t(m.name)]), r.mode, v => { r.mode = +v; r.slot = null; }),
      sel(slotOpts, r.slot ?? "", v => { r.slot = v === "" ? null : +v; }));
    const bk = h("input", { type: "checkbox", ...(r.back ? { checked: true } : {}) }); bk.addEventListener("change", () => { r.back = bk.checked; change(); });
    const act2 = h("div", { class: "row wrap au-line" }, h("label", { class: "chk" }, bk, " ", h("span", {}, t("then return to the previous mode when it has not held for"))),
      num(r.back_after, 1, 3600, v => { r.back_after = v; }), h("span", {}, t("s")));
    box.append(h("div", { class: "au-rule" + (active ? " on" : "") }, head, h("div", { class: "au-line" }, h("b", {}, t("If")), " ", conds), act1, act2));
  });
}
$("#au-rule-add").addEventListener("click", () => {
  const tp = AU_TEMPLATES.find(x => x[0] === $("#au-rule-tpl").value) || AU_TEMPLATES[0];
  if (!auRules) auRules = [];
  const r = JSON.parse(JSON.stringify(tp[2])); r.name = r.name ? t(r.name) : ""; r.enabled = true;
  if (r.mode === 2 && !S.power.turbo_support) r.mode = 1;
  auRules.push(r); auDirty = true; renderLoadRules();
});
$("#au-rules-save").addEventListener("click", () => act(async () => { await api("load-rules", { rules: auRules || [] }); auDirty = false; }, t("Saved")));
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

// ---------------------------------------------------------------- live events
let connState = "wait";
let connLostAt = null, connTimer = null;
function paintConn() {
  $("#conn").className = "conn" + (connState === "ok" ? " ok" : "");
  $("#conn span:last-child").textContent = t({ ok: "Service connected", err: "No connection to the service" }[connState] || "Connecting…");
  // after a minute without the service: how to restart it (the window cannot do it without the service)
  if (connState === "ok") { connLostAt = null; clearTimeout(connTimer); $("#svc-down").classList.add("hidden"); return; }
  connLostAt = connLostAt || Date.now();
  clearTimeout(connTimer);
  connTimer = setTimeout(() => {
    if (connState === "ok") return;
    const win = /Windows/.test(navigator.userAgent);
    $("#svc-down").textContent = win
      ? t("The service has not answered for a minute. Restart it: right-click the Control Center icon in the tray → “Restart the service”.")
      : t("The service has not answered for a minute. Restart it from the notification of the Control Center agent or with: sudo systemctl restart uwccd");
    $("#svc-down").classList.remove("hidden");
  }, Math.max(0, 60000 - (Date.now() - connLostAt)));
}
$("#svc-restart").addEventListener("click", () => act(async () => {
  if (!confirm(t("Restart the Control Center service? Fan control is handed to the laptop for a few seconds."))) return;
  await api("service/restart", {});
  toast(t("The service is restarting…"));
}));
function connect() {
  const es = new EventSource("/api/events?token=" + encodeURIComponent(TOKEN));
  es.onopen = () => { connState = "ok"; paintConn(); };
  es.onerror = () => { connState = "err"; paintConn(); };
  let pending = null;
  es.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.type === "monitor") return onMonitor(m.data);
    if (m.type === "busy") { renderBusy(m.data.ops || []); if (S) S.busy = m.data.ops || []; }
    if (m.type === "restarting") showRestart();
    if (m.type === "selfcheck_backup") { scBackup = m.data; renderBusy((S && S.busy) || []); }
    if (m.type === "selfcheck_restore") { scBackup = null; renderBusy((S && S.busy) || []); showRestoreResult(m.data); }
    if (m.type === "admin") { if (S && S.ec_access) S.ec_access.admin = m.data; renderAdmin(); if (m.data.declined) toast(t("Administrator rights were not granted"), true); }
    if (m.type === "mode" && m.data.osd) osd(m.data.mode === 3 ? `Custom · ${slotName(S?.profiles?.["Mode4_Profile" + ((m.data.slot || 0) + 1)], (m.data.slot || 0) + 1)}` : (MODES[m.data.mode]?.osd || ""));
    if (m.type === "overheat") toast(t("{0} at {1} °C for 30 seconds", m.data.sensor === "gpu" ? t("GPU") : t("CPU"), m.data.temp), true);
    if (m.type === "overheat_boost") toast(t("Fan Boost turned on because of overheating"), true);
    if (m.type === "load_rule") toast(t("Automation: {0} → {1}", m.data.rule === "back" ? t("back") : m.data.rule, t((MODES[m.data.mode] || {}).name || "")));
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
  if (S && S.settings && (S.settings.eula_accepted || 0) < (S.settings.eula_version || 1)) await showAgreement();
  await offerWmiIfNoDriver();
  connect();
})();

// ---------------------------------------------------------------- user agreement (first start)
function showAgreement() {
  return new Promise(resolve => {
    const text = h("pre", { class: "eula-text" }), chk = h("input", { type: "checkbox", id: "eula-chk" });
    const accept = h("button", { class: "btn", disabled: "" }), decline = h("button", { class: "btn ghost" });
    const title = h("h2"), lbl = h("label", { for: "eula-chk" }), langs = h("div", { class: "seg" });
    const load = async () => {
      title.textContent = t("User agreement"); lbl.textContent = t("I have read the agreement and accept it");
      accept.textContent = t("Accept"); decline.textContent = t("Decline");
      try {
        const r = await fetch(`eula.${LANG}.txt`, { cache: "no-cache" });
        text.textContent = (await r.text()).replace(/^\uFEFF/, "").replace(/\r/g, "");
      } catch (e) { text.textContent = t("Service unavailable: {0}", e.message); }
      text.scrollTop = 0;
      langs.querySelectorAll("button").forEach(b => b.classList.toggle("on", b.dataset.lang === LANG));
    };
    for (const l of ["en", "ru"]) langs.append(h("button", { "data-lang": l, onclick: () => { setLang(l, true); load(); } }, l.toUpperCase()));
    chk.addEventListener("change", () => { accept.disabled = !chk.checked; });
    const box = h("div", { class: "eula", role: "dialog", "aria-modal": "true" },
      h("div", { class: "eula-card" },
        h("div", { class: "row between" }, title, langs), text,
        h("div", { class: "eula-foot" }, h("div", { class: "eula-check" }, chk, lbl), h("div", { class: "row" }, decline, accept))));
    accept.addEventListener("click", async () => {
      accept.disabled = true;
      try { await api("setting", { key: "eula_accepted", value: S.settings.eula_version || 1 }); box.remove(); resolve(); }
      catch (e) { accept.disabled = false; toast(t("Service unavailable: {0}", e.message), true); }
    });
    decline.addEventListener("click", () => {
      box.querySelector(".eula-card").replaceChildren(h("h2", {}, t("User agreement")),
        h("p", { class: "muted" }, t("The agreement was not accepted. Control Center cannot be used without it — close this window or uninstall the program.")),
        h("div", { class: "row" }, h("button", { class: "btn", onclick: () => { box.remove(); showAgreement().then(resolve); } }, t("Read again"))));
      try { window.close(); } catch (_) {}
    });
    document.body.append(box); load();
  });
}

// ---------------------------------------------------------------- EC Manager: OEM driver / WMI (Windows)
const EC_FEATURES = {
  modes: { name: "Modes and profiles", sel: ["#mode-cards", "#profile-seg", "#btn-restore"] },
  fan_boost: { name: "Fan Boost", sel: ["#fanboost-card"] },
  power_limits: { name: "CPU power limits and TCC", sel: ["#profile-editor"] },
  gpu_power: { name: "Graphics power (cTGP, Dynamic Boost)", sel: [] },
  super_performance: { name: "Super performance", sel: ["#sp-row"] },
  fan_tables: { name: "Fan curves", sel: ["#page-fans .card"] },
  fan_monitor: { name: "Fan speed readings", sel: [] },
  battery: { name: "Battery protection and charge limits", sel: ["#page-battery .card"] },
  switches: { name: "Switches (Fn Lock, Win key, USB, touchpad)", sel: ["#switch-list"] },
  lightbar_ec: { name: "Light bar (EC trigger)", sel: [] },
  lc_ec: { name: "Liquid cooler: EC targets and flag", sel: [] },
  power_boost_lc: { name: "Power boost with liquid cooling", sel: ["#lc-hwoc-box"] },
};
const EC_PATHS = [
  { id: "auto", name: "OEM driver + WMI", tag: "recommended", rec: true, desc: "The manufacturer's UWACPIDriver.sys — full functions and full speed. WMI is used only when the driver is missing and you agreed." },
  { id: "oem", name: "OEM driver only", tag: "", desc: "Only UWACPIDriver.sys. Without it the program cannot reach the EC." },
  { id: "wmi", name: "WMI only — open implementation", tag: "not recommended · beta", desc: "No proprietary files: the Windows built-in WMI driver. Slow, no liquid-cooling power boost, approximate limits." },
];
const ecA = () => (S && S.ec_access) || null;
const ecWin = () => { const a = ecA(); return !!(a && a.windows); };

function applyFeatures() {
  const a = ecA();
  const feats = (a && a.features) || {};
  for (const [k, f] of Object.entries(EC_FEATURES)) {
    const st = feats[k] || "on";
    const els = [...f.sel.flatMap(s => $$(s)), ...$$(`[data-feature="${k}"]`)];
    for (const el of els) {
      el.classList.toggle("feat-off", st === "off");
      el.classList.toggle("feat-slow", st === "slow");
      el.dataset.featText = st === "off" ? (a && a.active === "none" ? t("no EC access") : t("not available with WMI")) : st === "slow" ? t("slow with WMI") : "";
      el.inert = st === "off";
    }
  }
}

function renderEcBanner() {
  const a = ecA(), b = $("#ec-banner"), badge = $("#wmi-badge");
  $("#nav-driver").classList.toggle("hidden", !ecWin());
  badge.classList.toggle("hidden", !(a && a.active === "wmi"));
  const show = a && a.active === "none";
  b.classList.toggle("hidden", !show);
  if (!show) return;
  const msg = { oem_missing: t("The OEM driver UWACPIDriver was not found — the program cannot reach the embedded controller (fans, modes, power limits, battery). Install the OEM driver (recommended) or switch to the open WMI implementation (beta)."),
    wmi_consent: t("The WMI path is selected, but its warning has not been accepted yet."),
    wmi_failed: t("The WMI path could not be opened: {0}", a.wmi_error || ""),
    clevo_only: t("This laptop has no Uniwill embedded controller interface but a Control Center 3.0 / Clevo one: modes, fans and backlight are on the Clevo (experimental) page; the Uniwill pages do not work here.") }[a.reason] || t("No access to the embedded controller.");
  b.replaceChildren(h("div", {}, h("b", {}, t("No access to the embedded controller")), h("p", {}, msg)),
    a.reason === "clevo_only" ? h("button", { class: "btn", onclick: () => $(`#nav a[data-page="clevo"]`)?.click() }, t("Open the Clevo page"))
      : h("button", { class: "btn", onclick: () => $(`#nav a[data-page="driver"]`)?.click() }, t("Open EC Manager")));
}
$("#wmi-badge").addEventListener("click", () => $(`#nav a[data-page="driver"]`)?.click());
$("#info-ec-open").addEventListener("click", () => $(`#nav a[data-page="driver"]`)?.click());

const PATH_NAME = { oem: "OEM driver (UWACPIDriver)", wmi: "WMI (open implementation, beta)", none: "none", native: "kernel module / acpi_call", mock: "simulation" };
function ecKv(a) {
  const d = a.driver || {};
  return [[t("Active path"), t(PATH_NAME[a.active] || a.active || "—")],
    [t("Selected"), t((EC_PATHS.find(p => p.id === a.setting) || {}).name || a.setting)],
    [t("OEM driver"), a.oem_present === null || a.oem_present === undefined ? "—" : a.oem_present
      ? t("installed") + (d.version ? ` · ${d.version}${d.date ? " (" + d.date + ")" : ""}` : "") : t("not found")],
    [t("WMI warning"), a.consent ? t("accepted") : t("not accepted")],
    ...(a.active === "wmi" && a.stats ? [[t("EC accesses"), t("{0} reads ({1} from cache), {2} writes ({3} skipped)", a.stats.reads, a.stats.cached, a.stats.writes, a.stats.skipped)]] : [])];
}

function renderDriver() {
  const a = ecA();
  if (!a || !a.windows) return;
  const dl = (el, rows) => { el.innerHTML = ""; for (const [k, v] of rows) el.append(h("dt", {}, k), h("dd", {}, v ?? "—")); };
  dl($("#dm-kv"), ecKv(a));
  $("#dm-docs").href = a.docs;
  const box = $("#dm-choices"); box.innerHTML = "";
  for (const p of EC_PATHS) box.append(h("div", { class: "choice" + (a.setting === p.id ? " on" : "") + (p.id === "wmi" ? " risky" : "") + (p.rec ? " rec" : ""),
    onclick: () => chooseEcPath(p.id) },
    h("h4", {}, t(p.name), p.tag ? h("span", { class: "tag" + (p.id === "wmi" ? " bad" : "") + (p.rec ? " good" : "") }, t(p.tag)) : null), h("p", {}, t(p.desc))));
  renderAdmin(); renderEdition(a); renderPlatform(a); renderMonitoring(a); renderSelfcheck(a); setupCollapsible();
  // info page block
  $("#info-ec").classList.remove("hidden");
  dl($("#info-ec-kv"), ecKv(a));
  $("#info-ec-note").textContent = a.active === "wmi" ? t("WMI path: about 125 ms per EC access, no liquid-cooling power boost (PWUP), limits from the WMI settings instead of the firmware table (SMRW).") + " " +
    t("The extra graphics power is reached only in the stock Turbo mode.") : "";
  if (!dmDirty) renderWmiConfig(a);
}

let dmCfg = null, dmDirty = false;
function renderWmiConfig(a) {
  dmCfg = JSON.parse(JSON.stringify(a.config));
  const f = $("#dm-features"); f.innerHTML = "";
  for (const fl of a.feature_list) {
    const k = fl.key, sel = h("select", { disabled: fl.locked ? true : null });
    for (const v of ["on", "slow", "off"]) { const o = h("option", { value: v }, t({ on: "available", slow: "available, slow", off: "off" }[v])); if (dmCfg.features[k] === v) o.selected = true; sel.append(o); }
    sel.addEventListener("change", () => { dmCfg.features[k] = sel.value; dmDirty = true; });
    f.append(h("div", { class: "dm-item" }, h("span", {}, t((EC_FEATURES[k] || {}).name || k), fl.locked ? h("small", { class: "muted" }, " · " + t("needs the OEM driver")) : null), sel));
  }
  const num = (parent, label, obj, key, min, max, step) => {
    const i = h("input", { type: "number", min, max, step: step || 1, value: obj[key] });
    i.addEventListener("input", () => { obj[key] = +i.value; dmDirty = true; });
    parent.append(h("div", { class: "dm-item" }, h("span", {}, label), i));
  };
  const p = $("#dm-params"); p.innerHTML = "";
  num(p, t("Read cache, ms"), dmCfg.poll, "cache_ms", 0, 60000, 500);
  num(p, t("Monitor interval, s"), dmCfg.poll, "monitor_s", 1, 60);
  num(p, t("WMI call timeout, s"), dmCfg, "timeout_s", 1, 30);
  const inst = h("input", { type: "text", value: dmCfg.instance, maxlength: 32 });
  inst.addEventListener("input", () => { dmCfg.instance = inst.value; dmDirty = true; });
  p.append(h("div", { class: "dm-item" }, h("span", {}, t("WMI instance (suffix)")), inst));
  const pid = "0x" + (S.platform.project_id || 0).toString(16).toUpperCase().replace(/^0X/, "");
  const key = Object.keys(dmCfg.limits || {}).find(k => parseInt(k, 16) === S.platform.project_id) || pid;
  dmCfg.limits = dmCfg.limits || {};
  const lim = dmCfg.limits[key] || (dmCfg.limits[key] = { PL1: 0, PL2: 0, PL4: 0, TccOffset: 15, ConfigurableTGP: 0, DynamicBoost: 0, TargetTemperature: 87, DefaultTGP: 0, DynamicBoostCpuTdp: 0 });
  $("#dm-limits-title").textContent = t("Limits instead of SMRW (project {0})", key);
  const l = $("#dm-limits"); l.innerHTML = "";
  for (const [k2, lab] of [["PL1", "PL1 max, W"], ["PL2", "PL2 max, W"], ["PL4", "PL4 max, W"], ["TccOffset", "TCC offset max, °C"],
    ["DefaultTGP", "GPU base TGP, W"], ["ConfigurableTGP", "cTGP above base, W"], ["DynamicBoost", "Dynamic Boost max, W"], ["TargetTemperature", "GPU temperature limit, °C"]])
    num(l, t(lab), lim, k2, 0, 255);
  const ls = $("#dm-lists"); ls.innerHTML = "";
  for (const [k2, lab] of [["always_write", "Always write (triggers, handshakes)"], ["no_cache", "Never cache"]]) {
    const i = h("input", { type: "text", value: (dmCfg[k2] || []).join(", ") });
    i.addEventListener("input", () => { dmCfg[k2] = i.value.split(/[\s,]+/).filter(Boolean); dmDirty = true; });
    ls.append(h("div", { class: "dm-item wide" }, h("span", {}, t(lab)), i));
  }
}
function wmiUserConfig() {
  const c = JSON.parse(JSON.stringify(dmCfg));
  delete c.version;
  return c;
}
$("#dm-save").addEventListener("click", () => act(async () => {
  const r = await adminApi("ec-access/config", { config: wmiUserConfig() }); dmDirty = false;
  await refresh();
  if (r.restart_needed) toast(t("Saved. Restart the service to apply polling and limit changes."));
}, t("Saved")));
$("#dm-reset").addEventListener("click", () => act(async () => {
  if (!confirm(t("Restore the factory WMI settings?"))) return;
  await adminApi("ec-access/config", { reset: true }); dmDirty = false; await refresh();
}, t("Factory settings restored")));
$("#dm-export").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify(dmCfg || (ecA() || {}).config, null, 2)], { type: "application/json" });
  const a = h("a", { href: URL.createObjectURL(blob), download: "ec_wmi.json" }); document.body.append(a); a.click(); a.remove();
});
$("#dm-import").addEventListener("click", () => $("#dm-file").click());
$("#dm-file").addEventListener("change", async e => {
  const f = e.target.files[0]; e.target.value = "";
  if (!f) return;
  try {
    const cfg = JSON.parse(await f.text());
    await adminApi("ec-access/config", { config: cfg }); dmDirty = false; await refresh();
    toast(t("WMI settings imported"));
  } catch (err) { toast(t("Import failed: {0}", err.message), true); }
});
$("#dm-test").addEventListener("click", () => act(async () => {
  const r = await api("ec-access/test", {});
  $("#dm-test-out").replaceChildren(
    h("p", {}, t("Path: {0}. Project {1} — {2}. {3} ms per read.", t(PATH_NAME[r.path] || r.path), r.project,
      r.tested_platform ? t("tested platform") : t("NOT a tested platform"), r.ms_per_read)),
    h("p", { class: "tiny" }, r.reads.map(x => `${x.addr} = 0x${x.value.toString(16).toUpperCase().padStart(2, "0")}`).join("  ·  ")));
}, t("Done")));
$("#dm-restart").addEventListener("click", () => act(async () => {
  if (!confirm(t("Restart the Control Center service? Fan control is handed to the laptop for a few seconds."))) return;
  const r = await api("service/restart", {}); if (r.restarting) showRestart(); else toast(t("The service is restarting…"));
}));

async function chooseEcPath(id) {
  const a = ecA();
  if (!a || id === a.setting) return;
  if (id === "wmi" && !a.consent && !(await showWmiWarning())) return;
  if (id === "wmi" && !confirm(t("Use only the open WMI implementation? Not recommended: it is slow and some functions are unavailable."))) return;
  await act(async () => {
    const r = await adminApi("ec-access", { backend: id, ...(id === "wmi" ? { consent: a.consent_version } : {}) });
    if (r.restarting) { showRestart(); return; }
    await refresh();
  });
}

// warning before the first use of the WMI path; resolves true when accepted
function showWmiWarning() {
  const a = ecA();
  return new Promise(resolve => {
    const chk = h("input", { type: "checkbox", id: "wmi-chk" });
    const ok = h("button", { class: "btn", disabled: true }, t("Enable WMI"));
    const cancel = h("button", { class: "btn ghost" }, t("Cancel"));
    const other = a && a.tested === false;
    const box = h("div", { class: "eula", role: "dialog", "aria-modal": "true" },
      h("div", { class: "eula-card" },
        h("h2", {}, t("Open WMI implementation (beta)")),
        h("div", { class: "eula-text wmi-warn" },
          h("p", {}, h("b", {}, t("Why some functions need the OEM driver"))),
          h("p", {}, t("The laptop firmware gives the full set of functions only to the manufacturer's driver UWACPIDriver.sys. Through the WMI interface built into Windows it allows only reading and writing EC registers. Two firmware methods are not reachable there: PWUP — the extra graphics power with the liquid cooler (in tests about 13–15 % lower GPU clock without it) and SMRW — the table of power limits (limits are taken from the WMI settings instead).")),
          h("p", {}, h("b", {}, t("What this implementation is"))),
          h("p", {}, t("An open implementation without proprietary files: the service talks to the firmware through the standard Windows WMI driver. Every EC access takes about 125 ms instead of about 10 ms, so readings update less often and writing a fan curve takes about 15 seconds.")),
          h("p", {}, t("The extra graphics power (175 W instead of 150 W on this platform) is reached only in the stock Turbo mode; in the Custom mode Dynamic Boost adds power only while the processor leaves room.")),
          h("p", {}, t("Changing these settings needs administrator rights: Windows will ask for them (UAC).")),
          h("p", {}, h("b", {}, t("Risks"))),
          h("p", {}, t("This is a beta. On another laptop model the same WMI call may mean something else: a wrong write to the EC can disturb fans, charging or power until the laptop is fully powered off. Use it at your own risk; we recommend the OEM driver.")),
          h("p", { class: "red-warn" }, t("The settings were made for {0} and similar systems; we have not tested other platforms. You can check which functions work on your laptop with the self-check (EC Manager).", a ? a.tested_names : "")),
          other ? h("p", { class: "red-warn" }, t("This laptop reports a different platform!")) : null,
          h("p", {}, h("a", { href: a ? a.docs : "#", target: "_blank", rel: "noopener" }, t("Documentation: EC registers, OEM driver vs WMI (GitHub)")))),
        h("div", { class: "eula-foot" }, h("label", { class: "eula-check" }, chk, h("span", {}, t("I understand the risks"))), h("div", { class: "row" }, cancel, ok))));
    chk.addEventListener("change", () => { ok.disabled = !chk.checked; });
    cancel.addEventListener("click", () => { box.remove(); resolve(false); });
    ok.addEventListener("click", async () => {
      ok.disabled = true;
      try {
        box.remove();
        const r = await adminApi("ec-access", { consent: a.consent_version });
        if (r.restarting) showRestart();
        resolve(true);
      } catch (e) { toast(t("Error: {0}", e.message), true); resolve(false); }
    });
    document.body.append(box);
  });
}

// OEM driver missing on start: recommend it, offer WMI after the warning (once per session)
async function offerWmiIfNoDriver() {
  const a = ecA();
  if (a && a.active === "none" && a.reason === "wmi_consent") {          // WMI chosen (installer / CLI): warning first
    await showWmiWarning();
    return;
  }
  if (!a || a.active !== "none" || a.reason !== "oem_missing" || a.setting !== "auto") return;
  try { if (sessionStorage.getItem("uwcc-oem-offer")) return; sessionStorage.setItem("uwcc-oem-offer", "1"); } catch (_) {}
  await new Promise(resolve => {
    const box = h("div", { class: "eula", role: "dialog", "aria-modal": "true" },
      h("div", { class: "eula-card" },
        h("h2", {}, t("OEM driver not found")),
        h("p", {}, t("The manufacturer's driver UWACPIDriver was not found, so the program cannot control fans, modes, power limits and battery protection.")),
        h("p", {}, h("b", {}, t("Recommended:")), " ", a.edition === "free"
          ? t("put the OEM driver (UWACPIDriver.inf, .sys, .cat from the manufacturer's Control Center) into {0} and install it in EC Manager.", a.driver_dir || "")
          : t("install the OEM driver — run the Control Center installer again and choose \"OEM driver + WMI\", or install the manufacturer's Control Center.")),
        h("p", { class: "muted" }, t("Alternatively you can use the open WMI implementation (beta): slower and without some functions.")),
        h("div", { class: "eula-foot" }, h("span"), h("div", { class: "row" },
          h("button", { class: "btn ghost", onclick: () => { box.remove(); resolve(); } }, t("Later")),
          h("button", { class: "btn ghost", onclick: async () => { box.remove(); await showWmiWarning(); resolve(); } }, t("Use WMI (beta)…"))))));
    document.body.append(box);
  });
}

// ---------------------------------------------------------------- long operations: "Applying…" (WMI path)
var scBackup = null;                                     // backup of the EC values made by self-check stage 2
function showRestoreResult(r) {
  const bad = r.mismatches || [];
  const box = h("div", { class: "eula", role: "dialog", "aria-modal": "true" },
    h("div", { class: "eula-card narrow" },
      h("h2", {}, bad.length ? t("EC values restored, with differences") : t("EC values restored")),
      h("p", {}, t("{0} of {1} controller values read back equal after the test.", r.restored, r.count)),
      bad.length ? h("ul", { class: "sc-unknown" }, ...bad.slice(0, 8).map(x => h("li", {}, x))) : null,
      bad.length ? h("p", { class: "muted tiny" }, t("The controller may change some values itself (fans, mode bits). The current mode profile was applied again.")) : null,
      h("p", { class: "muted tiny" }, t("Backup file: {0}", r.path)),
      h("div", { class: "row end" }, h("button", { class: "btn", onclick: () => box.remove() }, "OK"))));
  document.body.append(box);
}
let localBusy = null;
async function withBusy(label, fn) {             // cover the window at once, before the service answers
  localBusy = { op: "apply", label, blocking: true, progress: null, local: true };
  renderBusy((S && S.busy) || []);
  try { return await fn(); } finally { localBusy = null; renderBusy((S && S.busy) || []); }
}
const BUSY_LABEL = { office: "Office mode", gaming: "Gaming mode", turbo: "Turbo mode", custom: "Custom mode",
  restore: "Factory settings", profile: "Profile", super_performance: "Super performance" };
function renderBusy(ops) {
  const slow = ecA() && ecA().active === "wmi";
  const block = (ops || []).find(o => o.blocking) || (localBusy && slow ? localBusy : null);
  const table = (ops || []).find(o => o.op === "fan_table");
  const ov = $("#busy-overlay");
  if (block) {
    const what = block.op === "selfcheck" ? t("Self-check ({0})", t(block.label || ""))
      : t("Applying: {0}", t(BUSY_LABEL[block.label] || block.label || ""));
    $("#busy-title").textContent = what;
    $("#busy-sub").textContent = block.op === "selfcheck" ? t("The program reads the controller and, at stage 2, switches functions briefly and back. Do not close the lid.")
      : slow ? t("WMI path: every access to the controller takes about 0.15 s. Please wait.") : t("Please wait.");
    const bk = $("#busy-backup");
    bk.classList.toggle("hidden", !(block.op === "selfcheck" && scBackup));
    if (block.op === "selfcheck" && scBackup) bk.replaceChildren(h("b", {}, "✓ " + t("EC backup saved")), " ",
      t("{0} controller values were copied to {1} before the test writes; they are put back when the check ends.", scBackup.count, scBackup.path));
    const pb = $("#busy-bar");
    pb.classList.toggle("indet", block.progress == null);
    pb.firstElementChild.style.width = block.progress == null ? "" : block.progress + "%";
    ov.classList.remove("hidden");
  } else ov.classList.add("hidden");
  const chip = $("#busy-chip");
  chip.classList.toggle("hidden", !table);
  if (table) chip.textContent = t("Fan curve: writing {0} %", table.progress ?? 0);
  document.body.classList.toggle("table-busy", !!table);
}

// ---------------------------------------------------------------- service restart: wait and reload
let restartShown = false;
function showRestart() {
  if (restartShown) return;
  restartShown = true;
  const t0 = Date.now();
  const sub = h("p", { class: "muted" }), bar = h("div", { class: "pbar indet" }, h("div"));
  const reload = h("button", { class: "btn hidden", onclick: () => location.reload() }, t("Reload the page"));
  const box = h("div", { class: "eula", role: "dialog", "aria-modal": "true", id: "restart-box" },
    h("div", { class: "eula-card narrow" }, h("h2", {}, t("The service is restarting")),
      h("p", {}, t("Please wait about a minute — the window reloads by itself when the service is back.")), bar, sub,
      h("div", { class: "row end" }, reload)));
  document.body.append(box);
  let downSeen = false;
  const tick = async () => {
    const sec = Math.round((Date.now() - t0) / 1000);
    sub.textContent = t("{0} s", sec);
    if (sec > 90) {
      sub.textContent = t("The service has not come back yet. Reload the page (F5) or restart the service from the tray icon.");
      reload.classList.remove("hidden");
    }
    try {
      const r = await fetch("/api/state", { headers: { "X-UWCC-Token": TOKEN }, cache: "no-store" });
      if (r.ok && (downSeen || sec > 20)) { location.reload(); return; }
    } catch (_) { downSeen = true; }
    setTimeout(tick, 2000);
  };
  setTimeout(tick, 3000);
}

// ---------------------------------------------------------------- administrator rights (UAC / sudo)
async function adminApi(path, body) {
  try { return await api(path, body); }
  catch (e) {
    if (e.status !== 403 || !(e.data && e.data.admin_required)) throw e;
    if (!(await requestAdmin())) throw new Error(t("administrator rights were not granted"));
    return await api(path, body);
  }
}
function requestAdmin() {
  return new Promise(async resolve => {
    let done = false;
    const finish = ok => { if (done) return; done = true; box.remove(); resolve(ok); };
    const msg = h("p", {}), cmd = h("pre", { class: "code hidden" }, "sudo uwccctl ec unlock");
    const box = h("div", { class: "eula", role: "dialog", "aria-modal": "true" },
      h("div", { class: "eula-card narrow" }, h("h2", {}, t("Administrator rights needed")),
        h("p", { class: "muted" }, t("Changing how the program reaches the controller, its WMI settings and platform profiles needs administrator rights. They are granted for 10 minutes.")),
        msg, cmd, h("div", { class: "pbar indet" }, h("div")),
        h("div", { class: "row end" }, h("button", { class: "btn ghost", onclick: () => finish(false) }, t("Cancel")))));
    document.body.append(box);
    try {
      const r = await api("admin/request", {});
      if (r.unlocked) return finish(true);
      if (r.tray) msg.textContent = t("Confirm the Windows prompt (UAC) that has opened. If you do not see it, look at the taskbar.");
      else { msg.textContent = t("Run this command in a terminal (or uwccctl ec unlock in an administrator console on Windows):"); cmd.classList.remove("hidden"); }
    } catch (e) { msg.textContent = t("Error: {0}", e.message); }
    for (let i = 0; i < 180 && !done; i++) {
      await new Promise(r => setTimeout(r, 1000));
      try { const st = await api("admin"); if (st.unlocked) { if (S && S.ec_access) S.ec_access.admin = st; renderAdmin(); return finish(true); } } catch (_) {}
    }
    finish(false);
  });
}
let adminTimer = null;
function renderAdmin() {
  const a = ecA(), el = $("#dm-admin");
  if (!el || !a) return;
  const ad = a.admin || {};
  const left = ad.unlocked ? Math.max(0, Math.round(((ad.until || 0) * 1000 - Date.now()) / 1000)) : 0;
  el.className = "admin-bar" + (left > 0 ? " open" : "");
  el.replaceChildren(
    h("span", { class: "lock" }, left > 0 ? "🔓" : "🔒"),
    h("span", {}, left > 0 ? t("Settings unlocked — {0} min {1} s left", Math.floor(left / 60), left % 60)
      : t("Changes need administrator rights")),
    left > 0 ? h("button", { class: "btn ghost", onclick: () => act(() => api("admin/lock", {})) }, t("Lock now"))
      : h("button", { class: "btn ghost", onclick: () => requestAdmin().then(() => refresh().catch(() => {})) }, t("Unlock (administrator)")));
  clearTimeout(adminTimer);
  if (left > 0) adminTimer = setTimeout(() => { if (left <= 1 && a.admin) a.admin.unlocked = false; renderAdmin(); }, 1000);
}

// ---------------------------------------------------------------- monitoring switches
const MON_MODES = [["full", "Full monitoring"], ["off_oem", "Off with the OEM driver"], ["off_wmi", "Off with WMI"],
  ["off_both", "Off with the OEM driver and WMI"], ["off_all", "All monitoring off"]];
const MON_HINT = { full: "Sensors, fans and history are read all the time.",
  off_oem: "Through the OEM driver only the temperatures for the liquid cooler and the alerts are read, every 20 s; no Monitor page and history.",
  off_wmi: "Through WMI only the temperatures for the liquid cooler and the alerts are read, every 20 s — fewer slow accesses to the controller.",
  off_both: "Through either path only the temperatures for the liquid cooler and the alerts are read, every 20 s.",
  off_all: "Nothing is read: no Monitor page, history or overheat alerts; the liquid cooler in the automatic mode runs the fixed “Medium” preset." };
const INTERVALS = [0, 1, 2, 3, 5, 10, 15, 30, 60];
const HIST_SIZES = [256, 512, 1024, 2048, 5120, 10240, 51200];
function fmtSize(b) { return b >= 1048576 ? `${(b / 1048576).toFixed(1)} ${t("MB")}` : `${Math.round(b / 1024)} ${t("KB")}`; }
function renderMonitoring(a) {
  const m = a.monitoring || {}, hi = a.history || {};
  const box = $("#dm-monitor"); if (!box) return;
  if (box.contains(document.activeElement) && document.activeElement.tagName === "INPUT") return;   // typing a folder
  const mode = m.off_all ? "off_all" : m.off_oem && m.off_wmi ? "off_both" : m.off_oem ? "off_oem" : m.off_wmi ? "off_wmi" : "full";
  const sel = (opts, cur, on) => { const e = h("select", { onchange: () => on(e.value) }); for (const [v, l] of opts) { const o = h("option", { value: v }, l); if (String(v) === String(cur)) o.selected = true; e.append(o); } return e; };
  const set = (key, value) => act(() => api("setting", { key, value }));
  const item = (label, ctl, wide) => h("div", { class: "dm-item" + (wide ? " wide" : "") }, h("span", {}, label), ctl);
  const dir = h("input", { type: "text", value: hi.dir || "", spellcheck: "false" });
  box.replaceChildren(
    h("div", { class: "dm-grid" },
      item(t("Monitoring"), sel(MON_MODES.map(([v, l]) => [v, t(l)]), mode, v => set("monitoring", v))),
      item(t("Sampling interval"), sel(INTERVALS.map(v => [v, v ? t("{0} s", v) : t("automatic ({0} s)", hi.interval_auto ?? 2)]),
        hi.interval_setting || 0, v => set("monitor_interval", +v)))),
    h("p", { class: "muted tiny" }, t(MON_HINT[mode])),
    h("h4", {}, t("History")),
    h("div", { class: "dm-grid" },
      item(t("Size on disk"), h("span", {}, `${fmtSize(hi.size || 0)} · ${t("{0} min of 24 h", (hi.points || {}).day || 0)}`)),
      item(t("Maximum size"), sel(HIST_SIZES.map(v => [v, fmtSize(v * 1024)]).concat(HIST_SIZES.includes(hi.max_kb) ? [] : [[hi.max_kb, fmtSize((hi.max_kb || 0) * 1024)]]),
        hi.max_kb, v => set("history_max_kb", +v))),
      item(t("Folder"), h("div", { class: "row" }, dir, h("button", { class: "btn ghost", onclick: () => act(async () => {
        await adminApi("history/config", { dir: dir.value.trim() }); await refresh();
      }, t("Saved")) }, t("Move"))), true)),
    h("p", { class: "muted tiny" }, t("File: {0}. The oldest minutes are dropped when it grows beyond the maximum size. Moving the folder needs administrator rights.", hi.path || "")),
    h("div", { class: "row" }, h("button", { class: "btn ghost", onclick: () => act(async () => {
      if (!confirm(t("Delete the whole sensor history (1 hour and 24 hours)?"))) return;
      await api("history/clear", {}); await refresh(); loadHistory && loadHistory(true);
    }, t("Cleared")) }, t("Clear the history"))));
}
function renderMonOff(level) {
  level = level || (S && S.monitoring) || "full";
  const el = $("#mon-off"); if (!el) return;
  el.classList.toggle("hidden", level === "full");
  $("#page-monitor").classList.toggle("mon-off", level !== "full");
  if (level !== "full") el.replaceChildren(h("b", {}, t("Monitoring is off")), " ",
    t(level === "off" ? "All monitoring is switched off in EC Manager." : "Monitoring is switched off for this EC path in EC Manager: only the temperatures for the liquid cooler and the alerts are read, every 20 s."),
    " ", h("a", { href: "#", onclick: e => { e.preventDefault(); $(`#nav a[data-page="driver"]`)?.click(); } }, t("Open EC Manager")));
}

// ---------------------------------------------------------------- platform profile
const PLAT_STATUS = { verified: "verified", community: "from the community", draft: "draft (own self-check)", unknown: "unknown" };
function renderPlatform(a) {
  const p = a.platform || {}, box = $("#dm-platform-kv"); if (!box) return;
  const dl = rows => { box.innerHTML = ""; for (const [k, v] of rows) box.append(h("dt", {}, k), h("dd", {}, v ?? "—")); };
  const tested = p.tested ? [((p.tested.ec || []).length ? "EC " + p.tested.ec.join(", ") : ""), ((p.tested.bios || []).length ? "BIOS " + p.tested.bios.join(", ") : ""), p.tested.date || ""].filter(Boolean).join(" · ") : "";
  dl([[t("Profile"), p.name], [t("Project"), p.project],
    [t("Status"), h("span", { class: "tag " + (p.status === "verified" ? "good" : p.status === "unknown" ? "bad" : "") }, t(PLAT_STATUS[p.status] || p.status))],
    [t("Source"), p.source === "user" ? (p.modified ? t("your profile (replaces the built-in one)") : t("your profile")) : t("built into the program")],
    [t("Tested"), tested || "—"]]);
  const notes = $("#dm-platform-notes"); notes.innerHTML = "";
  for (const n of ((p.notes || {})[LANG] || (p.notes || {}).en || [])) notes.append(h("li", {}, n));
  $("#dm-plat-reset").classList.toggle("hidden", p.source !== "user");
}
$("#dm-plat-export").addEventListener("click", async () => {
  const r = await api("platform");
  const blob = new Blob([JSON.stringify(r.profile, null, 2)], { type: "application/json" });
  const el = h("a", { href: URL.createObjectURL(blob), download: (r.profile.id || "platform") + ".json" }); document.body.append(el); el.click(); el.remove();
});
$("#dm-plat-import").addEventListener("click", () => $("#dm-plat-file").click());
$("#dm-plat-file").addEventListener("change", async e => {
  const f = e.target.files[0]; e.target.value = "";
  if (!f) return;
  try {
    const prof = JSON.parse(await f.text());
    const r = await adminApi("platform/import", { profile: prof }); await refresh();
    toast(t("Platform profile saved") + (r.restart_needed ? " — " + t("restart the service to apply it") : ""));
  } catch (err) { toast(t("Import failed: {0}", err.message), true); }
});
$("#dm-plat-reset").addEventListener("click", () => act(async () => {
  if (!confirm(t("Remove your platform profile and use the built-in one?"))) return;
  const r = await adminApi("platform/reset", {}); await refresh();
  if (r.restart_needed) toast(t("Restart the service to apply it"));
}, t("Done")));

// ---------------------------------------------------------------- self-check
const SC_MARK = { ok: "✓", warn: "!", fail: "✕", skip: "–", unknown: "?" };
const SC_GROUP = { identity: "Identity", paths: "Access paths", registers: "Registers", firmware: "Firmware", write: "Writes (stage 2)" };
let scLoaded = null;
async function renderSelfcheck(a) {
  const sc = a.selfcheck || {};
  const last = sc.last;
  const s2 = $("#dm-sc-2");
  s2.disabled = !sc.stage1_done || !!sc.running;
  s2.title = sc.stage1_done ? "" : t("Run stage 1 (read only) first");
  $("#dm-sc-state").textContent = sc.running ? t("Running stage {0}…", sc.running)
    : last ? t("Last check: stage {0}, {1}", last.stage, new Date(last.time * 1000).toLocaleString(LANG === "ru" ? "ru-RU" : "en-GB")) : t("Not run yet.");
  const key = last ? last.time : null;
  if (!last || scLoaded === key || sc.running) { if (!last) $("#dm-sc-out").innerHTML = ""; $("#dm-sc-apply").disabled = !last; return; }
  scLoaded = key;
  let r;
  try { r = (await api("selfcheck")).result; } catch (_) { return; }
  const out = $("#dm-sc-out"); out.innerHTML = "";
  if (!r) return;
  if (r.error) out.append(h("p", { class: "red-warn" }, t("Error: {0}", r.error)));
  const groups = {};
  for (const it of r.items || []) (groups[it.group] = groups[it.group] || []).push(it);
  for (const [g, items] of Object.entries(groups)) {
    out.append(h("h4", {}, t(SC_GROUP[g] || g)));
    const tb = h("div", { class: "sc-list" });
    for (const it of items) tb.append(h("div", { class: "sc-row " + it.status }, h("span", { class: "sc-mark" }, SC_MARK[it.status] || "?"),
      h("span", { class: "sc-name" }, t(it.name)), h("span", { class: "sc-detail muted" }, it.detail)));
    out.append(tb);
  }
  if ((r.unknowns || []).length) {
    out.append(h("h4", {}, t("Not clear")));
    out.append(h("ul", { class: "sc-unknown" }, ...r.unknowns.map(u => h("li", {}, u))));
  }
  if (r.features) out.append(h("p", { class: "muted tiny" }, t("Functions for the draft profile:") + " " +
    Object.entries(r.features).map(([k, v]) => `${t((EC_FEATURES[k] || {}).name || k)}: ${t({ on: "available", slow: "available, slow", off: "off" }[v] || v)}`).join(" · ")));
  $("#dm-sc-apply").disabled = !r.draft;
}
async function runSelfcheck(stage) {
  if (stage === 2 && !confirm(t("Stage 2 briefly switches functions of the controller and back (mode, Fan Boost, PL1, cTGP, charge limit, Fn Lock). First every value it writes is copied to a backup file; at the end they are restored and checked. The laptop must be on AC power. Continue?"))) return;
  await act(async () => {
    await (stage === 2 ? adminApi : api)("selfcheck", { stage });
    localBusy = { op: "selfcheck", label: "stage " + stage, blocking: true, progress: 0 };
    renderBusy((S && S.busy) || []);
    for (let i = 0; i < 600; i++) {
      await new Promise(r => setTimeout(r, 1000));
      const st = await api("selfcheck").catch(() => null);
      if (st && !st.running) break;
    }
    localBusy = null; scLoaded = null;
  });
}
$("#dm-sc-1").addEventListener("click", () => runSelfcheck(1));
$("#dm-sc-2").addEventListener("click", () => runSelfcheck(2));
$("#dm-sc-export").addEventListener("click", async () => {
  try {
    const r = await api("selfcheck/export");
    const blob = new Blob([JSON.stringify(r, null, 2)], { type: "application/json" });
    const el = h("a", { href: URL.createObjectURL(blob), download: "uwcc-selfcheck.json" }); document.body.append(el); el.click(); el.remove();
  } catch (e) { toast(t("Error: {0}", e.message), true); }
});
$("#dm-sc-apply").addEventListener("click", () => act(async () => {
  if (!confirm(t("Save the result of the self-check as this laptop's platform profile (status: draft)? It decides which functions are available through WMI."))) return;
  const r = await adminApi("platform/apply-draft", {}); await refresh();
  if (r.restart_needed) toast(t("Restart the service to apply it"));
}, t("Saved")));

// ---------------------------------------------------------------- edition (free / non-free) and the OEM driver package
const DRIVER_REPO = "https://github.com/aspidovss/open-uniwill-cc/tree/main/proprietary/driver";
const CHK_MARK = { ok: "✓", warn: "!", fail: "✕", hard: "✕", skip: "–" };
function renderEdition(a) {
  const box = $("#dm-edition"); if (!box) return;
  const free = a.edition === "free", pkg = a.driver_package, need = a.active !== "oem";
  box.classList.toggle("hidden", !free && !(need && (pkg || a.driver_store)));
  if (box.classList.contains("hidden")) return;
  const kids = [];
  if (free) {
    kids.push(h("div", { class: "row between wrap" }, h("h3", {}, t("Free build")), helpLink("oem-driver")),
      h("p", {}, t("This build does not contain the original OEM driver and is distributed completely freely (open source, MIT licence). Without the driver the program works through the open WMI implementation (beta).")),
      h("p", {}, h("b", {}, t("Recommended:")), " ", t("put the OEM driver of the manufacturer's Control Center (UWACPIDriver.inf, UWACPIDriver.sys, UWACPIDriver.cat) into this folder and install it with the button below:")),
      h("pre", { class: "code" }, a.driver_dir || "C:\\ProgramData\\UWCC\\driver"));
  } else {
    kids.push(h("div", { class: "row between wrap" }, h("h3", {}, t("OEM driver package")), helpLink("oem-driver")));
  }
  // where to get it
  kids.push(h("div", { class: "row wrap" },
    a.driver_store ? h("button", { class: "btn" + (pkg ? " ghost" : ""), onclick: () => act(async () => {
      const r = await adminApi("ec-access/fetch-driver", {}); toast(t("Copied: {0}", r.files.join(", "))); await refresh();
    }, t("Copied")) }, t("Get the driver from this system")) : null,
    h("a", { class: "btn ghost", href: DRIVER_REPO, target: "_blank", rel: "noopener" }, t("Driver in the repository")),
    h("button", { class: "btn ghost", onclick: () => openHelp("oem-driver") }, t("How to get the driver"))));
  if (!a.driver_store && !pkg) kids.push(h("p", { class: "muted tiny" }, t("The driver is not in the Windows driver store of this laptop (the manufacturer's Control Center was never installed) — take it from the repository or from the manufacturer's installer.")));
  // the package and its check
  if (!pkg) kids.push(h("p", {}, t("No driver package in {0} yet.", a.driver_dir || "")));
  else {
    const c = pkg.check || {};
    kids.push(h("p", {}, t("Driver package: {0}", pkg.dir)));
    if (c.checks) kids.push(h("div", { class: "sc-list" }, ...c.checks.map(x => h("div", { class: "sc-row " + (x.status === "hard" ? "fail" : x.status) },
      h("span", { class: "sc-mark" }, CHK_MARK[x.status] || "?"), h("span", { class: "sc-name" }, t({ files: "Files", inf: "INF", signature: "Signature", hash: "Known version" }[x.id] || x.id)),
      h("span", { class: "sc-detail muted" }, x.detail)))));
    const lvl = c.level;
    if (lvl === "hard") kids.push(h("p", { class: "red-warn" }, t("This package cannot be used: files are missing or it is a driver for another device.")));
    if (need && lvl !== "hard") {
      const risky = lvl === "warn" || lvl === "fail";
      const chk = h("input", { type: "checkbox", id: "drv-risk" });
      const btn = h("button", { class: "btn", disabled: risky ? true : null, onclick: () => act(async () => {
        if (!confirm(t("Install the OEM driver from {0}? The service restarts and uses it.", pkg.dir))) return;
        const r = await adminApi("ec-access/install-driver", { accept_risks: risky && chk.checked });
        if (r.risk_required) { toast(t("The driver check found problems — confirm that you understand the risk"), true); return; }
        if (r.restarting) showRestart(); else await refresh();
      }, t("Installed")) }, t("Install the OEM driver"));
      chk.addEventListener("change", () => { btn.disabled = !chk.checked; });
      if (risky) kids.push(h("p", { class: "warn-text" }, lvl === "warn" ? t("This driver version is not in the list of known versions (the signature is valid).")
        : t("The signature of the driver is not valid or could not be checked.")),
        h("label", { class: "eula-check" }, chk, h("span", {}, t("I still want to use this driver and understand the risk"))));
      kids.push(h("div", { class: "row" }, btn));
    }
  }
  kids.push(h("p", { class: "muted tiny" }, t("By installing the OEM driver you confirm that you have the right to use this file (UWACPIDriver.sys, part of the laptop manufacturer's Control Center).")));
  box.replaceChildren(...kids);
}

// ---------------------------------------------------------------- built-in help (docs/*.md served under /help/)
const REPO_BLOB = "https://github.com/aspidovss/open-uniwill-cc/blob/main/";
const HELP_PAGES = [
  { group: "EC access" },
  { id: "ec-manager", name: "EC Manager, platform profiles, self-check", en: "EC/Platforms.md", ru: "EC/Platforms.ru.md" },
  { id: "oem-driver", name: "Getting the OEM driver", en: "EC/OEM-driver.md", ru: "EC/OEM-driver.ru.md" },
  { id: "wmi-vs-driver", name: "OEM driver vs WMI", en: "EC/WMI-vs-Driver.md", ru: "EC/WMI-vs-Driver.ru.md" },
  { id: "wmi-config", name: "WMI settings (ec_wmi.json)", en: "EC/WMI-config.md", ru: "EC/WMI-config.ru.md" },
  { id: "registers", name: "EC registers", en: "EC/Registers.md", ru: "EC/Registers.ru.md" },
  { id: "ec-tool", name: "EC test tool (ec_tool.py)", en: "EC/README.md", ru: "EC/README.ru.md" },
  { group: "Program" },
  { id: "features", name: "Features and how they work", en: "FEATURES.md", ru: "FEATURES.md" },
  { id: "lighting", name: "BetterRGB keyboard effects", en: "LIGHTING.md", ru: "LIGHTING.ru.md" },
  { id: "clevo", name: "Control Center 3.0 / Clevo (experimental)", en: "CLEVO.md", ru: "CLEVO.ru.md" },
  { id: "cli", name: "Command line (uwccctl)", en: "CLI.md", ru: "CLI.ru.md" },
];
var helpCur = null;                     // var: setLang() may run before this line
function helpFile(p) { return p[LANG === "ru" ? "ru" : "en"] || p.en; }
function renderHelpToc() {
  const toc = $("#help-toc"); if (!toc) return;
  toc.replaceChildren(...HELP_PAGES.map(p => p.group ? h("small", {}, t(p.group))
    : h("a", { class: helpCur && helpCur.id === p.id ? "on" : "", onclick: () => openHelp(p.id) }, t(p.name))));
}
function resolveDoc(base, href) {                       // "EC/Platforms.md" + "../CLI.md#x" -> "CLI.md#x"
  const [path, hash] = href.split("#");
  const parts = base.split("/").slice(0, -1);
  for (const seg of path.split("/")) { if (seg === "..") parts.pop(); else if (seg && seg !== ".") parts.push(seg); }
  return { path: parts.join("/"), hash: hash || "" };
}
async function openHelp(id, anchor) {
  const p = HELP_PAGES.find(x => x.id === id) || { id, file: id };
  const file = p.file || helpFile(p);
  helpCur = { ...p, file };
  $(`#nav a[data-page="help"]`)?.click();
  renderHelpToc();
  const body = $("#help-body");
  body.textContent = t("Loading…");
  try {
    const r = await fetch("help/" + file, { cache: "no-cache" });
    if (!r.ok) throw new Error(r.status === 404 ? t("this page is not part of this installation") : r.statusText);
    body.innerHTML = MD.render(await r.text());
  } catch (e) {
    body.replaceChildren(h("p", {}, t("The page could not be opened: {0}", e.message)),
      h("p", {}, h("a", { href: REPO_BLOB + "docs/" + file, target: "_blank", rel: "noopener" }, t("Open it on GitHub"))));
    return;
  }
  body.querySelectorAll("a[data-md-link]").forEach(a => {
    const href = a.getAttribute("href");
    if (/^https?:/i.test(href)) { a.target = "_blank"; a.rel = "noopener"; return; }
    if (href.startsWith("#")) { a.addEventListener("click", e => { e.preventDefault(); body.querySelector("#md-" + CSS.escape(decodeURIComponent(href.slice(1))))?.scrollIntoView({ behavior: "smooth" }); }); return; }
    const { path, hash } = resolveDoc(file, href);
    if (path.endsWith(".md") && !path.startsWith("..")) {
      const known = HELP_PAGES.find(x => x.en === path || x.ru === path);
      a.href = "#";
      a.addEventListener("click", e => { e.preventDefault(); known ? openHelp(known.id, hash) : openHelp(path, hash); });
    } else {                                              // source files, images, folders: GitHub
      a.href = REPO_BLOB + ("docs/" + path).replace(/^docs\/\.\.\//, "");
      a.target = "_blank"; a.rel = "noopener";
    }
  });
  const target = anchor ? body.querySelector("#md-" + CSS.escape(anchor)) : null;
  if (target) target.scrollIntoView({ block: "start" });
  else { const m = body.closest("main"); if (m) m.scrollTop = 0; window.scrollTo(0, 0); }
}
function helpLink(id, anchor) {                       // anchor: "x" or {en: "x", ru: "y"}
  return h("button", { class: "help-q", title: t("Help"), "aria-label": t("Help"),
    onclick: e => { e.stopPropagation(); openHelp(id, anchor && typeof anchor === "object" ? anchor[LANG === "ru" ? "ru" : "en"] : anchor); } }, "?");
}
$(`#nav a[data-page="help"]`)?.addEventListener("click", () => { if (!helpCur) openHelp("ec-manager"); else renderHelpToc(); });
(function addHelpLinks() {                               // "?" next to the titles of the EC Manager cards
  const pairs = [["#dm-platform h3", "ec-manager", { en: "platform-profile", ru: "профиль-платформы" }],
    ["#dm-selfcheck h3", "ec-manager", { en: "self-check", ru: "самопроверка" }],
    ["#dm-wmi h3", "wmi-config"],
    ["#fx-card h3", "lighting", { en: "effects", ru: "эффекты" }],
    ["#fx-engine-card h3", "lighting", { en: "engine-settings", ru: "настройки-движка" }]];
  const firstCard = $$("#page-driver .card h3").find(x => (x.dataset.en || x.textContent) === "EC access path");
  const mon = $$("#page-driver .card h3").find(x => (x.dataset.en || x.textContent) === "Monitoring");
  const els = pairs.map(([sel, id, a]) => [$(sel), id, a]).concat([[firstCard, "wmi-vs-driver"], [mon, "ec-manager", { en: "monitoring", ru: "мониторинг" }]]);
  for (const [el, id, a] of els) {
    if (!el || el.parentElement.classList.contains("h-help")) continue;
    const wrap = h("span", { class: "h-help" });
    el.before(wrap); wrap.append(el, helpLink(id, a));
  }
})();

// ---------------------------------------------------------------- EC Manager: cards fold by a click on their title
function setupCollapsible() {
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem("uwcc-folded") || "{}"); } catch (_) {}
  // EC Manager cards, the profile settings (Mode selection) and the diagnostic report (Information)
  for (const card of $$("#page-driver > .card, #profile-editor, #report-card")) {
    card.classList.add("foldable");
    const h3 = card.querySelector("h3");
    if (!h3) continue;
    let head = h3;                                   // the direct child of the card that holds the title
    while (head.parentElement && head.parentElement !== card) head = head.parentElement;
    head.classList.add("card-head");
    const key = card.id || h3.dataset.en || h3.textContent;
    if (!h3.dataset.fold) {
      h3.dataset.fold = "1";
      h3.classList.add("fold-title");
      h3.setAttribute("role", "button");
      h3.tabIndex = 0;
      const toggle = () => {
        const on = !card.classList.contains("folded");
        card.classList.toggle("folded", on);
        try { const m = JSON.parse(localStorage.getItem("uwcc-folded") || "{}"); m[key] = on; localStorage.setItem("uwcc-folded", JSON.stringify(m)); } catch (_) {}
      };
      h3.addEventListener("click", toggle);
      h3.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
      card.classList.toggle("folded", !!saved[key]);
    }
    h3.setAttribute("aria-expanded", String(!card.classList.contains("folded")));
  }
}
