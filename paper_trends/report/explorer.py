"""Exact, role-separated counts and bounded paper examples for the time explorer.

Counts and affiliations use every matching record. Only evidence examples are sampled:
at most three highest-cited records per phrase, year and exclusive mention role.
"""

from collections import Counter, defaultdict

from ..rank import entities_of
from ..text import ngrams

ROLES = {"title": 0, "repeated": 1, "once": 2}
SAMPLES_PER_BUCKET = 3
MAX_TERMS = 20


def selected_phrase_roles(title_tokens, abstract_tokens, terms, *, n_min=2, n_max=3, stopwords):
    """Count only requested phrases from cached tokens, using the shared role rules.

    This avoids generating every possible n-gram when the user changes one query.
    Invalid/unsupported phrases retain a zero result instead of changing the basis.
    """
    candidates = defaultdict(list)
    for term in dict.fromkeys(terms):
        words = term.split()
        if words and term in ngrams(words, n_min, n_max, stopwords):
            candidates[words[0]].append((term, words))

    def counts(tokens):
        found = Counter()
        for i, token in enumerate(tokens):
            for term, words in candidates.get(token, ()):
                if tokens[i:i + len(words)] == words:
                    found[term] += 1
        return found

    roles = {term: "title" for term in counts(title_tokens)}
    for term, count in counts(abstract_tokens).items():
        roles.setdefault(term, "repeated" if count >= 2 else "once")
    return roles


class ExplorerBuilder:
    def __init__(self, records, kt, tt, inst, show, terms, *, full_results=False):
        self.records, self.kt, self.tt, self.inst = records, kt, tt, inst
        self.years = list(range(kt.years[0], kt.years[-1] + 1))
        self.year_index = {y: i for i, y in enumerate(self.years)}
        self.chosen = list(dict.fromkeys(terms))[:MAX_TERMS]
        self.full_results = full_results
        self.matches = {t: [] for t in self.chosen}
        self.counts = {t: [[0, 0, 0] for _ in self.years] for t in self.chosen}
        self.labels = {t: show(t) for t in self.chosen}
        self.insts = {t: defaultdict(lambda: defaultdict(lambda: [0, 0, 0])) for t in self.chosen}
        self.topics = {t: defaultdict(lambda: defaultdict(lambda: [0, 0, 0])) for t in self.chosen}
        self.examples = {t: defaultdict(list) for t in self.chosen}

    def add(self, i, roles):
        matched = [(term, roles[term]) for term in self.chosen if term in roles]
        if not matched:
            return
        record = self.records[i]
        year = self.year_index[record["publication_year"]]
        institutions = entities_of(record, "institution", roll_up=True)
        topic = self.tt.assignments.get(i)
        for term, mention_role in matched:
            role = ROLES[mention_role]
            if self.full_results:
                self.matches[term].append([year, role, i])
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
        abstracts = Counter(r["publication_year"] for r in self.records if r.get("abstract"))
        used = sorted({i for buckets in self.examples.values() for ids in buckets.values() for i in ids})
        index = {old: new for new, old in enumerate(used)}
        result_ids = sorted({i for matches in self.matches.values() for _, _, i in matches})
        result_index = {old: new for new, old in enumerate(result_ids)}
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
                **({"matches": [[year, role, result_index[i]] for year, role, i in self.matches[term]]}
                   if self.full_results else {}),
            })
        return {
            "years": self.years,
            "papers_per_year": [self.kt.papers_per_year.get(y, 0) for y in self.years],
            "abstracts_per_year": [abstracts[y] for y in self.years],
            "text_mode": self.kt.text_mode, "terms": terms, "samples_per_bucket": SAMPLES_PER_BUCKET,
            # Full evidence stores only listing metadata; abstracts stay in bounded examples.
            **({"results": [{"id": self.records[i].get("id") or "", "title": self.records[i].get("title") or "Untitled",
                             "year": self.records[i]["publication_year"], "doi": self.records[i].get("doi") or "",
                             "citations": self.records[i].get("cited_by_count") or 0} for i in result_ids]}
               if self.full_results else {}),
            "papers": [{"title": self.records[i].get("title") or "Untitled",
                        "abstract": self.records[i].get("abstract") or "",
                        "year": self.records[i]["publication_year"],
                        "doi": self.records[i].get("doi") or "",
                        "citations": self.records[i].get("cited_by_count") or 0} for i in used],
        }
