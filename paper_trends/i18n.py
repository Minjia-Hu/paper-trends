"""Display-only translations. Never translate corpus text, identifiers or analysis data."""

import re
from copy import deepcopy


def language(value=None, accept_language=""):
    if value in {"en", "zh"}:
        return value
    # Use the browser's first language, ignoring quality parameters.
    return "zh" if accept_language.split(",")[0].strip().lower().startswith("zh") else "en"


ZH = {
    "Publication trends for any academic conference": "从会议论文中追踪研究趋势",
    "All conferences →": "全部会议 →", "Publication trends": "论文趋势",
    "papers": "篇论文", "editions": "届会议", "with abstracts": "含摘要",
    "data from OpenAlex · report generated": "数据来自 OpenAlex · 报告生成于",
    "Why some years are not used by default": "为什么默认不包含部分年份？",
    "Explicit year selections can include these editions; their counts may be incomplete.": "手动选择年份可以包含这些届次，但其记录可能不完整。",
    "At a glance": "趋势速览", "Papers per year": "历年论文数量",
    "abstract coverage": "摘要覆盖率", "What is rising": "关注度上升",
    "What is fading": "关注度下降", "New vocabulary": "新兴词汇",
    "How the field's topics shifted": "研究主题如何变化", "Topics in the selected year": "所选年份的研究主题",
    "Share of papers by dominant topic": "各主要主题的论文占比",
    "Topics fitted with NMF on titles and abstracts; each paper assigned to its strongest topic. Smaller topics folded into “Other”.": "基于标题和摘要，用 NMF 提取主题；每篇论文归入关联最强的主题，小主题合并为 Other（其他）。",
    "Who publishes": "发文机构与地区", "Where the papers come from": "论文来自哪里",
    "Institutions": "研究机构", "Countries": "国家与地区", "Year": "年份", "▶ Play": "▶ 播放",
    "❚❚ Pause": "❚❚ 暂停", "About the data": "关于数据",
    "Coverage by year": "逐年数据覆盖", "Papers": "论文数", "With abstract": "含摘要比例",
    "No cached records": "暂无缓存记录", "Generated": "生成于", "by": "由",
    "The field, in motion": "看见领域的变化", "Follow a change.": "追踪趋势，",
    "Question the evidence.": "回到论文。",
    "Move through time. Change what counts. Read the papers behind the curve.": "选择时间，切换计数规则，阅读曲线背后的论文。",
    "YOUR TIME WINDOW": "当前时间范围", "▶ Play years": "▶ 逐年播放", "Full period": "完整时段",
    "From": "起始", "To": "结束", "First year of exploration window": "探索范围的起始年份",
    "Last year of exploration window": "探索范围的结束年份", "01 / Follow a phrase": "01 / 追踪关键词",
    "Phrase to explore": "选择关键词", "Annual phrase shares under three counting rules": "三种计数规则下的年度关键词占比",
    "Counting rule": "计数规则", "Title only": "仅统计标题", "Title or repeated": "标题提及或摘要多次提及",
    "Any mention": "任意提及", "02 / Explore the window": "02 / 看看同期关注什么",
    "In the conversation": "这段时间的关注点", "Click a phrase to follow its trajectory.": "点击关键词，查看它的变化轨迹。",
    "03 / Read the evidence": "03 / 阅读论文证据", "What do these papers actually say?": "这些论文如何提及这个关键词？",
    "Show more examples": "显示更多示例", "Who is working on this?": "匹配论文来自哪些机构？",
    "Matching papers in your window. A paper can credit multiple institutions.": "统计所选时间范围内的匹配论文。一篇论文可计入多个机构。",
    "Topics around this phrase": "这个关键词涉及哪些主题",
    "Dominant topics from the full-period model, counted within your window.": "主题由完整时段的数据拟合，数量按当前时间范围统计。",
    "Title and repetition are clues, not topic labels. Repeated background mentions can still count. The report below keeps its full-period scope.": "标题和重复提及只是相关性线索，并不等于研究主题；重复出现的背景介绍也可能被计入。下方报告仍使用完整时段。",
    "This explorer needs JavaScript. The full-period report is available below.": "此探索区需要启用 JavaScript。你仍可阅读下方完整时段报告。",
    "The full-period report": "完整时段报告",
    "The same measure for the phrases losing the most share. A falling share measures a change in vocabulary, not necessarily a decline in the technique’s use. Click any phrase, institution or topic on this page to see who writes about it, what it travels with and the papers behind it.": "按同一规则，列出论文占比下降最多的词。词汇占比下降不一定意味着技术使用减少。点击关键词、机构或主题，可以查看关联机构、共现词和论文。",
    "Papers with at least one author at the institution (a paper counts once per institution; subsidiaries and institutes are credited to their parent).": "至少有一位作者来自该机构的论文数；同一篇论文在每个机构只计一次，下属单位归入上级机构。",
    "The arrow is the change in share of papers between the two halves of the period.": "箭头表示前半时段到后半时段的论文占比变化。",
    "Share of papers with at least one author in the country. Countries without a paper are left blank.": "至少有一位作者来自该国家或地区的论文占比。没有记录的地区留空。",
    "Single years are three-year rolling shares, so the picture moves rather than jumps.": "单年视图使用三年滚动占比，以平滑年度波动。",
    "Rank among the ten most prolific institutions, on a three-year rolling count of papers. Red lines climbed three places or more, blue lines slipped.": "按三年滚动论文数，展示发文最多的十家机构的排名。红线表示上升至少三位，蓝线表示排名下降。",
    "Share of each institution's papers whose dominant topic is the column; each row sums to 100 %. Dark cells are specialities.": "每列为主要研究主题，数值为该主题占机构论文的比例；每行合计 100%。颜色越深，表示该机构越集中于该主题。",
    "Topics come from non-negative matrix factorisation of TF-IDF vectors with a fixed seed, so they are reproducible; labels are the topic's top terms. Institution names and parent relationships are OpenAlex's, which are good but not perfect.": "主题通过 TF-IDF 向量的非负矩阵分解（NMF）得到，固定随机种子以保证结果可复现；名称取自主题的高权重词。机构名称和上下级关系来自 OpenAlex，可能存在匹配误差。",
    "Search": "搜索会议", "Any conference in OpenAlex — an acronym like DAC or ISCAS, or the name as OpenAlex spells it": "搜索 OpenAlex 中的会议：输入 DAC、ISCAS 等简称，或会议英文全名",
    "Period": "时段", "View": "视图", "Last 10 years": "近十年", "Last 5 years": "近五年",
    "Custom": "自选", "Report": "报告", "Explore": "探索", "Options": "选项", "Years": "年份",
    "What a field talks about, year by year": "从历年论文，看见领域演进",
    "Your own conference": "探索其他会议",
    "Curated reports, expanding over time. Coverage reflects verified OpenAlex data, not the number of conferences in each field.": "精选会议，持续扩充。当前数量反映的是已核验的 OpenAlex 数据，不代表各领域的会议规模。",
    "Semiconductor & microelectronics": "半导体与微电子", "Packaging & integration": "封装与集成",
    "Thermal management & reliability": "热管理与可靠性", "Devices & circuits": "器件与电路",
    "Artificial intelligence & perception": "人工智能与感知", "Communications & signal processing": "通信与信号处理",
    "Computer systems & security": "计算机系统与安全", "Robotics": "机器人",
    "Biomedical engineering": "生物医学工程", "More": "更多",
    "Overview": "概览", "Keywords": "关键词", "Topics": "主题", "Rankings": "排名", "Compare": "跨会议比较", "Data": "数据",
    "No papers in the selected period. Choose another range.": "所选时段没有论文，请选择其他年份。",
    "No papers with a publication year are available in this corpus.": "这份语料没有带发表年份的论文。",
    "Coverage describes cached OpenAlex records, not completeness against the official proceedings.": "覆盖率描述的是已缓存的 OpenAlex 记录，不代表相对官方会议论文集的收录完整度。",
    "Only one year is available. Rising, fading and other comparisons over time need at least two years.": "目前只有一年的数据。上升、下降等时间比较至少需要两年。",
    "The latest selected editions may be incompletely indexed. Counts and trends for these years are provisional.": "所选的最新届次可能尚未收录完整，其论文数和趋势仅供暂时参考。",
    "Topic mix in the selected year; no comparison over time is available.": "展示所选年份的主题分布；无法进行跨年比较。",
    "The order of the leading institutions barely changed.": "主要机构的排名基本没有变化。",
    "fewer than three years are available; growth is not estimated": "可用数据不足三年，不估算年增长率",
    "Data fetched: unknown (no recorded fetch timestamp)": "数据获取时间：未知（未记录）",
    "Data coverage and period details": "数据覆盖与时段说明",
    "DOI prefix(es) for a custom conference, space-separated": "其他会议的 DOI 前缀（多个前缀用空格分隔）",
    "Extra stopwords, one per line": "额外停用词（每行一个）",
    "Words to ignore in keyword and topic analyses, e.g. your field's boilerplate.": "关键词和主题分析中忽略的词，例如本领域常见、但区分研究方向作用较弱的通用表达。",
    "Refresh data from OpenAlex": "从 OpenAlex 更新数据", "Fetch by DOI prefix": "按 DOI 前缀获取数据",
    "Fetch from OpenAlex": "从 OpenAlex 获取数据", "close": "关闭",
    "By year": "逐年数据", "Papers by country": "各国家与地区的论文数",
    "N-grams": "词组长度", "Text": "文本范围", "title+abstract": "标题与摘要", "title": "标题",
    "Count every mention": "统计任意提及", "Include boilerplate phrases": "包含通用表达", "Plot terms": "选择绘图关键词",
    "Share of papers mentioning the phrase": "关键词对应的论文占比", "Rising": "上升", "Falling": "下降", "Emerging": "新兴",
    "Papers mentioning a term": "关键词对应论文", "Term": "关键词", "Top terms by year": "逐年高频词",
    "Method": "分析方法", "Topics (NMF)": "主题数量（NMF）", "NMF on titles + abstracts": "标题与摘要 NMF 分析",
    "OpenAlex topic labels": "OpenAlex 主题标签", "OpenAlex subfields": "OpenAlex 子领域",
    "Rank": "排名对象", "Sort by": "排序依据", "Show top": "显示前几名", "Roll up to parent institutions": "归并至上级机构",
    "Gaining share": "占比上升", "Losing share": "占比下降", "Compare with": "选择对比会议", "Terms": "关键词",
    "Rising everywhere": "共同上升的关键词", "Corpus (JSONL)": "论文语料（JSONL）", "Keyword table (CSV)": "关键词表（CSV）",
    "Institution ranking (CSV)": "机构排名（CSV）", "All papers in the period": "所选时段的全部论文",
    "Newest and most cited first; sortable, scrollable": "按年份从新到旧排列，同年按被引次数排序；可排序和滚动",
    "No topic data is available for the selected papers.": "所选论文暂无主题数据。",
    "Comparisons over time need at least two years. Open Data to see the papers in this period.": "时间比较至少需要两年数据。可打开“数据”查看所选时段论文。",
    "Changes in share need at least two years.": "占比变化至少需要两年数据。",
    "Fetch another preset conference to enable comparison.": "请先获取另一个预设会议的数据，再进行比较。",
    "Same terms, other conferences. Only conferences already fetched on this server are listed.": "比较相同关键词在其他会议中的占比；仅列出已获取数据的会议。",
    "Terms whose share rose in every selected conference, ranked by their smallest gain.": "这些词在所有所选会议中的占比均上升，按最小增幅排名。",
    "Topics are fitted with NMF on TF-IDF (fixed seed, reproducible). Labels are the top terms; each paper is assigned to its strongest topic.": "对 TF-IDF 使用 NMF 提取主题，固定随机种子以保证可复现。主题名称取自高权重词；每篇论文归入关联最强的主题。",
    "Each paper assigned to its strongest topic; smaller topics folded into “Other”": "每篇论文归入关联最强的主题；小主题合并为 Other（其他）",
    "A paper counts once per entity (full counting). Institution ids come from OpenAlex affiliation matching, which is imperfect: treat close ranks as ties.": "每篇论文在每个对象中计一次（完整计数）。机构由 OpenAlex 匹配，可能存在误差，接近的排名不宜过度解读。",
    "Near-absent in the first half of the range, at least 1 % of papers in the second half — the new vocabulary, ranked by current share.": "前半时段几乎未出现、后半时段占比至少 1% 的新兴词，按后半时段占比排名。",
    "Off (default): a paper counts when the phrase is in its title or repeated in its abstract. This is a relevance heuristic; repeated background mentions can still count. On: any mention counts.": "默认关闭：标题出现，或摘要中至少出现两次，才计入论文。这是相关性线索，重复的背景提及也可能计入。开启后统计任意提及。",
    "Credit the top-level parent from OpenAlex's lineage: A*STAR instead of IME, Chinese Academy of Sciences instead of its institutes.": "按 OpenAlex 的机构层级归入上级单位，例如将下属研究所归入中国科学院。",
    "Phrases come from titles and abstracts (OpenAlex has no full text). Early/late compare the pooled share of papers in the first vs. second half of the year range. Acronyms the corpus defines are read as their long form; fragments that almost always sit inside a longer phrase are folded into it; the rising and falling lists show one phrase per family.": "词组提取自标题和摘要（不涉及全文）。前期、后期指所选时段前后两半，按各半时段汇总占比比较。已定义的缩写按全称统计；稳定包含于长词中的片段会合并，上升和下降榜单每组词形只展示一个代表词。",
    "year": "年份", "term": "关键词", "early": "前期占比", "late": "后期占比", "delta": "占比变化",
    "first seen": "首次出现", "also": "相关词形", "citations": "被引次数", "institution": "机构", "country": "国家或地区",
    "author": "作者", "topic": "主题", "conference": "会议", "total": "总数", "share": "占比",
    "abstracts": "含摘要论文数", "coverage": "摘要覆盖率", "doi": "DOI", "terms": "关键词",
    "Counting keywords…": "正在统计关键词…", "Searching papers…": "正在查找论文…",
    "Fitting topic model…": "正在分析研究主题…", "Ranking…": "正在计算排名…",
    "Looking the conference up in OpenAlex…": "正在 OpenAlex 中查找会议…", "Writing the report…": "正在生成报告…",
    "Another fetch is running on this server. Please retry in a minute.": "正在获取其他会议的数据，请稍后重试。",
    "Fetching “{query}” from OpenAlex…": "正在从 OpenAlex 获取“{query}”的数据…",
    "Fetched {count:,} papers → {path}": "已获取 {count:,} 篇论文 → {path}",
    "Fetch failed: {error}. Check your network and try again in a minute.": "数据获取失败（{error}）。请检查网络后重试。",
    "Unable to fetch data from OpenAlex. Details: {error}": "暂时无法从 OpenAlex 获取数据。详细信息：{error}",
    "Unable to look up this conference. Details: {error}": "暂时无法查询此会议。详细信息：{error}",
    "Not found": "未找到匹配会议", "Found in OpenAlex": "已在 OpenAlex 找到会议", "Not fetched yet": "尚未获取数据",
    "We could not identify this conference reliably. Try its full name, or add a known DOI prefix under Options.": "暂时无法准确匹配此会议。请尝试会议全名，或在“选项”中添加已知的 DOI 前缀。",
    "About {count:,} papers since 2016": "自 2016 年起约有 {count:,} 篇论文",
    " · not on this machine yet": " · 尚未获取数据", "Not on this machine yet.": "尚未获取此会议的数据。",
    "Shared prefix.": "多个会议共用前缀。",
    "This DOI prefix is used by several venues: ": "以下会议共用此 DOI 前缀：",
    ". The fetch will include all of them.": "。获取的数据将包含这些会议的论文。",
    "One to fifteen minutes depending on the venue's size; the data is then cached on this machine.": "根据论文数量，通常需要 1–15 分钟；获取后会缓存数据，供后续使用。",
    "{growth}; abstract coverage {coverage}{note}.": "{growth}；摘要覆盖率 {coverage}{note}。",
    "Share of papers with at least one author in the country, {start}–{end}; countries without a paper are left blank": "{start}–{end} 年，至少有一位作者来自该国家或地区的论文占比；没有记录的地区留空",
    "A paper counts once per country": "同一篇论文在每个国家或地区只计一次",
    "; the arrow is the change in share between the two halves of the period": "；箭头表示前后半时段的论文占比变化",
    "Off (default): phrases on a reviewed boilerplate list (high performance, low cost, next generation…) are hidden when used by {fields} or more other fields. Cross-field technical phrases such as deep learning remain eligible.": "默认关闭：经审核的通用表达（如 high performance、low cost、next generation）若出现在至少 {fields} 个其他领域中，会从榜单隐藏。deep learning 等跨领域技术词仍参与排名。",
    "{count} boilerplate phrases used in {fields}+ other fields are hidden, e.g. {examples}. Cross-field technical phrases remain eligible.": "已隐藏 {count} 个出现在至少 {fields} 个其他领域中的通用表达，例如 {examples}。跨领域技术词仍参与排名。",
    "{start}–{end}; the number at the end of each line is the latest year": "{start}–{end} 年；曲线末端标注的是最后一年的占比",
    "{count:,} papers matching the selected counting rule, newest and most cited first.": "共 {count:,} 篇论文符合所选计数规则；按年份从新到旧排列，同年按被引次数排序。",
    "Need at least two papers with text to fit topics.": "至少需要两篇含标题或摘要的论文，才能分析研究主题。",
    "No usable vocabulary remains after text filtering.": "过滤后没有可用词汇，暂时无法分析研究主题。",
    "Corpus {path} ({size:.0f} MB) — one JSON record per paper: title, abstract, authorships, citations, OpenAlex topics.": "论文数据 {path}（{size:.0f} MB）：每篇论文对应一条 JSON 记录，包含标题、摘要、作者及所属机构、被引次数和 OpenAlex 主题。",
}


