# 科研与行业同行版

适用：LinkedIn、OpenAlex 社区、相关科研或行业群。以下为文案草稿，尚未向这些渠道发布。

## 中文

**从一条研究趋势，追到相关机构和论文：paper-trends 开源了**

一个会议过去十年在讨论什么？某个技术方向受到更多关注时，哪些机构在参与，背后有哪些论文？

我做了 paper-trends，用 OpenAlex 的公开论文元数据，把这些问题整理成可以点击探索的报告。

以 2026-11-01 获取的 ECTC 样本为例：与 hybrid bonding 匹配的论文占比，从 2016–2020 年的约 1.1%，
上升到 2021–2025 年的约 9.6%。这是前后两个五年时段的汇总占比比较；匹配规则是短语出现在标题中，
或在摘要中至少出现两次。它描述的是这个样本中的论文关注度。

点击报告中的 hybrid bonding，可以看到趋势、相关机构和高被引论文；再点击一个机构，
可以继续查看它的特色关键词和主题分布。

我放出了 ECTC 与 CVPR 的中英文在线示例，打开即可查看，无需注册或配置 API key。
工具也支持分析 OpenAlex 收录的其他会议，完整应用和命令行代码已采用 MIT 许可开源。

- 在线示例：https://minjia-hu.github.io/paper-trends/index.zh.html
- ECTC 报告：https://minjia-hu.github.io/paper-trends/ectc.zh.html
- 源码与使用说明：https://github.com/Minjia-Hu/paper-trends

OpenAlex 的会议收录、摘要和机构识别存在差异，报告中附有数据覆盖率与方法说明。
欢迎试用，也想听听你最希望分析哪个会议，以及哪些趋势值得进一步核对。

## English

**From a research trend to its institutions and papers: introducing paper-trends**

What has a conference been talking about over the past decade—and who is working on the emerging topics?

I built paper-trends to explore these questions using public metadata from OpenAlex.
In the ECTC sample fetched on 2026-11-01, the share of papers matching “hybrid bonding” rises from about 1.1% in 2016–2020
to 9.6% in 2021–2025. These are pooled shares across two five-year periods. A paper matches when the phrase
appears in its title or at least twice in its abstract.

Click a phrase to see its trend, related institutions and highly cited papers. Click an institution to follow
its signature phrases and topic mix.

The online demo includes ECTC and CVPR reports in English and Chinese, with no sign-in or API key needed
to view them. The full app and CLI are open source under MIT and can analyze other conferences indexed by OpenAlex.

- Try the demo: https://minjia-hu.github.io/paper-trends/
- ECTC report: https://minjia-hu.github.io/paper-trends/ectc.html
- Code: https://github.com/Minjia-Hu/paper-trends

Coverage, abstract availability and affiliation disambiguation vary in OpenAlex; each report includes data
and methods notes. I'd welcome feedback on useful conferences to cover and findings that deserve a closer look.

## 配图与复用

优先使用 ECTC 趋势截图，或 [8 秒交互 GIF](demo-interaction.gif)。外部直接图片地址：
<https://raw.githubusercontent.com/Minjia-Hu/paper-trends/main/docs/demo-interaction.gif>。
统计数字已按 2026-11-01 获取的语料重新核对，分析时段仍为 2016–2025；以后更新语料时需要再次核对。
现有截图和 GIF 是较早的界面快照，数值和主题标签可能不同；发布时可注明，或使用当前在线报告的截图。
