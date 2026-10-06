"""The relational layer behind the report's detail panel: which institutions write about a
phrase, which phrases travel together, what a topic's institutions are, and the papers
behind each. Everything is derived from the same counts the page shows (topical phrase
counts, rolled-up institutions, NMF topics) so the panel never contradicts the charts."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any, Callable

from ..keywords import KeywordTrends
from ..rank import Ranking, entities_of
from ..store import Record
from ..text import TOPICAL_ROLES, term_mentions
from ..topics import TopicTrends
from ..viz import CATEGORICAL
from .explorer import ExplorerBuilder

N_TERMS, N_INSTS = 150, 60
MIN_CO = 8        # papers two phrases must share before a co-occurrence is reported
MIN_LIFT = 1.3    # ... and how far above chance
MIN_DISTINCT = 5  # papers an institution needs on a phrase for it to count as a signature


def _nested(a: str, b: str) -> bool:
    return a in b or b in a


def build_entities(recs: list[Record], kt: KeywordTrends, tt: TopicTrends, inst: Ranking, show: Callable[[str], str],
                   *, n_terms: int = N_TERMS, n_insts: int = N_INSTS,
                   required_terms: Iterable[str] = (), explore_terms: Iterable[str] = ()) -> dict[str, Any]:
    years = kt.years
    N = len(recs)
    split = years[len(years) // 2]

    # ---- which phrases, which institutions, which topics -----------------------------
    chosen = list(dict.fromkeys([
        *kt.top_terms(n_terms, min_total=5),
        *(t for t in required_terms if t in kt.doc_freq and kt.total(t)),
    ]))
    chosen_set = set(chosen)
    term_id = {t: i for i, t in enumerate(chosen)}
    top_insts = inst.top(n_insts)
    inst_id = {k: i for i, k in enumerate(top_insts)}
    topics = tt.ordered()
    topic_pos = {t.id: i for i, t in enumerate(topics)}
    explorer = ExplorerBuilder(recs, kt, tt, inst, show, explore_terms)

    # ---- per paper: phrases it is about, its institutions, its topic ---------------------
    paper_terms: list[list[int]] = []
    paper_insts: list[list[int]] = []
    paper_topic: list[int | None] = []
    for i, r in enumerate(recs):
        roles = term_mentions(r.get("title"), r.get("abstract") if kt.text_mode != "title" else None,
                              kt.n_min, kt.n_max, kt.stopwords, kt.acronyms)
        explorer.add(i, roles)
        paper_terms.append(sorted(term_id[t] for t, role in roles.items()
                                  if t in chosen_set and (kt.basis == "any" or role in TOPICAL_ROLES)))
        paper_insts.append(sorted({inst_id[k] for k in entities_of(r, "institution", roll_up=True) if k in inst_id}))
        k = tt.assignments.get(i)
        paper_topic.append(topic_pos[k] if k is not None and k in topic_pos else None)

    term_n: Counter[int] = Counter(t for ts in paper_terms for t in ts)
    term_inst: dict[int, Counter[int]] = defaultdict(Counter)
    term_topic: dict[int, Counter[int]] = defaultdict(Counter)
    term_papers: dict[int, list[int]] = defaultdict(list)
    inst_term: dict[int, Counter[int]] = defaultdict(Counter)
    inst_topic: dict[int, Counter[int]] = defaultdict(Counter)
    inst_papers: dict[int, list[int]] = defaultdict(list)
    collab: dict[int, Counter[int]] = defaultdict(Counter)
    topic_inst: dict[int, Counter[int]] = defaultdict(Counter)
    topic_papers: dict[int, list[int]] = defaultdict(list)
    co: Counter[tuple[int, int]] = Counter()
    for i in range(N):
        ts, ins, tp = paper_terms[i], paper_insts[i], paper_topic[i]
        if tp is not None:
            topic_papers[tp].append(i)
        for t in ts:
            term_papers[t].append(i)
            if tp is not None:
                term_topic[t][tp] += 1
            for j in ins:
                term_inst[t][j] += 1
                inst_term[j][t] += 1
        for a_i, a in enumerate(ts):
            for b in ts[a_i + 1 :]:
                co[(a, b)] += 1
        for j in ins:
            inst_papers[j].append(i)
            if tp is not None:
                inst_topic[j][tp] += 1
                topic_inst[tp][j] += 1
            for k in ins:
                if k != j:
                    collab[j][k] += 1

    cites = [r.get("cited_by_count") or 0 for r in recs]

    def top_cited(idxs: list[int], k: int = 6) -> list[int]:
        return sorted(idxs, key=lambda i: (-cites[i], -(recs[i].get("publication_year") or 0)))[:k]

    def co_list(t: int, k: int = 8) -> list[list]:
        rows = []
        for (a, b), n in co.items():
            if n < MIN_CO or t not in (a, b):
                continue
            o = b if a == t else a
            if _nested(chosen[t], chosen[o]):
                continue
            lift = (n / N) / ((term_n[t] / N) * (term_n[o] / N)) if term_n[t] and term_n[o] else 0
            if lift > MIN_LIFT:
                rows.append([o, round(lift, 1), n])
        rows.sort(key=lambda r: -(r[2] * math.log(r[1])))
        return rows[:k]

    # ---- output ---------------------------------------------------------------------------
    terms_out = []
    for t, i in term_id.items():
        e, l, d = kt.momentum(t)
        tt_c = term_topic[i]
        tot = sum(tt_c.values()) or 1
        terms_out.append({
            "id": i, "term": show(t), "total": kt.total(t), "early": round(e, 4), "late": round(l, 4), "delta": round(d, 4),
            "first": min((y for y, n in kt.doc_freq[t].items() if n), default=years[0]),
            "topic": max(tt_c, key=tt_c.get) if tt_c else None,
            "topics": [[k, round(v / tot, 3)] for k, v in tt_c.most_common(4)],
            "series": [{"y": y, "s": round(kt.share(t, y), 4), "n": kt.doc_freq[t].get(y, 0)} for y in years],
            "insts": [[k, n] for k, n in term_inst[i].most_common(8)],
            "co": co_list(i), "papers": top_cited(term_papers[i]),
        })

    per_year = Counter(r.get("publication_year") for r in recs)
    insts_out = []
    for key, j in inst_id.items():
        n_i = inst.total(key)
        e, l, d = inst.momentum(key)
        sig = []
        for t, n in inst_term[j].items():
            if n >= MIN_DISTINCT and term_n[t]:
                lift = (n / n_i) / (term_n[t] / N)
                if lift > 1.4:
                    sig.append([t, round(lift, 1), n])
        sig.sort(key=lambda r: -(r[2] * math.log(r[1])))
        mix = inst_topic[j]
        tot = sum(mix.values()) or 1
        insts_out.append({
            "id": j, "name": inst.names[key], "total": n_i, "early": round(e, 4), "late": round(l, 4), "delta": round(d, 4),
            "series": [{"y": y, "n": inst.by_year[key].get(y, 0), "s": round(inst.share(key, y), 4)} for y in years],
            "terms": sig[:8], "topics": [[k, round(v / tot, 3)] for k, v in mix.most_common(5)],
            "collab": [[k, n] for k, n in collab[j].most_common(6)], "papers": top_cited(inst_papers[j]),
        })

    topics_out = []
    for pos, t in enumerate(topics):
        e, l, d = tt.momentum(t.id)
        key_terms = Counter({term_id[x]: kt.total(x) for x in chosen if term_topic[term_id[x]] and max(term_topic[term_id[x]], key=term_topic[term_id[x]].get) == pos})
        topics_out.append({
            "id": pos, "label": t.label, "terms": t.terms[:8], "color": CATEGORICAL[pos % len(CATEGORICAL)] if pos < 6 else "#CFCCC4",
            "total": tt.total(t.id), "early": round(e, 4), "late": round(l, 4), "delta": round(d, 4),
            "series": [{"y": y, "s": round(tt.share(t.id, y), 4), "n": tt.by_year[t.id].get(y, 0)} for y in years],
            "key_terms": [i for i, _ in key_terms.most_common(8)],
            "insts": [[j, n] for j, n in topic_inst[pos].most_common(8)], "papers": top_cited(topic_papers[pos]),
        })

    # Only papers some panel lists are shipped (a few per entity), renumbered densely: the
    # full corpus would be 2+ MB for CVPR and the page never shows it.
    used = sorted({p for group in (terms_out, insts_out, topics_out) for e in group for p in e["papers"]})
    new_idx = {old: new for new, old in enumerate(used)}
    for group in (terms_out, insts_out, topics_out):
        for e in group:
            e["papers"] = [new_idx[p] for p in e["papers"]]
    papers_out = [{"t": recs[i].get("title") or "", "y": recs[i].get("publication_year"),
                   "d": (recs[i].get("doi") or "").replace("https://doi.org/", ""), "c": cites[i], "tp": paper_topic[i]} for i in used]
    return {
        "explorer": explorer.finish(),
        "years": years, "split": split, "n_papers": N,
        "terms": terms_out, "insts": insts_out, "topics": topics_out, "papers": papers_out,
        # lookups from the names printed on the page
        "term_index": {t["term"]: t["id"] for t in terms_out},
        "inst_index": {i["name"]: i["id"] for i in insts_out},
        "topic_index": {t["label"]: t["id"] for t in topics_out},
    }
