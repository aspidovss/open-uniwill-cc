"use strict";
// Colour-stop editor for BetterRGB temperature lighting. No sensor polling here.
const temperatureSelection = { cpu: 0, gpu: 0 };

function temperatureColorAt(points, temp) {
  if (temp <= points[0].temp) return [...points[0].color];
  const linear = v => v / 255 <= 0.04045 ? v / 255 / 12.92 : ((v / 255 + 0.055) / 1.055) ** 2.4;
  const srgb = v => Math.round(255 * (v <= 0.0031308 ? v * 12.92 : 1.055 * v ** (1 / 2.4) - 0.055));
  for (let i = 1; i < points.length; i++) {
    if (temp > points[i].temp) continue;
    const a = points[i - 1], b = points[i], mix = (temp - a.temp) / (b.temp - a.temp);
    return a.color.map((v, j) => srgb(linear(v) * (1 - mix) + linear(b.color[j]) * mix));
  }
  return [...points[points.length - 1].color];
}

function temperatureInsertPoint(points, temp) {
  if (points.length >= 15 || !Number.isInteger(temp) || temp < 0 || temp > 120 || points.some(p => p.temp === temp)) return null;
  return [...points.map(p => ({ temp: p.temp, color: [...p.color] })), { temp, color: temperatureColorAt(points, temp) }]
    .sort((a, b) => a.temp - b.temp);
}

function temperatureAddPosition(points) {
  const bounds = [0, ...points.map(p => p.temp), 120];
  let best = null, gap = -1;
  for (let i = 1; i < bounds.length; i++) {
    const temp = Math.floor((bounds[i - 1] + bounds[i]) / 2), span = bounds[i] - bounds[i - 1];
    if (span > gap && !points.some(p => p.temp === temp)) { best = temp; gap = span; }
  }
  return best;
}