def tr(text, lang="en", **values):
    translated = narrative(text) if lang == "zh" else text
    # Format after translation so values (paper text, names, etc.) stay verbatim.
    return translated.format(**values) if values else translated


def field_label(field, lang="en"):
    """Column/sort labels have a different grammatical role from count suffixes."""
    return "论文数" if field == "papers" and lang == "zh" else tr(field, lang)


def chart_labels(specs, lang):
    """Localize presentation titles only; preserve field names, values and selections."""
    if lang != "zh":
        return specs
    labels = {"year": "年份", "share": "占比", "papers": "论文数", "name": "名称", "topic": "主题", "term": "关键词",
              "rank": "排名", "country": "国家或地区", "institution": "机构", "early share": "前半时段占比",
              "late share": "后半时段占比", "of its papers": "占机构论文比例", "papers (3-yr)": "三年论文数", "share of papers": "论文占比", "citations": "被引次数"}
    def walk(obj):
        if isinstance(obj, list):
            return [walk(v) for v in obj]
        if not isinstance(obj, dict):
            return obj
        out = {k: (v if k in {"data", "values", "datasets"} else walk(v)) for k, v in obj.items()}
        if isinstance(out.get("title"), str):
            out["title"] = labels.get(out["title"], out["title"])
        if "tooltip" in out and isinstance(out["tooltip"], list):
            for field in out["tooltip"]:
                if isinstance(field, dict) and "title" not in field:
                    field["title"] = labels.get(field.get("field"), field.get("field", ""))
        return out
    return walk(specs)


