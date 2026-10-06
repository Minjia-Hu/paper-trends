import json
import re
from copy import deepcopy

from paper_trends.i18n import language, chart_labels, report_copy, tr
from paper_trends.report.build import build_report
from paper_trends.report.render import render_page, render_site
from test_report import _corpus


def test_language_explicit_choice_overrides_browser():
    assert language(None, "zh-CN,zh;q=0.9,en;q=0.8") == "zh"
    assert language("en", "zh-TW") == "en"
    assert language("zh", "en-US") == "zh"
    assert language("<script>", "en-US") == "en"


def test_chinese_home_copy_reads_naturally():
    assert tr("Publication trends for any academic conference", "zh") == "从会议论文中追踪研究趋势"
    assert tr("What a field talks about, year by year", "zh") == "从历年论文，看见领域演进"
    assert tr(
        "Any conference in OpenAlex — an acronym like DAC or ISCAS, or the name as OpenAlex spells it",
        "zh",
    ) == "搜索 OpenAlex 中的会议：输入 DAC、ISCAS 等简称，或会议英文全名"
    assert tr("Semiconductor & microelectronics", "zh") == "半导体与微电子"
    assert tr("Packaging & integration", "zh") == "封装与集成"
    assert tr("Thermal management & multiphysics", "zh") == "热管理与多物理场"
    assert tr("Reliability", "zh") == "可靠性"
    assert tr("Communications & signal processing", "zh") == "通信与信号处理"
    assert tr("Communications & networking", "zh") == "通信与网络"


def test_chinese_report_keeps_exact_data_and_original_paper_text(tmp_path):
    records = _corpus()
    records[0]["title"] = 'Hybrid bonding <script>alert("x")</script>'
    r = build_report(records, name="Test Conf", slug="test", years=(2016, 2023), n_topics=2)
    before = deepcopy(r)
    en = render_page(r)
    zh = render_page(r, lang="zh")
    assert '<html lang="zh-CN">' in zh
    assert "趋势速览" in zh and "默认不包含" not in zh
    assert "关键词出现在标题中，或在摘要中至少出现两次" in zh and "前半时段" in zh
    assert "OpenAlex 收录了 Test Conf" in zh
    assert "hybrid bonding" in zh
    assert 'Hybrid bonding <script>' not in zh
    entities = lambda html: json.loads(re.search(r'window.ENTITIES = (.*);', html)[1])
    assert entities(en) == entities(zh)
    assert r == before
    render_site([r], tmp_path)
    assert (tmp_path / 'test.zh.html').exists()
    assert 'test.zh.html' in (tmp_path / 'index.zh.html').read_text()
    assert 'index.zh.html' in (tmp_path / 'test.zh.html').read_text()


def test_chinese_title_only_and_single_year_explain_limitations():
    r = build_report([{'publication_year': 2020, 'title': 'Hybrid bonding'}], name='Test', slug='test')
    zh = render_page(r, lang='zh')
    assert '目前只有一年的数据' in zh
    assert '本报告关键词统计仅使用标题' in zh
    assert '数据获取时间：未知' in zh


def test_chart_translation_does_not_change_fields_or_data():
    spec = {'data': {'values': [{'name': 'year', 'papers': 4}]}, 'encoding': {'tooltip': [{'field': 'papers'}]}}
    assert chart_labels(spec, 'zh')['encoding']['tooltip'][0] == {'field': 'papers', 'title': '论文数'}
    assert chart_labels(spec, 'zh')['data'] == spec['data']
    assert 'title' not in spec['encoding']['tooltip'][0]