function drawTemperatureParams(k, p, box, send) {
  const side = h("select", { "data-temp-focus": "left" }, ...["cpu", "gpu"].map(sensor => {
    const option = h("option", { value: sensor }, t(FX_CHOICE[sensor]));
    option.selected = p.left === sensor;
    return option;
  }));
  side.addEventListener("change", () => { p.left = side.value; send(); });
  const smoothing = h("input", { type: "range", min: 0, max: 5000, step: 100, value: p.smoothing_ms, "data-temp-focus": "smoothing" });
  const output = h("output", {}, `${p.smoothing_ms} ${t("ms")}`);
  smoothing.addEventListener("input", () => { output.textContent = `${smoothing.value} ${t("ms")}`; });
  smoothing.addEventListener("change", () => { p.smoothing_ms = +smoothing.value; send(); });
  box.append(h("div", { class: "temp-general" },
    h("label", {}, h("span", {}, t("Left half")), side),
    h("label", { class: "temp-smoothing" }, h("span", {}, t("Colour smoothing")), smoothing, output)));
  const curves = h("div", { class: "temp-curves" });
  box.append(curves);
  for (const sensor of ["cpu", "gpu"]) {
    let points = p[sensor + "_points"];
    let selected = Math.min(temperatureSelection[sensor], points.length - 1), dragging = null;
    const card = h("section", { class: "temp-sensor", "aria-label": sensor.toUpperCase() });
    const count = h("span", { class: "muted tiny" });
    card.append(h("div", { class: "temp-sensor-head" }, h("h4", {}, sensor.toUpperCase()),
      h("span", { id: "fx-temperature-" + sensor, class: "temp-reading", "aria-live": "polite" }), count));
    const svg = svgEl(`<svg class="temp-curve" viewBox="0 0 400 150" role="group"></svg>`);
    svg.setAttribute("aria-label", t("{0} temperature colour curve", sensor.toUpperCase()));
    card.append(svg);
    const editor = h("div", { class: "temp-point-editor" });
    const temperature = h("input", { type: "number", step: 1, "data-temp-focus": sensor + "-temperature" });
    const colour = h("input", { type: "color", "data-temp-focus": sensor + "-colour" });
    const remove = h("button", { class: "btn ghost sm", type: "button", "data-temp-focus": sensor + "-remove" }, t("Remove point"));
    editor.append(h("label", {}, h("span", {}, t("Temperature, °C")), temperature),
      h("label", {}, h("span", {}, t("Colour")), colour), remove);
    card.append(editor);
    const add = h("button", { class: "btn ghost sm", type: "button", "data-temp-focus": sensor + "-add" }, t("Add point"));
    const reset = h("button", { class: "btn ghost sm", type: "button", "data-temp-focus": sensor + "-reset" }, t("Reset curve"));
    card.append(h("div", { class: "temp-actions" }, add, reset),
      h("p", { class: "muted tiny temp-hint" }, t("Drag a point to change its temperature. Click the colour band to add a point (up to 15).")));
    curves.append(card);
    const choose = i => { selected = temperatureSelection[sensor] = i; };
    const limits = () => [selected ? points[selected - 1].temp + 1 : 0,
      selected + 1 < points.length ? points[selected + 1].temp - 1 : 120];
    const paint = () => {
      count.textContent = t("{0} / 15 points", points.length);
      const gradient = points.map(pt => `<stop offset="${pt.temp / 120}" stop-color="${rgb2hex(pt.color)}"/>`).join("");
      const ticks = [0, 20, 40, 60, 80, 100, 120].map(temp => {
        const x = 20 + temp * 3;
        return `<path d="M${x} 116v5"/><text x="${x}" y="138" text-anchor="middle">${temp}°</text>`;
      }).join("");
      const dots = points.map((pt, i) => `<circle data-point="${i}" cx="${20 + pt.temp * 3}" cy="104" r="${i === selected ? 8 : 6}"
        fill="${rgb2hex(pt.color)}" class="${i === selected ? "selected" : ""}" tabindex="0" role="button" data-temp-focus="${sensor}-point-${i}"
        aria-label="${t("Point {0}: {1} °C", i + 1, pt.temp)}"/>`).join("");
      svg.innerHTML = `<defs><linearGradient id="temp-gradient-${sensor}" color-interpolation="linearRGB">${gradient}</linearGradient></defs>
        <rect x="20" y="24" width="360" height="80" rx="8" fill="url(#temp-gradient-${sensor})"/>
        <g class="temp-ticks">${ticks}</g><line class="temp-now" id="fx-temperature-line-${sensor}" y1="14" y2="114"/>${dots}`;
      const [min, max] = limits();
      temperature.min = min; temperature.max = max; temperature.value = points[selected].temp;
      colour.value = rgb2hex(points[selected].color);
      remove.disabled = points.length <= 2;
      add.disabled = points.length >= 15;
      renderFxTemperature();
    };
    const insert = temp => {
      if (temp === null) return;
      const next = temperatureInsertPoint(points, temp);
      if (!next) return;
      points = p[sensor + "_points"] = next;
      choose(points.findIndex(pt => pt.temp === temp));
      paint(); send();
    };
    const position = event => {
      const pt = svg.createSVGPoint(); pt.x = event.clientX; pt.y = event.clientY;
      return pt.matrixTransform(svg.getScreenCTM().inverse());
    };
    svg.addEventListener("pointerdown", event => {
      if (event.button !== 0) return;
      const dot = event.target.closest("[data-point]");
      if (!dot) {
        const pos = position(event);
        if (pos.x >= 20 && pos.x <= 380 && pos.y >= 24 && pos.y <= 104) insert(Math.round((pos.x - 20) / 3));
        return;
      }
      event.preventDefault();
      choose(+dot.dataset.point);
      dragging = { id: event.pointerId, original: points[selected].temp };
      svg.setPointerCapture(event.pointerId);
      paint();
    });
    svg.addEventListener("pointermove", event => {
      if (!dragging || event.pointerId !== dragging.id) return;
      const [min, max] = limits();
      points[selected].temp = Math.max(min, Math.min(max, Math.round((position(event).x - 20) / 3)));
      paint();
    });
    svg.addEventListener("pointerup", event => {
      if (!dragging || event.pointerId !== dragging.id) return;
      const changed = points[selected].temp !== dragging.original;
      dragging = null; svg.releasePointerCapture(event.pointerId);
      if (changed) send();
    });
    svg.addEventListener("pointercancel", () => {
      if (dragging) { points[selected].temp = dragging.original; dragging = null; paint(); }
    });
    svg.addEventListener("keydown", event => {
      const dot = event.target.closest("[data-point]");
      if (dot && ["Enter", " "].includes(event.key)) {
        event.preventDefault(); choose(+dot.dataset.point); paint(); temperature.focus();
      }
    });
    temperature.addEventListener("change", () => {
      const [min, max] = limits();
      const value = temperature.value === "" ? NaN : +temperature.value;
      if (!Number.isInteger(value) || value < min || value > max) { paint(); return; }
      points[selected].temp = value; paint(); send();
    });
    colour.addEventListener("change", () => { points[selected].color = hex2rgb(colour.value); paint(); send(); });
    remove.addEventListener("click", () => {
      if (points.length <= 2) return;
      points.splice(selected, 1); choose(Math.min(selected, points.length - 1)); paint(); send();
    });
    add.addEventListener("click", () => insert(temperatureAddPosition(points)));
    reset.addEventListener("click", () => {
      points = p[sensor + "_points"] = fxDefaults(116)[sensor + "_points"];
      choose(0); paint(); send();
    });
    paint();
  }
  box.append(h("p", { class: "muted tiny temp-smoothing-note" }, t("Smoothing: 0 = immediate. Higher values make colour changes slower.")));
}

function renderFxTemperature() {
  const temps = S?.keyboard?.fx?.temperatures || {};
  for (const sensor of ["cpu", "gpu"]) {
    const el = $("#fx-temperature-" + sensor), line = $("#fx-temperature-line-" + sensor);
    const valid = Number.isFinite(temps[sensor]);
    if (el) el.textContent = valid ? `${temps[sensor]} °C` : t("No temperature data");
    if (line) {
      line.style.display = valid ? "" : "none";
      const x = 20 + Math.max(0, Math.min(120, temps[sensor] || 0)) * 3;
      line.setAttribute("x1", x); line.setAttribute("x2", x);
    }
  }
}
