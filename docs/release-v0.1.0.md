# v0.1.0 发布准备

这是一份发布草案。仓库尚未公开，尚未创建 `v0.1.0` 标签或 GitHub Release。

## 已准备

- MIT 许可证、贡献指南、中英文 README、更新后的截图和交互 GIF。
- OpenAlex 分页兼容和认证错误提示、配置模板、数据及元信息原子写入、CSV 公式防护。
- Python 3.12/3.13 与前端自动测试、最小 Ruff 检查、Dependabot 每周依赖更新。
- 干净克隆安装及真实 API 端到端验证：ECTC 2019–2020，共 710 篇；这是验证时的数据快照，后续数量可能变化。
- 可手动触发的真实 API 验证脚本和工作流。普通 CI 保持离线。
- 新验证脚本已在本地联网运行通过；GitHub 端尚未配置 Secrets，也尚未执行该手动工作流。
- Git 历史中的 484 个文件对象已核对，未发现当前配置的邮箱或 API key；这不等同于排除所有类型的敏感内容。
- 仓库简介和 Topics 已配置。

## 发布前收尾

- [ ] 确认最新主分支 CI 通过，工作区干净。
- [ ] 最后检查待公开的 Git 历史、截图和文档中没有凭证或不希望公开的信息。
- [ ] 由仓库所有者确认公开仓库；在确认前保持私有。
- [ ] 在经过验证的主分支提交上创建 `v0.1.0` 标签，并使用下方说明发布 Release。
- [ ] 公开后检查 README 图片、动图、中文入口和安装链接。

按需完成：

- 在仓库 Actions Secrets 中配置 `OPENALEX_MAILTO`、`OPENALEX_API_KEY`，再手动运行
  **Live OpenAlex smoke check**。配置方式见 [贡献指南](../CONTRIBUTING.md#optional-live-api-check)。
  本地凭证不会随代码推送自动上传到 GitHub。
- 当前 Dependabot PR 保留待审查；发布不依赖于全部升级。
- 在线演示、公开部署只读模式、`SECURITY.md`、Issue 模板及 README 拆分后续按需完善。

## GitHub Release 文案（英文）

### paper-trends v0.1.0

The first public release of paper-trends: fetch public conference metadata from
OpenAlex and explore how research topics, phrases and participating institutions
change over time.

**Included**

- CLI commands for fetching, coverage inspection, keyword trends, topics,
  institution/author/country rankings and cross-conference phrase comparisons.
- A bilingual Streamlit app with Report and Explore views, supporting-paper
  evidence, linked detail panels and CSV exports.
- Shareable static HTML reports in English and Chinese.
- Configuration examples, atomic corpus writes, CSV formula protection and
  automated tests.

**Getting started**

Follow the [English README](https://github.com/Minjia-Hu/paper-trends/blob/main/README.md)
or [中文 README](https://github.com/Minjia-Hu/paper-trends/blob/main/README.zh-CN.md).
Python 3.12+ and uv are required for the documented setup. Run the project in place
with `uv run python -m paper_trends`; launch the app with `uv run streamlit run app.py`.
Complete fetches require an activated OpenAlex API key and a contact email.

**Scope and limitations**

- This is an early release. OpenAlex coverage and abstract availability vary by
  venue and year; check the coverage summary before interpreting trends.
- Analyses use public metadata and available abstracts, not paywalled full text.
  Phrase and topic trends are analytical signals, not an exhaustive literature review.
- Static reports include linked detail panels; the complete Explore workspace runs
  in the Streamlit app. Report chart libraries and fonts load from CDNs on first use.
- No hosted public demo is included in this release.

Code: MIT. OpenAlex metadata: CC0.
