// Optional DOM integration test: NODE_PATH=<jsdom install>/node_modules node --test tests/explorer-dom.test.cjs
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { spawnSync } = require('node:child_process');
let JSDOM;
try { ({ JSDOM } = require('jsdom')); } catch { /* core Node tests remain dependency-free */ }
let html;
function fixture() {
  if (html) return html;
  const result = spawnSync('.venv/bin/python', ['-c', `
from paper_trends.report.analysis import analyze_corpus
from paper_trends.report.build import build_explorer_data
from paper_trends.report.render import render_explorer_page
records=[]
for y, roles in [(2018, ['title']*2+['repeated']*2+['once']*2+['none']*2), (2020, ['title','repeated']+['once']*2+['none']*4)]:
    for i,role in enumerate(roles):
        records.append({'id':f'{y}-{i}', 'publication_year':y,
          'title':'Hybrid bonding' if role=='title' else 'Interconnect reliability <img id="probe" src=x>',
          'abstract':'Hybrid bonding improves hybrid bonding.' if role=='repeated' else 'Hybrid bonding is used.' if role=='once' else 'Thermal resistance heat sink cooling.',
          'doi':'javascript:alert(1)' if i==0 else f'10.1109/test.{y}.{i}', 'cited_by_count':i,
          'authorships':[{'institutions':[{'id':'I1','name':'Lab Alpha'}]},{'institutions':[{'id':'I1','name':'Lab Alpha'}]}]})
print(render_explorer_page(build_explorer_data(analyze_corpus(records,slug='test',n_topics=2),name='Test conference',slug='test')))
`], { encoding: 'utf8', maxBuffer: 5 * 1024 * 1024 });
  assert.equal(result.status, 0, result.stderr);
  html = result.stdout;
  return html;
}
function mount(edit, lang = 'en') {
  const page = fixture(), dom = new JSDOM(page, { runScripts: 'outside-only', url: 'http://localhost/test.html' });
  const win = dom.window, data = JSON.parse(page.match(/window\.ENTITIES = (.*);/)[1]);
  if (edit) edit(data.explorer);
  win.ENTITIES = data;
  win.REPORT_LANG = lang;
  const timers = new Map(); let next = 0;
  win.setInterval = fn => { timers.set(++next, fn); return next; };
  win.clearInterval = id => timers.delete(id);
  win.eval(fs.readFileSync('paper_trends/report/static/explorer.js', 'utf8'));
  const get = id => win.document.getElementById('obs-' + id);
  const input = (id, value, event='input') => { get(id).value = value; get(id).dispatchEvent(new win.Event(event, { bubbles: true })); };
  input('term', data.explorer.terms.findIndex(t => t.key === 'hybrid bonding'), 'change');
  return { dom, win, data: data.explorer, get, input, timers };
}

test('changing counting rules and time updates real explorer DOM, evidence and institutions', { skip: !JSDOM }, () => {
  const { dom, win, get, input } = mount();
  try {
    assert.equal(get('share').textContent, '37.5%');
    win.document.querySelector('[data-rule="title"]').click();
    assert.equal(get('share').textContent, '18.8%');
    assert.equal(get('matches').textContent, '3 of 16 records');
    assert.equal(get('results-count').textContent, '(3)');
    assert.equal(get('results-body').querySelectorAll('tr').length, 3);
    assert.equal(get('papers').querySelectorAll('article').length, 3);
    assert.equal(get('institutions').querySelector('b').textContent, '3');
    assert.equal([...get('topics').querySelectorAll('b')].reduce((n, e) => n + Number(e.textContent), 0), 3);
    const abstract = get('papers').querySelector('details');
    abstract.querySelector('summary').click();
    assert.equal(abstract.open, true);
    assert.ok(abstract.querySelector('p').textContent.length > 0);
    win.document.querySelector('[data-rule="any"]').click();
    assert.equal(get('share').textContent, '62.5%');
    assert.equal(get('results-count').textContent, '(10)');
    assert.equal(get('results-body').querySelectorAll('tr').length, 10);
    assert.equal(get('more').hidden, false);
    get('more').click();
    assert.equal(get('papers').querySelectorAll('article').length, 10);
    input('from', 2);
    assert.equal(get('share').textContent, '50.0%');
    assert.equal(get('period').textContent, '2020');
    assert.equal(get('results-count').textContent, '(4)');
    assert.ok([...get('results-body').querySelectorAll('tr')].every(e => e.textContent.includes('2020')));
    assert.equal(get('papers').querySelectorAll('article').length, 4);
    assert.ok([...get('papers').querySelectorAll('.obs-paper-meta')].every(e => e.textContent.includes('2020')));
    input('from', 1); input('to', 1);
    assert.equal(get('share').textContent, '—');
    assert.ok(get('papers').textContent.includes('No matching papers'));
    assert.equal(get('ranking').querySelectorAll('button').length, 0);
    assert.equal(get('results-count').textContent, '(0)');
    assert.equal(get('download').disabled, true);
    get('reset').click();
    assert.equal(get('matches').textContent, '10 of 16 records');
    assert.equal(win.document.querySelector('#probe'), null);
    assert.ok([...get('papers').querySelectorAll('a')].every(a => a.href.startsWith('https://doi.org/')));
    assert.equal(win.document.querySelector('#ent-drawer'), null);
    assert.deepEqual(Object.keys(win.ENTITIES), ['explorer']);
  } finally { dom.window.close(); }
});
test('Chinese interactions keep counts and original evidence while updating translated copy', { skip: !JSDOM }, () => {
  const { dom, win, get, input, timers } = mount(undefined, 'zh');
  try {
    assert.equal(get('share').textContent, '37.5%');
    assert.equal(get('matches').textContent, '16 篇中有 6 篇匹配');
    assert.match(get('sample-note').textContent, /并非全部结果/);
    win.document.querySelector('[data-rule="title"]').click();
    assert.equal(get('share').textContent, '18.8%');
    assert.match(get('rule-note').textContent, /仅统计标题/);
    assert.match(get('papers').textContent, /Hybrid bonding/);
    assert.match(get('papers').textContent, /阅读摘要/);
    input('from', 1); input('to', 1);
    assert.match(get('papers').textContent, /没有匹配论文/);
    get('play').click();
    assert.equal(get('play').textContent, '❚❚ 暂停');
    get('play').click();
    assert.equal(get('play').textContent, '▶ 逐年播放');
    assert.equal(timers.size, 0);
  } finally { dom.window.close(); }
});

