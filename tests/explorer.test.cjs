const test = require('node:test');
const assert = require('node:assert/strict');
const { aggregate, series, rankContext, examples, advance, doiUrl, resultsCsv } = require('../paper_trends/report/static/explorer.js');
const csvCases = require('./csv-export-cases.json');

test('CSV text protection matches Python exports and preserves numeric cells', () => {
  const state = { lo: 0, hi: 0, mode: 'title' };
  for (const [value, expected] of csvCases) {
    const input = { years: [2025], results: [{ year: 2025, title: value, citations: 2, doi: null, id: 'W1' }] };
    const phrase = { label: 'term', matches: [[0, 0, 0]] };
    const row = ['term', 'title', 2025, 2025, 2025, expected, 2, null, 'W1'];
    const quoted = row.map(v => '"' + String(v ?? '').replace(/"/g, '""') + '"').join(',');
    assert.ok(resultsCsv(input, phrase, state).endsWith('\r\n' + quoted), JSON.stringify(value));
  }
});
const data = { years: [2020, 2021, 2022], papers_per_year: [10, 0, 100], papers: [
  { title: 'A', year: 2020, citations: 1 }, { title: 'B', year: 2022, citations: 9 }, { title: 'C', year: 2022, citations: 4 }
] };
const term = { counts: [[2, 1, 1], [0, 0, 0], [5, 5, 10]], examples: [[0, 0, 0], [2, 2, 1], [2, 1, 2]] };
test('pooled shares use all records; missing years are not false zeros', () => {
  assert.deepEqual(aggregate(data, term, { lo: 0, hi: 2, mode: 'topical' }), { total: 13, papers: 110, share: 13/110 });
  assert.deepEqual(series(data, term, 'title'), [.2, null, .05]);
  assert.deepEqual(aggregate(data, term, { lo: 1, hi: 1, mode: 'any' }), { total: 0, papers: 0, share: null });
});
test('evidence and affiliations follow both time and counting rule', () => {
  const state = { lo: 2, hi: 2, mode: 'topical' };
  assert.deepEqual(examples(data, term, state).map(p => p.title), ['C']);
  assert.deepEqual(examples(data, term, { ...state, mode: 'any' }).map(p => p.title), ['B', 'C']);
  assert.deepEqual(rankContext([{ name: 'Lab', rows: [[0, 9, 0, 0], [2, 1, 2, 3]] }], state), [{ name: 'Lab', total: 3 }]);
});
test('playback preserves window width and restarts from the beginning', () => {
  assert.deepEqual(advance({ lo: 1, hi: 3 }, 5), { lo: 2, hi: 4 });
  assert.deepEqual(advance({ lo: 2, hi: 4 }, 5), { lo: 0, hi: 2 });
});
test('paper links only navigate to DOI resolver URLs', () => {
  assert.equal(doiUrl('javascript:alert(1)'), null);
  assert.equal(doiUrl('https://example.com/10.1109/x'), null);
  assert.equal(doiUrl('https://doi.org/10.1109/x.2020'), 'https://doi.org/10.1109/x.2020');
  assert.equal(doiUrl('10.1109/<script>"'), 'https://doi.org/10.1109/%3Cscript%3E%22');
});
