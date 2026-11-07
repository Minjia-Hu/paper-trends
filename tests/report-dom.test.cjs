// Optional DOM integration tests: NODE_PATH=<jsdom install>/node_modules node --test tests/report-dom.test.cjs
const test = require('node:test');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
let JSDOM;
try { ({ JSDOM } = require('jsdom')); } catch { /* dependency-free tests still run */ }
let fixture;
function pages() {
  if (fixture) return fixture;
  const result = spawnSync('.venv/bin/python', ['-c', `
import json
from paper_trends.report.build import build_report
from paper_trends.report.render import render_page, render_index
records=[]
for year in range(2018,2021):
    for i in range(16):
        records.append({'id':f'{year}-{i}', 'publication_year':year,
            'title':'Hybrid bonding for reliable interconnects' if i < 4+(year-2018)*3 else 'Thermal resistance and heat sink cooling',
            'abstract':'Hybrid bonding improves hybrid bonding reliability.' if i < 4+(year-2018)*3 else 'Thermal resistance improves heat sink cooling and thermal resistance.',
            'cited_by_count':i, 'doi':f'10.1109/test.{year}.{i}',
            'authorships':[{'institutions':[{'id':'I1','name':'Lab Alpha','country':'US','root_id':'I1','root_name':'Lab Alpha','root_country':'US'}]}]})
r=build_report(records,name='Test conference',slug='test',years=(2018,2020),n_topics=2)
print(json.dumps({lang:render_page(r,lang=lang) for lang in ['en','zh']} | {'download':render_page(r,standalone=True), 'index':render_index([('Test field', [(None, [('test', 'Test', 'Test conference', 48)])])],lang='zh')}))
`], { encoding: 'utf8', maxBuffer: 8 * 1024 * 1024 });
  assert.equal(result.status, 0, result.stderr);
  fixture = JSON.parse(result.stdout);
  return fixture;
}
async function mount(lang = 'en', embed) {
  const dom = new JSDOM(pages()[lang], { runScripts: 'outside-only', url: 'https://example.test/test.html' });
  if (embed) dom.window.vegaEmbed = embed;
  for (const script of dom.window.document.querySelectorAll('script:not([src])')) dom.window.eval(script.textContent);
  await dom.window.REPORT_CHARTS_READY;
  return dom;
}

test('downloaded reports retain detail navigation without links back to the app', async () => {
  const dom = await mount('download'), doc = dom.window.document;
  try {
    assert.equal(dom.window.EXPLORE_URL, null);
    assert.equal(doc.querySelector('.language-switch'), null);
    assert.ok(doc.querySelector('style'));
    doc.querySelector('[data-ent="term"]').click();
    assert.equal(doc.getElementById('ent-drawer').hidden, false);
    assert.equal(doc.querySelector('[data-obs-phrase]'), null);
    doc.querySelector('#ent-drawer [data-ent="inst"]').click();
    assert.equal(doc.getElementById('ent-heading').textContent, 'Lab Alpha');
    doc.getElementById('ent-back').click();
    doc.getElementById('ent-close').click();
    assert.equal(doc.getElementById('ent-drawer').hidden, true);
  } finally { dom.window.close(); }
});

test('entity details use buttons, trap focus and restore the opener after Escape', { skip: !JSDOM }, async () => {
  const dom = await mount(), win = dom.window, doc = win.document;
  try {
    assert.ok([...doc.querySelectorAll('[data-ent]')].every(el => el.tagName === 'BUTTON'));
    const trigger = doc.querySelector('[data-ent="topic"]');
    trigger.focus(); trigger.click();
    const drawer = doc.getElementById('ent-drawer'), heading = doc.getElementById('ent-heading');
    assert.equal(drawer.getAttribute('role'), 'dialog');
    assert.equal(drawer.getAttribute('aria-modal'), 'true');
    assert.equal(drawer.getAttribute('aria-labelledby'), heading.id);
    assert.equal(drawer.hidden, false);
    assert.equal(doc.activeElement, heading);
    assert.equal(doc.querySelector('main').inert, true);
    assert.equal(doc.querySelector('main').getAttribute('aria-hidden'), 'true');
    assert.equal(trigger.getAttribute('aria-expanded'), 'true');
    const controls = [...drawer.querySelectorAll('button,a[href]')].filter(el => !el.hidden && !el.disabled);
    const first = controls[0], last = controls[controls.length - 1];
    doc.dispatchEvent(new win.KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true }));
    assert.equal(doc.activeElement, last);
    doc.dispatchEvent(new win.KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true }));
    assert.equal(doc.activeElement, first);
    const next = drawer.querySelector('[data-ent="inst"]');
    next.click();
    assert.equal(doc.getElementById('ent-heading').textContent, 'Lab Alpha');
    assert.equal(doc.getElementById('ent-back').hidden, false);
    assert.equal(doc.querySelector('#ent-crumbs button').tagName, 'BUTTON');
    doc.getElementById('ent-back').click();
    assert.equal(doc.getElementById('ent-heading').textContent, trigger.textContent);
    doc.dispatchEvent(new win.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
    assert.equal(drawer.hidden, true);
    assert.equal(drawer.getAttribute('aria-hidden'), 'true');
    assert.equal(doc.activeElement, trigger);
    assert.equal(trigger.getAttribute('aria-expanded'), 'false');
    assert.equal(doc.querySelector('main').inert, undefined);
    assert.equal(doc.querySelector('main').getAttribute('aria-hidden'), null);
    win.openEntity('unknown', 'missing');
    assert.equal(drawer.hidden, true);
  } finally { win.close(); }
});