test('complete evidence paginates and exports all filtered rows, not just the visible page or samples', { skip: !JSDOM }, () => {
  const { dom, win, get, input } = mount(data => {
    const term = data.terms.find(t => t.key === 'hybrid bonding');
    for (let i = 0; i < 25; i++) {
      term.matches.push([0, 0, data.results.length]);
      data.results.push({ id: `extra${i}`, year: 2018, title: `Extra evidence ${i}`, citations: i, doi: '' });
    }
    term.counts[0][0] += 25;
    data.papers_per_year[0] += 25;
  });
  try {
    get('results').querySelector('summary').click();
    assert.equal(get('results').open, true);
    assert.equal(get('matches').textContent, '31 of 41 records');
    assert.equal(get('results-count').textContent, '(31)');
    assert.equal(get('results-body').querySelectorAll('tr').length, 20);
    get('next').click();
    assert.equal(get('results-body').querySelectorAll('tr').length, 11);
    assert.equal(get('page').textContent, 'Page 2 of 2');
    let csv, downloaded;
    win.Blob = class { constructor(parts) { csv = parts.join(''); } };
    win.URL.createObjectURL = () => 'blob:test';
    win.URL.revokeObjectURL = () => {};
    win.HTMLAnchorElement.prototype.click = function () { downloaded = this.download; };
    get('download').click();
    assert.equal(csv.split('\r\n').length, 32); // header + all 31 papers
    assert.match(downloaded, /hybrid_bonding_2018-2020_topical\.csv/);
    assert.match(csv, /Extra evidence 24/);
    input('from', 2);
    win.document.querySelector('[data-rule="title"]').click();
    assert.equal(get('results-count').textContent, '(1)');
    get('download').click();
    assert.equal(csv.split('\r\n').length, 2);
    assert.match(csv, /"title","2020","2020"/);
    assert.doesNotMatch(csv, /Extra evidence/);
  } finally { dom.window.close(); }
});

test('playback advances, manual changes stop it, and hidden pages release timers', { skip: !JSDOM }, () => {
  const { dom, win, get, input, timers } = mount();
  try {
    get('play').click();
    assert.equal(get('period').textContent, '2018');
    assert.equal(timers.size, 1);
    [...timers.values()][0]();
    assert.equal(get('period').textContent, '2019');
    input('to', 2);
    assert.equal(timers.size, 0);
    assert.equal(get('play').getAttribute('aria-pressed'), 'false');
    get('play').click();
    win.document.dispatchEvent(new win.Event('visibilitychange'));
    assert.equal(timers.size, 0);
  } finally { dom.window.close(); }
});
test('title-only and single-year reports disable unsupported controls', { skip: !JSDOM }, () => {
  const { dom, win, get } = mount(data => { data.text_mode='title'; data.years=[2018]; data.papers_per_year=[8]; data.abstracts_per_year=[0]; data.terms.forEach(t => t.counts=t.counts.slice(0,1)); });
  try {
    assert.equal(get('play').disabled, true);
    assert.equal(get('from').disabled, true);
    const any = win.document.querySelector('[data-rule="any"]');
    assert.equal(any.disabled, true);
    any.click();
    assert.equal(get('share').textContent, '25.0%');
    assert.ok(get('coverage').textContent.includes('titles only'));
    assert.equal(get('change').textContent, 'Single-year snapshot');
  } finally { dom.window.close(); }
});
