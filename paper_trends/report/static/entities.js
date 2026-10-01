// Detail panel: phrases, institutions and topics open a drawer whose contents are clickable
// too. Data is window.ENTITIES (built by report/entities.py); no libraries needed.
(function () {
  const E = window.ENTITIES;
  if (!E) return;
  const YEARS = E.years, RED = "#E3120B", BLUE = "#1F4E79", INK = "#1B1B1B", GREY = "#B8B5AE";
  const pct = (x, d = 1) => (x * 100).toFixed(d) + "%";
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // ---- markup
  document.body.insertAdjacentHTML("beforeend",
    '<div class="ent-scrim" id="ent-scrim"></div>' +
    '<aside class="ent-drawer" id="ent-drawer" aria-hidden="true"><div class="bar"><button type="button" id="ent-back">← back</button>' +
    '<button type="button" id="ent-close">close ✕</button></div><div class="crumbs" id="ent-crumbs"></div><div id="ent-body"></div></aside>');
  const drawer = document.getElementById("ent-drawer"), scrim = document.getElementById("ent-scrim"), body = document.getElementById("ent-body"), crumbs = document.getElementById("ent-crumbs");
  let stack = [];
  const label = (e) => e.t === "term" ? E.terms[e.id].term : e.t === "inst" ? E.insts[e.id].name : E.topics[e.id].label;

  // ---- tiny line chart (no library): series = [{y, s|n}]
  function lineSvg(series, key, color, fmt) {
    const w = 440, h = 120, m = { t: 14, r: 56, b: 20, l: 6 };
    const xs = (y) => m.l + (y - YEARS[0]) / (YEARS[YEARS.length - 1] - YEARS[0] || 1) * (w - m.l - m.r);
    const max = Math.max(...series.map((d) => d[key])) * 1.15 || 1;
    const ys = (v) => h - m.b - (v / max) * (h - m.t - m.b);
    const pts = series.map((d) => [xs(d.y), ys(d[key])]);
    const path = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
    const last = series[series.length - 1];
    return `<svg viewBox="0 0 ${w} ${h}" width="100%" class="ent-line">` +
      `<line x1="${m.l}" x2="${w - m.r}" y1="${ys(0)}" y2="${ys(0)}" stroke="#E6E3DC"/>` +
      `<path d="${path}" fill="none" stroke="${color}" stroke-width="2.2" stroke-linejoin="round"/>` +
      pts.map((p, i) => `<circle cx="${p[0]}" cy="${p[1]}" r="2.6" fill="${color}"><title>${series[i].y}: ${fmt(series[i][key])}</title></circle>`).join("") +
      `<text x="${xs(last.y) + 8}" y="${ys(last[key]) + 4}" fill="${color}" font-size="12.5" font-weight="600">${fmt(last[key])}</text>` +
      `<text x="${m.l}" y="${h - 4}" fill="#5C5C5C" font-size="11.5">${YEARS[0]}</text><text x="${xs(YEARS[YEARS.length - 1])}" y="${h - 4}" fill="#5C5C5C" font-size="11.5" text-anchor="end">${YEARS[YEARS.length - 1]}</text></svg>`;
  }
  const bars = (rows, max, color = GREY) => rows.map(([html, n, right]) =>
    `<div class="ent-row"><span>${html}</span><span><span class="ent-bar" style="width:${Math.max(3, (n / (max || 1)) * 100)}%;background:${color}"></span></span><span class="n">${right ?? n}</span></div>`).join("");
  const termChip = (id, extra = "") => `<span class="ent-chip" data-ent="term" data-id="${id}">${esc(E.terms[id].term)}${extra ? `<small>${extra}</small>` : ""}</span>`;
  const instLink = (id) => `<span class="ent" data-ent="inst" data-id="${id}">${esc(E.insts[id].name)}</span>`;
  const topicLink = (id) => `<span class="ent" data-ent="topic" data-id="${id}"><span class="ent-dot" style="background:${E.topics[id].color}"></span>${esc(E.topics[id].label)}</span>`;
  const blk = (tag, html) => `<div class="ent-blk"><span class="ent-tag">${tag}</span>${html}</div>`;
  const paper = (i) => { const p = E.papers[i]; const link = p.d ? `<a href="https://doi.org/${esc(p.d)}" target="_blank" rel="noopener">${esc(p.t)}</a>` : esc(p.t);
    return `<div class="ent-paper">${link}<small>${p.y} · cited ${p.c}${p.tp != null ? " · " + esc(E.topics[p.tp].label) : ""}</small></div>`; };
  const trend = (e, l, d) => `${pct(e)} → <b style="color:${d >= 0 ? RED : BLUE}">${pct(l)}</b>`;

  function renderTerm(id) {
    const t = E.terms[id];
    return `<div class="ent-kicker">Phrase</div><h2>${esc(t.term)}</h2><p class="ent-meta">${t.total} papers about it · first seen ${t.first} · ${trend(t.early, t.late, t.delta)} of papers</p>`
      + lineSvg(t.series, "s", t.delta >= 0 ? RED : BLUE, pct)
      + blk("Who writes about it", t.insts.length ? bars(t.insts.map(([i, n]) => [instLink(i), n]), t.insts[0][1]) : '<span class="ent-meta">No institution data.</span>')
      + blk("Topics it belongs to", t.topics.length ? bars(t.topics.map(([k, s]) => [topicLink(k), s, pct(s, 0)]), 1) : '<span class="ent-meta">—</span>')
      + blk("Often appears together with", t.co.length ? t.co.map(([o, lift, n]) => termChip(o, `${n} papers · ${lift}×`)).join("") : '<span class="ent-meta">No strong co-occurrence.</span>')
      + blk("Most cited papers", t.papers.map(paper).join(""));
  }
  function renderInst(id) {
    const i = E.insts[id];
    return `<div class="ent-kicker">Institution</div><h2>${esc(i.name)}</h2><p class="ent-meta">${i.total} papers · share ${trend(i.early, i.late, i.delta)}</p>`
      + lineSvg(i.series, "n", INK, (v) => v)
      + blk("Signature phrases (over-represented here)", i.terms.length ? i.terms.map(([t, lift, n]) => termChip(t, `${n} papers · ${lift}×`)).join("") : '<span class="ent-meta">Too few papers for a clear signature.</span>')
      + blk("Topic mix", i.topics.length ? bars(i.topics.map(([k, s]) => [topicLink(k), s, pct(s, 0)]), i.topics[0][1]) : '<span class="ent-meta">—</span>')
      + blk("Publishes most often with", i.collab.length ? bars(i.collab.map(([j, n]) => [instLink(j), n]), i.collab[0][1]) : '<span class="ent-meta">No frequent partner among the leading institutions.</span>')
      + blk("Most cited papers", i.papers.map(paper).join(""));
  }
  function renderTopic(id) {
    const t = E.topics[id];
    return `<div class="ent-kicker">Topic</div><h2><span class="ent-dot big" style="background:${t.color}"></span>${esc(t.label)}</h2><p class="ent-meta">${t.total} papers · ${trend(t.early, t.late, t.delta)} of papers</p>`
      + lineSvg(t.series, "s", t.color, pct)
      + blk("Key phrases", t.key_terms.length ? t.key_terms.map((k) => termChip(k)).join("") : `<span class="ent-meta">${t.terms.map(esc).join(", ")}</span>`)
      + blk("Main institutions", t.insts.length ? bars(t.insts.map(([i, n]) => [instLink(i), n]), t.insts[0][1]) : '<span class="ent-meta">—</span>')
      + blk("Most cited papers", t.papers.map(paper).join(""));
  }
  // Inside a content-sized Streamlit iframe "fixed" means the top of a very tall frame, so
  // the panel is placed next to the click instead (body.embedded is set by the template).
  const embedded = document.body.classList.contains("embedded");
  let lastY = 0;
  document.addEventListener("click", (ev) => { lastY = ev.pageY; }, true);
  function place() {
    if (!embedded) return;
    const h = Math.min(760, Math.max(420, Math.round(document.documentElement.clientWidth * 0.6)));
    const top = Math.max(0, Math.min(lastY - 80, document.documentElement.scrollHeight - h - 10));
    drawer.style.top = top + "px"; drawer.style.height = h + "px";
  }
  function open(t, id, push = true) {
    if (id == null || id < 0) return;
    if (push) { stack.push({ t, id }); place(); }
    drawer.classList.add("open"); scrim.classList.add("open"); drawer.setAttribute("aria-hidden", "false");
    crumbs.innerHTML = stack.map((e, i) => `<span data-i="${i}">${esc(label(e))}</span>`).join(" › ");
    document.getElementById("ent-back").style.visibility = stack.length > 1 ? "visible" : "hidden";
    body.innerHTML = ({ term: renderTerm, inst: renderInst, topic: renderTopic })[t](id);
    drawer.scrollTop = 0;
  }
  function close() { drawer.classList.remove("open"); scrim.classList.remove("open"); drawer.setAttribute("aria-hidden", "true"); stack = []; }
  const byName = { term: E.term_index, inst: E.inst_index, topic: E.topic_index };
  window.openEntity = (t, nameOrId) => open(t, typeof nameOrId === "number" ? nameOrId : byName[t][nameOrId]);

  document.addEventListener("click", (ev) => {
    const el = ev.target.closest("[data-ent]");
    if (el) { const id = el.dataset.id != null ? +el.dataset.id : byName[el.dataset.ent][el.dataset.name]; open(el.dataset.ent, id); return; }
    const c = ev.target.closest("#ent-crumbs span");
    if (c) { stack = stack.slice(0, +c.dataset.i + 1); const e = stack[stack.length - 1]; open(e.t, e.id, false); }
  });
  document.getElementById("ent-back").onclick = () => { stack.pop(); const e = stack[stack.length - 1]; if (e) open(e.t, e.id, false); else close(); };
  document.getElementById("ent-close").onclick = close;
  scrim.onclick = close;
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
})();