def report_copy(report, lang):
    """Translate generated narrative fields, never the entities or paper records."""
    if lang != "zh":
        return report
    r = dict(report)
    # The initial overview uses original metadata plus the same computed growth sentence.
    y0, y1 = r["year_range"]
    r["growth_sentence"] = narrative(r["growth_sentence"])
    r["glance"] = [f"OpenAlex 收录了 {r['name']} 在 {y0}–{y1} 年的 {r['n_papers']:,} 篇论文；{r['growth_sentence']}。"]
    for s in report["glance"][1:]:
        r["glance"].append("新兴词汇：" + s[len("New vocabulary: "):].rstrip(".") + "。" if s.startswith("New vocabulary: ") else "；".join(narrative(bit) for bit in s.rstrip(".").split("; ")) if "gained the most" in s or "among countries" in s else narrative(s))
    for key in ("topic_sentence", "inst_rank_sentence", "coverage_note"):
        r[key] = "；".join(narrative(bit) for bit in r[key].split("; "))
        if r[key].endswith("."):
            r[key] = r[key][:-1] + "。"
    # Specialisation narrative: keep institution and topic labels verbatim.
    s = r["inst_topic_sentence"]
    s = re.sub(r"(.*?) is the most focused: (.*?) of its papers are about “(.*?)”, against (.*?) of the conference\.", r"\1 的主题集中度最高：\2 的论文归入“\3”，该主题在整个会议中的占比为 \4。", s)
    s = re.sub(r"No leading institution specialises much; the most focused is (.*?), (.*?) of its papers are about “(.*?)”, against (.*?) of the conference\.", r"在本会议收录的论文中，主要机构的主题分布没有明显的相对集中；相对最集中的 \1 有 \2 的论文归入“\3”，会议整体占比为 \4。", s)
    r["inst_topic_sentence"] = s
    r["analysis_notes"] = [narrative(s) if not s.startswith("Topics are unavailable:") else "主题分析不可用：有效文本不足，无法拟合主题模型。" for s in r["analysis_notes"]]
    r["data_coverage"] = deepcopy(r["data_coverage"])
    for key in ("selection", "caveat"):
        r["data_coverage"][key] = narrative(r["data_coverage"][key])
    r["data_coverage"]["notices"] = [narrative(s) for s in r["data_coverage"]["notices"]]
    for row in r["data_coverage"]["exclusions"]:
        row["message"] = narrative(row["message"])
    label = r["data_fetched_label"]
    r["data_fetched_label"] = narrative(label)
    return r


