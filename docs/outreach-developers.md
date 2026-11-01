# 开发者与工具社区版

适用：Streamlit 的 Show the Community、V2EX 分享创造等。以下为文案草稿，尚未向这些渠道发布。

## 中文

**开源 paper-trends：把学术会议论文变成可交互的趋势报告，附在线示例**

想了解一个会议的研究方向如何变化，往往要反复搜索关键词、翻论文列表，再整理机构和时间分布。
我把这套流程做成了一个 Python 工具：输入会议名称，从 OpenAlex 获取公开元数据，
生成关键词变化、主题演变和发文机构的分析报告。

最想展示的是报告里的联动：点击一个短语，会打开趋势、机构和相关论文；再点机构，可以继续查看
它的特色关键词和主题。详情面板里的数据预先计算好，所以静态 HTML 也能保留这些交互。

项目包含 CLI、Streamlit 应用和中英文静态报告，共用同一套分析代码。完整应用还支持时间窗口调整、
论文筛选、跨会议短语比较和 CSV 导出。代码采用 MIT 许可。

先试用在线示例，无需安装或配置 key：

- ECTC / CVPR 示例：https://minjia-hu.github.io/paper-trends/index.zh.html
- GitHub：https://github.com/Minjia-Hu/paper-trends

在线示例是预先生成的报告；完整 Explore 和抓取功能在本地应用中使用。
分析自己的会议需要 Python 3.12+、uv 和一个已激活的 OpenAlex key。
结果取决于 OpenAlex 的收录情况，页面提供覆盖率与统计方法说明。

欢迎反馈第一次使用时不清楚的地方，以及你希望用它回答的研究问题。

## English

**paper-trends: a Streamlit app and CLI for interactive conference research reports**

I built paper-trends to turn OpenAlex conference metadata into a report you can explore: keyword changes,
topic evolution and publishing institutions, with English and Chinese interfaces.

The interaction I wanted was a short path from a trend to its evidence. Click a phrase, inspect its curve,
institutions and cited papers, then click an institution to explore its signature phrases and topics.
These linked panels are precomputed, so they also work in the exported static HTML reports.

The Python analysis library is shared by the CLI, Streamlit app and report generator. The full app adds
time-window controls, paper filtering, cross-conference phrase comparisons and CSV exports.

- No-setup ECTC / CVPR demo: https://minjia-hu.github.io/paper-trends/
- MIT-licensed source: https://github.com/Minjia-Hu/paper-trends

The demo serves saved reports; full Explore and fetching run in the local app. Fetching a complete corpus
requires an activated OpenAlex key. Coverage and abstract availability vary, and the reports explain their
counting rules and data limitations.

I'd appreciate feedback on the report navigation, first-run experience and the research questions this could support.

## 配图与复用

推荐附上 [8 秒交互 GIF](demo-interaction.gif)，展示短语 → 机构的操作。
外部直接图片地址：<https://raw.githubusercontent.com/Minjia-Hu/paper-trends/main/docs/demo-interaction.gif>。
发到 Streamlit 社区时可使用英文标题与正文；发到 V2EX 时可直接使用中文版本。
