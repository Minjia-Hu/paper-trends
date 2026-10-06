// Role-separated counts are complete; paper examples are explicitly sampled.
(function () {
  "use strict";
  const MODES = { title: 0, topical: 1, any: 2 };
  const count = (row, mode) => row.slice(0, MODES[mode] + 1).reduce((a, b) => a + b, 0);
  const sum = (values, lo, hi) => values.slice(lo, hi + 1).reduce((a, b) => a + b, 0);
  function series(data, term, mode) {
    return term.counts.map((row, i) => data.papers_per_year[i] ? count(row, mode) / data.papers_per_year[i] : null);
  }
  function aggregate(data, term, state) {
    const counts = term.counts.map(row => count(row, state.mode));
    const total = sum(counts, state.lo, state.hi), papers = sum(data.papers_per_year, state.lo, state.hi);
    return { total, papers, share: papers ? total / papers : null };
  }
  function rankContext(items, state) {
    return items.map(item => ({ name: item.name, total: item.rows.reduce((n, row) =>
      n + (row[0] >= state.lo && row[0] <= state.hi ? count(row.slice(1), state.mode) : 0), 0) }))
      .filter(item => item.total).sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));
  }
  function examples(data, term, state) {
    return term.examples.filter(([y, role]) => y >= state.lo && y <= state.hi && role <= MODES[state.mode])
      .map(([, role, id]) => ({ ...data.papers[id], role, id }))
      .sort((a, b) => b.citations - a.citations || b.year - a.year || a.id - b.id);
  }
  function advance(state, length) {
    const width = state.hi - state.lo;
    return state.hi >= length - 1 ? { lo: 0, hi: width } : { lo: state.lo + 1, hi: state.hi + 1 };
  }
  function doiUrl(doi) {
    const clean = String(doi || "").replace(/^https?:\/\/(?:dx\.)?doi\.org\//i, "");
    return /^10\.\d{4,9}\/\S+$/i.test(clean) ? "https://doi.org/" + encodeURI(clean).replace(/["<>]/g, encodeURIComponent) : null;
  }
  const api = { count, aggregate, series, rankContext, examples, advance, doiUrl };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; return; }
  const root = document.getElementById("observatory"), data = window.ENTITIES && window.ENTITIES.explorer;
  if (!root || !data || !data.terms.length) return;
  const L = (en, zh) => window.REPORT_LANG === "zh" ? zh : en;
  const $ = id => root.querySelector("#obs-" + id);
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pct = value => value == null ? "—" : (value * 100).toFixed(1) + "%";
  const modes = data.text_mode === "title" ? ["title"] : ["title", "topical", "any"];
  const colors = { title: "#1F4E79", topical: "#E3120B", any: "#8A877F" };
  let state = { lo: Math.max(0, data.years.length - 3), hi: data.years.length - 1,
    term: 0, mode: data.text_mode === "title" ? "title" : "topical" };
  let timer = null, shown = 6;
  for (const id of ["from", "to"]) { $(id).min = 0; $(id).max = data.years.length - 1; $(id).disabled = data.years.length < 2; }
  $("play").disabled = data.years.length < 2;
  root.querySelectorAll("[data-rule]").forEach(button => { button.disabled = !modes.includes(button.dataset.rule); });

  function stop() {
    if (timer) clearInterval(timer);
    timer = null; $("play").textContent = L("▶ Play years", "▶ 逐年播放"); $("play").setAttribute("aria-pressed", "false");
  }
  function chart(term) {
    const w = 640, h = 238, l = 46, r = 20, top = 22, bottom = 38;
    const all = modes.map(mode => series(data, term, mode));
    const max = Math.max(...all.flat().filter(v => v != null), 0.01) * 1.16;
    const x = i => data.years.length === 1 ? w / 2 : l + i / (data.years.length - 1) * (w - l - r);
    const y = v => h - bottom - v / max * (h - top - bottom);
    const left = Math.max(l, x(state.lo) - 10), right = Math.min(w - r, x(state.hi) + 10);
    let html = `<svg viewBox="0 0 ${w} ${h}" aria-hidden="true"><rect x="${left}" y="${top}" width="${right-left}" height="${h-top-bottom}" fill="#F4E6DE"/>`;
    for (let step = 0; step < 4; step++) {
      const v = max * step / 3;
      html += `<line x1="${l}" x2="${w-r}" y1="${y(v)}" y2="${y(v)}" stroke="#E6E3DC"/><text x="${l-8}" y="${y(v)+4}" text-anchor="end">${pct(v)}</text>`;
    }
    // Draw the active rule last so it remains visible when lines coincide.
    for (const mode of [...modes.filter(m => m !== state.mode), state.mode]) {
      const values = series(data, term, mode); let path = "", pen = false;
      values.forEach((v, i) => { if (v == null) { pen = false; return; } path += `${pen ? "L" : "M"}${x(i)},${y(v)} `; pen = true; });
      html += `<path d="${path}" fill="none" stroke="${colors[mode]}" stroke-width="${mode===state.mode ? 3 : 1.5}" opacity="${mode===state.mode ? 1 : .48}" ${mode==="any" ? 'stroke-dasharray="5 4"' : ''}/>`;
      if (mode === state.mode) values.forEach((v, i) => {
        if (v != null) html += `<circle cx="${x(i)}" cy="${y(v)}" r="${i >= state.lo && i <= state.hi ? 4 : 2}" fill="${colors[mode]}"><title>${data.years[i]}: ${pct(v)}</title></circle>`;
      });
    }
    data.years.forEach((year, i) => { if (data.years.length <= 12 || i % 2 === 0 || i === data.years.length-1)
      html += `<text x="${x(i)}" y="${h-12}" text-anchor="middle" fill="${i>=state.lo && i<=state.hi ? '#1B1B1B' : '#8A877F'}">${year}</text>`; });
    $("chart").innerHTML = html + "</svg>";
    $("chart").setAttribute("aria-label", `${term.label}${L(", annual share: ", "，年度占比：")}` + series(data, term, state.mode).map((v, i) => `${data.years[i]} ${v == null ? L("no records", "无记录") : pct(v)}`).join("; "));
  }
  function bars(id, items) {
    const top = rankContext(items, state).slice(0, 5), max = top[0]?.total || 1;
    $(id).innerHTML = top.length ? top.map(item => `<div class="obs-context-row"><div><span>${esc(item.name)}</span><b>${item.total.toLocaleString()}</b></div><i style="width:${100*item.total/max}%"></i></div>`).join("") : '<p class="obs-caption">' + L("No matching records with this metadata.", "没有包含此类元数据的匹配记录。") + '</p>';
  }
  function papers(term, total) {
    const selected = examples(data, term, state), labels = [L("In the title", "标题中出现"), L("Repeated in abstract", "摘要中重复出现"), L("Mentioned once", "仅提及一次")];
    $("sample-note").textContent = `${L(`${total.toLocaleString()} matching papers. Examples are citation-ranked, with up to ${data.samples_per_bucket} per year and mention type; they are not the full result set.`, `共 ${total.toLocaleString()} 篇匹配论文。示例按被引次数排序，每个年份、每种提及类型最多展示 ${data.samples_per_bucket} 篇，并非全部结果。`)}`;
    $("papers").innerHTML = selected.slice(0, shown).map(p => {
      const link = doiUrl(p.doi);
      return `<article class="obs-paper"><div class="obs-paper-meta"><span>${p.year} / ${labels[p.role]}</span><span>${L(`${p.citations.toLocaleString()} citations`, `被引 ${p.citations.toLocaleString()} 次`)}</span></div>` +
        `<h4>${link ? `<a href="${esc(link)}" target="_blank" rel="noopener noreferrer">${esc(p.title)} <span aria-hidden="true">↗</span></a>` : esc(p.title)}</h4>` +
        (p.abstract ? `<details><summary>${L("Read abstract", "阅读摘要")}</summary><p>${esc(p.abstract)}</p></details>` : '<p class="obs-caption">' + L("No abstract available.", "暂无摘要。") + '</p>') + "</article>";
    }).join("") || '<div class="obs-empty">' + L("No matching papers in this window. Try another year or counting rule.", "当前时段没有匹配论文，请尝试其他年份或计数规则。") + '</div>';
    $("more").hidden = selected.length <= shown;
    $("more").textContent = `${L(`Show more examples (${Math.min(shown, selected.length)} of ${selected.length})`, `显示更多示例（已显示 ${Math.min(shown, selected.length)} / ${selected.length}）`)}`;
  }
  function render() {
    const focusedRank = document.activeElement?.dataset.term;
    const term = data.terms[state.term], result = aggregate(data, term, state);
    $("from").value = state.lo; $("to").value = state.hi;
    $("from").setAttribute("aria-valuetext", String(data.years[state.lo])); $("to").setAttribute("aria-valuetext", String(data.years[state.hi]));
    $("from-value").textContent = data.years[state.lo]; $("to-value").textContent = data.years[state.hi];
    $("period").textContent = state.lo === state.hi ? data.years[state.lo] : `${data.years[state.lo]}—${data.years[state.hi]}`;
    $("denominator").textContent = `${L(`${result.papers.toLocaleString()} records in this window`, `当前时段共 ${result.papers.toLocaleString()} 篇论文`)}`;
    $("term").value = state.term;
    $("share").textContent = pct(result.share);
    $("matches").textContent = `${L(`${result.total.toLocaleString()} of ${result.papers.toLocaleString()} records`, `${result.papers.toLocaleString()} 篇中有 ${result.total.toLocaleString()} 篇匹配`)}`;
    const s = series(data, term, state.mode), first = s[state.lo], last = s[state.hi];
    $("change").textContent = state.lo === state.hi ? L("Single-year snapshot", "单年视图") : first == null || last == null ? L("Missing endpoint records; change unavailable", "起始或结束年份缺少记录，无法计算变化") : `${last-first >= 0 ? "+" : ""}${((last-first)*100).toFixed(1)}${L(" percentage points, ", " 个百分点，")}${data.years[state.lo]} → ${data.years[state.hi]}`;
    root.querySelectorAll("[data-rule]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.rule === state.mode)));
    const notes = { title: L("Only title mentions count. Acronyms are normalized using the report’s rules.", "仅统计标题中出现的关键词；缩写按报告规则归一化。"), topical: L("Title mentions or repeated abstract mentions count. A repeated background mention may still qualify.", "标题中出现，或摘要中至少出现两次，即计入。重复的背景介绍也可能符合条件。"), any: L("Every mention counts, including methods and background references made only once.", "任意提及均计入，包括仅出现一次的方法和背景介绍。") };
    $("rule-note").textContent = notes[state.mode] + L(" The large percentage pools all records in your window; the curve shows yearly shares.", " 上方百分比按所选时段汇总计算；曲线显示各年占比。");
    const abs = sum(data.abstracts_per_year, state.lo, state.hi);
    $("coverage").textContent = data.text_mode === "title" ? L("This report uses titles only because abstracts are sparse. Abstract-based rules are unavailable.", "由于收录的摘要较少，本报告仅统计标题，无法使用基于摘要的计数规则。") :
      result.papers && abs / result.papers < .9 ? `${L(`Abstracts available for ${pct(abs/result.papers)} of this window. Missing abstracts can affect the comparison.`, `当前时段 ${pct(abs/result.papers)} 的论文含摘要；摘要缺失可能影响比较。`)}` : "";
    chart(term);
    const ranking = data.terms.map((t, id) => ({ id, label: t.label, ...aggregate(data, t, state) })).filter(t => t.total)
      .sort((a, b) => b.total-a.total || a.id-b.id).slice(0, 6);
    $("ranking").innerHTML = ranking.map(t => `<button type="button" class="obs-rank" data-term="${t.id}" aria-pressed="${t.id===state.term}"><span>${esc(t.label)}</span><b>${pct(t.share)}</b><i style="width:${100*t.total/(ranking[0]?.total || 1)}%"></i></button>`).join("") || '<p class="obs-caption">' + L("No matching phrases in this window.", "当前时段没有匹配关键词。") + '</p>';
    if (focusedRank != null) root.querySelector(`[data-term="${Number(focusedRank)}"]`)?.focus({ preventScroll: true });
    $("shortlist").textContent = `${L(`Ranked within ${data.terms.length} phrases drawn from the report’s rising, fading and frequent terms. Counts use your selected rule.`, `从报告的上升词、下降词和高频词中选出 ${data.terms.length} 个候选词，按当前时段和计数规则排名。`)}`;
    bars("institutions", term.institutions); bars("topics", term.topics); papers(term, result.total);
  }
  function update(patch) { stop(); Object.assign(state, patch); shown = 6; render(); }
  $("from").addEventListener("input", e => { const lo = +e.target.value; update({ lo, hi: Math.max(lo, state.hi) }); });
  $("to").addEventListener("input", e => { const hi = +e.target.value; update({ hi, lo: Math.min(hi, state.lo) }); });
  $("term").addEventListener("change", e => update({ term: +e.target.value }));
  $("reset").addEventListener("click", () => update({ lo: 0, hi: data.years.length-1 }));
  root.addEventListener("click", e => {
    const rule = e.target.closest("[data-rule]"), phrase = e.target.closest("[data-term]");
    if (rule && !rule.disabled) update({ mode: rule.dataset.rule });
    if (phrase) update({ term: +phrase.dataset.term });
  });
  $("more").addEventListener("click", () => { shown += 6; papers(data.terms[state.term], aggregate(data, data.terms[state.term], state).total); });
  $("play").addEventListener("click", () => {
    if (timer) return stop();
    // A full-period window cannot move; play single-year frames in that case.
    if (state.hi-state.lo === data.years.length-1) { state.lo = 0; state.hi = 0; }
    else Object.assign(state, advance(state, data.years.length));
    shown = 6; render(); $("play").textContent = L("❚❚ Pause", "❚❚ 暂停"); $("play").setAttribute("aria-pressed", "true");
    timer = setInterval(() => { if (state.hi >= data.years.length-1) return stop(); Object.assign(state, advance(state, data.years.length)); render(); }, 1300);
  });
  document.addEventListener("visibilitychange", () => { if (document.hidden) stop(); });
  window.addEventListener("pagehide", stop);
  window.explorePhrase = label => {
    const term = data.terms.findIndex(t => t.label === label);
    if (term < 0) return false;
    update({ term });
    root.scrollIntoView?.({ behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' });
    $("term").focus({ preventScroll: true });
    return true;
  };
  render();
})();
