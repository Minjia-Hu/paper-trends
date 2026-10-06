"""Exact, role-separated counts and bounded paper examples for the time explorer.

Counts and affiliations use every matching record. Only evidence examples are sampled:
at most three highest-cited records per phrase, year and exclusive mention role.
"""

from collections import defaultdict

from ..rank import entities_of

ROLES = {"title": 0, "repeated": 1, "once": 2}
SAMPLES_PER_BUCKET = 3
MAX_TERMS = 20


class ExplorerBuilder:
    def __init__(self, records, kt, tt, inst, show, terms):
        self.records, self.kt, self.tt, self.inst = records, kt, tt, inst
        self.years = list(range(kt.years[0], kt.years[-1] + 1))
        self.year_index = {y: i for i, y in enumerate(self.years)}
        self.chosen = list(dict.fromkeys(t for t in terms if t in kt.doc_freq))[:MAX_TERMS]
        self.counts = {t: [[0, 0, 0] for _ in self.years] for t in self.chosen}
        self.labels = {t: show(t) for t in self.chosen}
        self.insts = {t: defaultdict(lambda: defaultdict(lambda: [0, 0, 0])) for t in self.chosen}
        self.topics = {t: defaultdict(lambda: defaultdict(lambda: [0, 0, 0])) for t in self.chosen}
        self.examples = {t: defaultdict(list) for t in self.chosen}

    def add(self, i, roles):
        record = self.records[i]
        year = self.year_index[record["publication_year"]]
        institutions = entities_of(record, "institution", roll_up=True)
        topic = self.tt.assignments.get(i)
        for term in self.chosen:
            if term not in roles:
                continue
            role = ROLES[roles[term]]
            self.counts[term][year][role] += 1
            for key in institutions:
                self.insts[term][key][year][role] += 1
            if topic is not None:
                self.topics[term][topic][year][role] += 1
            bucket = self.examples[term][year, role]
            bucket.append(i)
            bucket.sort(key=lambda p: (-(self.records[p].get("cited_by_count") or 0), p))
            del bucket[SAMPLES_PER_BUCKET:]

    def finish(self):
        used = sorted({i for buckets in self.examples.values() for ids in buckets.values() for i in ids})
        index = {old: new for new, old in enumerate(used)}
        topic_names = {t.id: t.label for t in self.tt.topics}

        def rows(table):
            return [[year, *counts] for year, counts in sorted(table.items())]

        terms = []
        for term in self.chosen:
            terms.append({
                "key": term, "label": self.labels[term], "counts": self.counts[term],
                "institutions": [{"name": self.inst.names.get(k, k), "rows": rows(counts)}
                                 for k, counts in sorted(self.insts[term].items())],
                "topics": [{"name": topic_names[k], "rows": rows(counts)}
                           for k, counts in sorted(self.topics[term].items()) if k in topic_names],
                "examples": [[year, role, index[i]] for (year, role), ids in sorted(self.examples[term].items()) for i in ids],
            })
        return {
            "years": self.years,
            "papers_per_year": [self.kt.papers_per_year.get(y, 0) for y in self.years],
            "abstracts_per_year": [sum(bool(r.get("abstract")) for r in self.records if r["publication_year"] == y) for y in self.years],
            "text_mode": self.kt.text_mode, "terms": terms, "samples_per_bucket": SAMPLES_PER_BUCKET,
            "papers": [{"title": self.records[i].get("title") or "Untitled",
                        "abstract": self.records[i].get("abstract") or "",
                        "year": self.records[i]["publication_year"],
                        "doi": self.records[i].get("doi") or "",
                        "citations": self.records[i].get("cited_by_count") or 0} for i in used],
        }
