"use strict";
/* Small Markdown renderer for the built-in help (docs/*.md): headings with GitHub-style anchors, paragraphs, lists
   (nested by indentation), fenced code, tables, block quotes (GitHub notes), rules, inline code / bold / italic /
   links. Everything is escaped first — raw HTML in the documents is shown as text, never executed. */
const MD = (() => {
  const esc = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const slug = s => s.trim().toLowerCase().replace(/<[^>]+>/g, "").replace(/[`*_~]/g, "")
    .replace(/[^\p{L}\p{N}\s-]/gu, "").replace(/\s/g, "-");

  function inline(text) {
    const codes = [];
    let s = text.replace(/`([^`]+)`/g, (_, c) => { codes.push(c); return `\u0000${codes.length - 1}\u0000`; });
    s = esc(s);
    s = s.replace(/!\[([^\]]*)\]\(([^)\s]+)[^)]*\)/g, (_, alt) => alt ? `<em class="md-img">[${alt}]</em>` : "");
    s = s.replace(/\[([^\]]+)\]\(([^)\s]+)(?:\s+&quot;[^)]*&quot;)?\)/g,
      (_, label, href) => `<a href="${href}" data-md-link="1">${label}</a>`);
    s = s.replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, (_, pre, url) => `${pre}<a href="${url}" data-md-link="1">${url}</a>`);
    s = s.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/__([^_]+)__/g, "<b>$1</b>");
    s = s.replace(/(^|[^\w*])\*([^*\s][^*]*?)\*(?!\w)/g, "$1<i>$2</i>").replace(/(^|[^\w])_([^_\s][^_]*?)_(?!\w)/g, "$1<i>$2</i>");
    s = s.replace(/&lt;br\s*\/?&gt;/g, "<br>");
    return s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${esc(codes[+i])}</code>`);
  }

  // a row split into cells; "|" inside `code` or escaped as \| stays in the cell
  function cells(r) {
    const out = [];
    let cur = "", code = false;
    const t = r.trim().replace(/^\|/, "").replace(/(?<!\\)\|$/, "");
    for (let k = 0; k < t.length; k++) {
      const ch = t[k];
      if (ch === "\\" && t[k + 1] === "|") { cur += "|"; k++; continue; }
      if (ch === "`") code = !code;
      if (ch === "|" && !code) { out.push(cur.trim()); cur = ""; continue; }
      cur += ch;
    }
    out.push(cur.trim());
    return out;
  }

  function table(rows) {
    const head = cells(rows[0]);
    const align = cells(rows[1]).map(c => /^:-+:$/.test(c) ? "center" : /^-+:$/.test(c) ? "right" : /^:-+$/.test(c) ? "left" : "");
    const st = k => align[k] ? ` style="text-align:${align[k]}"` : "";
    const body = rows.slice(2).map(cells);
    return `<div class="md-table"><table><thead><tr>${head.map((c, k) => `<th${st(k)}>${inline(c)}</th>`).join("")}</tr></thead><tbody>` +
      body.map(r => `<tr>${r.map((c, k) => `<td${st(k)}>${inline(c)}</td>`).join("")}</tr>`).join("") + "</tbody></table></div>";
  }

  function list(lines) {
    // lines: [{indent, ordered, text}] — build nested lists
    let html = "", stack = [];
    for (const l of lines) {
      while (stack.length && l.indent < stack[stack.length - 1].indent) html += `</li></${stack.pop().tag}>`;
      const top = stack[stack.length - 1];
      if (!top || l.indent > top.indent) {
        const tag = l.ordered ? "ol" : "ul";
        stack.push({ indent: l.indent, tag });
        html += `<${tag}><li>`;
      } else html += "</li><li>";
      html += inline(l.text);
    }
    while (stack.length) html += `</li></${stack.pop().tag}>`;
    return html;
  }

  function render(src) {
    const lines = src.replace(/\r/g, "").split("\n");
    const out = [];
    let i = 0;
    const isTableSep = s => /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$/.test(s);    // GitHub: one dash is enough (|:-:|)
    while (i < lines.length) {
      const line = lines[i];
      let m;
      if (/^\s*$/.test(line)) { i++; continue; }
      if ((m = line.match(/^(\s*)(```|~~~)\s*([\w-]*)/))) {
        const fence = m[2], ind = m[1].length, buf = [];
        i++;
        while (i < lines.length && !lines[i].trim().startsWith(fence)) { buf.push(lines[i].slice(Math.min(ind, lines[i].search(/\S|$/)))); i++; }
        i++;
        out.push(`<pre class="code"><code>${esc(buf.join("\n"))}</code></pre>`);
        continue;
      }
      if ((m = line.match(/^(#{1,6})\s+(.*?)\s*#*\s*$/))) {
        const n = m[1].length;
        // "md-" prefix: a heading such as "Effects" must not get the id of an element of the window (#effects)
        out.push(`<h${n} id="md-${esc(slug(m[2]))}">${inline(m[2])}</h${n}>`);
        i++; continue;
      }
      if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { out.push("<hr>"); i++; continue; }
      if (/^\s*</.test(line) && /^\s*<\/?(p|div|img|h\d|a|br|details|summary)\b/i.test(line)) { i++; continue; }   // raw HTML of READMEs
      if (line.includes("|") && i + 1 < lines.length && isTableSep(lines[i + 1])) {
        const rows = [];
        while (i < lines.length && lines[i].includes("|") && lines[i].trim()) rows.push(lines[i++]);
        out.push(table(rows));
        continue;
      }
      if (/^\s*>/.test(line)) {
        const buf = [];
        while (i < lines.length && /^\s*>/.test(lines[i])) buf.push(lines[i++].replace(/^\s*>\s?/, ""));
        let cls = "md-quote";
        if (/^\[!(\w+)\]/.test(buf[0] || "")) { cls += " md-" + buf[0].match(/^\[!(\w+)\]/)[1].toLowerCase(); buf[0] = buf[0].replace(/^\[!\w+\]\s*/, ""); }
        out.push(`<blockquote class="${cls}">${render(buf.join("\n"))}</blockquote>`);
        continue;
      }
      if (/^\s*([-*+]|\d+[.)])\s+/.test(line)) {
        const items = [];
        while (i < lines.length) {
          const l = lines[i];
          const mm = l.match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/);
          if (mm) { items.push({ indent: mm[1].length, ordered: /\d/.test(mm[2]), text: mm[3] }); i++; continue; }
          if (/^\s*$/.test(l)) {                    // blank line: the list goes on only if an item follows
            const nxt = lines[i + 1] || "";
            if (/^\s*([-*+]|\d+[.)])\s+/.test(nxt)) { i++; continue; }
            break;
          }
          if (/^\s+\S/.test(l) && items.length && !/^\s*(```|~~~)/.test(l)) { items[items.length - 1].text += " " + l.trim(); i++; continue; }
          break;
        }
        out.push(list(items));
        continue;
      }
      const buf = [line];
      i++;
      while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|\s*```|\s*~~~|\s*>|\s*([-*+]|\d+[.)])\s)/.test(lines[i])
             && !(lines[i].includes("|") && i + 1 < lines.length && isTableSep(lines[i + 1]))) buf.push(lines[i++]);
      out.push(`<p>${inline(buf.join(" "))}</p>`);
    }
    return out.join("\n");
  }
  return { render, slug };
})();