test('missing CDN libraries show local chart tables while details and method links still work', { skip: !JSDOM }, async () => {
  const dom = await mount('zh'), win = dom.window, doc = win.document;
  try {
    const charts = [...doc.querySelectorAll('.viz')];
    assert.ok(charts.length > 2);
    assert.ok(charts.every(chart => chart.querySelector('.chart-fallback table')));
    assert.match(doc.getElementById('fig-papers').textContent, /图表暂时无法加载/);
    assert.match(doc.getElementById('fig-papers').textContent, /2018/);
    assert.equal(doc.getElementById('map-ctl').hidden, true);
    assert.equal(doc.querySelectorAll('.report-data-table').length, 1);
    assert.equal(doc.querySelectorAll('#about table').length, 0);
    const source = doc.querySelector('#about [data-open-details="report-data"]');
    source.click();
    assert.equal(doc.getElementById('report-data').open, true);
    doc.querySelector('.report-jump [data-open-details="method-details"]').click();
    assert.equal(doc.getElementById('method-details').open, true);
    doc.querySelector('[data-ent="topic"]').click();
    assert.equal(doc.getElementById('ent-drawer').hidden, false);
    assert.equal(doc.getElementById('ent-close').textContent, '关闭 ✕');
    assert.doesNotMatch(pages().zh, /fig-bump|fig-heat/);
  } finally { win.close(); }
});

test('one rejected chart does not suppress the other charts', { skip: !JSDOM }, async () => {
  const view = { addEventListener() {}, signal() { return this; }, runAsync() { return Promise.resolve(); } };
  const dom = await mount('en', async target => {
    if (target.id === 'fig-map') throw new Error('Network unavailable');
    const svg = target.ownerDocument.createElementNS('http://www.w3.org/2000/svg', 'svg');
    target.appendChild(svg);
    return { view };
  });
  try {
    assert.ok(dom.window.document.querySelector('#fig-papers svg'));
    assert.ok(dom.window.document.querySelector('#fig-map .chart-fallback table'));
    assert.ok(dom.window.VIEWS['fig-inst']);
  } finally { dom.window.close(); }
});

test('report phrases navigate to Explore without carrying the exploration payload', { skip: !JSDOM }, async () => {
  const dom = await mount(), win = dom.window;
  try {
    assert.equal(win.ENTITIES.explorer, undefined);
    win.EXPLORE_URL = '?conference=test&period=custom&years=2018&years=2020&view=explore';
    let target;
    win.navigateHost = url => { target = url; return true; };
    const phrase = win.ENTITIES.terms[0].term;
    win.openEntity('term', phrase);
    win.document.querySelector('[data-obs-phrase]').click();
    assert.equal(target, win.EXPLORE_URL + '&term=' + encodeURIComponent(phrase));
    assert.equal(win.document.getElementById('ent-drawer').hidden, true);
  } finally { win.close(); }
});

test('printing expands data and methods, closes the modal, and restores disclosure state', { skip: !JSDOM }, async () => {
  const dom = await mount(), win = dom.window, doc = win.document;
  try {
    const data = doc.getElementById('report-data'), methods = doc.getElementById('method-details');
    methods.open = true;
    doc.querySelector('[data-ent="topic"]').click();
    win.dispatchEvent(new win.Event('beforeprint'));
    assert.equal(doc.getElementById('ent-drawer').hidden, true);
    assert.equal(data.open, true);
    assert.equal(methods.open, true);
    assert.equal(doc.querySelector('main').getAttribute('aria-hidden'), null);
    win.dispatchEvent(new win.Event('beforeprint'));
    win.dispatchEvent(new win.Event('afterprint'));
    assert.equal(data.open, false);
    assert.equal(methods.open, true);
  } finally { win.close(); }
});

test('static bilingual metadata stays relative and faint copy meets 4.5 contrast', { skip: !JSDOM }, () => {
  const en = new JSDOM(pages().en), zh = new JSDOM(pages().zh), index = new JSDOM(pages().index);
  try {
    for (const [dom, english, chinese] of [[en, 'test.html', 'test.zh.html'], [zh, 'test.html', 'test.zh.html'], [index, 'index.html', 'index.zh.html']]) {
      const doc = dom.window.document;
      assert.equal(doc.querySelector('link[hreflang="en"]').getAttribute('href'), english);
      assert.equal(doc.querySelector('link[hreflang="zh-CN"]').getAttribute('href'), chinese);
      assert.ok(doc.querySelector('meta[property="og:description"]').content.length > 20);
      assert.ok(doc.querySelector('meta[name="description"]').content.length > 20);
      assert.equal(doc.querySelector('meta[property="og:url"]'), null);
    }
    assert.match(zh.window.document.querySelector('meta[name="description"]').content, /研究主题/);
    const css = fs.readFileSync('paper_trends/report/static/report.css', 'utf8');
    const luminance = hex => {
      const rgb = hex.match(/[a-f\d]{2}/gi).map(v => parseInt(v, 16) / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
      return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722;
    };
    const paper = luminance(css.match(/--paper:\s*(#[a-f\d]{6})/i)[1]), faint = luminance(css.match(/--faint:\s*(#[a-f\d]{6})/i)[1]);
    assert.ok((paper + .05) / (faint + .05) >= 4.5);
    assert.match(css, /@media print/);
  } finally { en.window.close(); zh.window.close(); index.window.close(); }
});