def narrative(s):
    if s in ZH:
        return ZH[s]
    rules = [
        (r"[Oo]utput has been flat, between (.*?) and (.*?) papers a year", r"年发文量基本稳定，在 \1 至 \2 篇之间"),
        (r"[Oo]utput growing about (.*?) a year, from (.*?) to (.*?) papers", r"年发文量年均增长约 \1，从 \2 篇增至 \3 篇"),
        (r"[Oo]utput shrinking about (.*?) a year, from (.*?) to (.*?) papers", r"年发文量年均下降约 \1，从 \2 篇降至 \3 篇"),
        (r"The fastest-growing phrase is “(.*?)”, up from (.*?) to (.*?) of papers\.", r"占比上升最快的关键词是“\1”，从 \2 升至 \3。"),
        (r"(.*?) gained the most share among institutions \((.*?)\)", r"\1 的论文占比在机构中增幅最大（\2）"),
        (r"(.*?) among countries \((.*?)\)", r"\1 在国家与地区中增幅最大（\2）"),
        (r"“(.*?)” grew from (.*?) to (.*?) of papers, while “(.*?)” fell from (.*?) to (.*?)\.", r"“\1”的论文占比从 \2 增至 \3；“\4”则从 \5 降至 \6。"),
        (r"(.*?) climbed from rank (\d+) to (\d+)", r"\1 从第 \2 名升至第 \3 名"),
        (r"(.*?) slipped from (\d+) to (\d+)", r"\1 从第 \2 名降至第 \3 名"),
        (r", lowest (.*?) in (\d+)", r"，最低为 \2 年的 \1"),
        (r"Default period: (.*?) \(up to (\d+) calendar years ending before the current year\)\.", r"默认时段：\1（截至上一年，最多 \2 个自然年）。"),
        (r"Provisional period: (.*?); no past editions are cached\.", r"暂用时段：\1；尚未缓存往届数据。"),
        (r"Selected period: (.*?)\.", r"所选时段：\1。"),
        (r"Recommended default: (.*?)\.", r"推荐默认时段：\1。"),
        (r"Only (.*?) of selected records have abstracts\. Report phrase trends use titles only and may miss subjects absent from titles; topic analysis still uses available titles and abstracts\.", r"所选记录仅 \1 含摘要。关键词趋势仅统计标题，可能漏掉标题未提及的研究内容；主题分析仍使用可用的标题和摘要。"),
        (r"Abstract coverage below 90%: (.*?)\. Changes in abstract availability can affect phrase trends\.", r"以下年份摘要覆盖率低于 90%：\1。摘要收录程度的变化可能影响关键词趋势。"),
        (r"No cached records for (.*?)\. This may be a skipped edition or an indexing/query gap; it is not evidence of zero research output\.", r"以下年份没有缓存记录：\1。可能是该年未举办会议，也可能存在索引或查询缺漏，并不代表研究产出为零。"),
        (r"(\d+) is not used by default: current or future calendar year; indexing may be incomplete\.", r"默认不包含 \1 年：属于当前或未来年份，收录可能尚未完成。"),
        (r"Data fetched:\s*", "数据获取时间："),
        (r"(\d+) is not used by default: (.*)\. This may reflect incomplete indexing\.", r"默认不包含 \1 年：\2。可能尚未收录完整。"),
        (r"([\d,]+) records, below 20% of the median \((.*?)\) for the preceding (\d+) observed editions", r"仅有 \1 篇论文，不足此前 \3 届有记录会议的论文数中位数（\2）的 20%"),
        (r"only (.*?) have abstracts, at a venue with typical coverage of (.*?)%", r"摘要覆盖率仅 \1，而该会议的典型覆盖率为 \2%"),
    ]
    for pattern, replacement in rules:
        s = re.sub(pattern, replacement, s)
    return s
