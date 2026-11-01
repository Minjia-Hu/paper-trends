# 在线示例的构建与部署

入口：<https://minjia-hu.github.io/paper-trends/>，中文：<https://minjia-hu.github.io/paper-trends/index.zh.html>。

示例包含 ECTC、CVPR 的 2016–2025 年中英文静态报告，以及报告中的短语、机构、主题详情联动。
访客无需登录或提供 API key。完整 Explore、修改分析时段、跨会议比较和抓取其他会议，请运行仓库中的应用。
图表库、字体和地图底图使用 CDN，初次访问需要联网。

## 构建

在仓库根目录运行，要求已有 `data/ectc.jsonl`、`data/cvpr.jsonl`：

```bash
uv sync --frozen
uv run python -m scripts.build_demo
python3 -m http.server 8518 --directory site/demo
```

打开 `http://localhost:8518/`，检查两种语言、图表、点击详情及手机布局。
构建过程使用现有语料，不调用 OpenAlex。若需更新数据，先按 README 的 fetch 用法获取，再构建。
默认时段固定为 2016–2025，与首批宣传案例一致；后续调整时须同步核对宣传文案中的统计口径。

`site/demo/` 下的 `demo-manifest.json` 记录生成时间、源代码提交、语料 SHA-256、报告时段、
主题数和已验证的抓取来源信息。旧语料若没有抓取时间，仍标记为 unknown/unrecorded；生成时间不代表抓取时间。
生成文件和完整 JSONL 语料均不提交到 `main`。

## 发布

GitHub Pages 使用 **Deploy from a branch → gh-pages → /(root)**。
`gh-pages` 是独立的静态产物分支；`.nojekyll` 让 GitHub 直接部署现成 HTML。
无需配置 OpenAlex Actions Secrets，也没有定时抓取任务。主分支代码变化后，需要重新生成并发布示例。

后续更新可在单独目录克隆 `gh-pages`，将下列文件从 `site/demo/` 复制过去，检查差异后正常提交和推送：

- `index.html`、`index.zh.html`、`report.css`、`.nojekyll`、`demo-manifest.json`
- `ectc.html`、`ectc.zh.html`、`ectc.json`
- `cvpr.html`、`cvpr.zh.html`、`cvpr.json`

仅发布上述文件；完整语料、`.env`、临时日志不属于站点。无需强制推送或改写部署历史。
推送后查看 GitHub 的 **pages build and deployment** 工作流，并以未登录状态检查公开网址。

## 宣传材料

- [科研与行业同行版](outreach-research.md)：以 ECTC 的一个实际趋势为例。
- [开发者与工具社区版](outreach-developers.md)：介绍工作流和实现，适合 Streamlit、V2EX 等社区。

这两份材料是待发布文案。后续数据更新时，先核对示例数字与线上报告，再发布或复用。
