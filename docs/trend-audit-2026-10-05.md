# 关键词趋势审计 · 2026-10-05

这轮检查覆盖 ECTC、ICASSP、EMBC、IEEE S&P 和 GLOBECOM 的 2016–2025 年本地语料，共 **49,731 篇记录**。结论是：跨领域频率不能判断技术词有没有意义；计数能复算，也不代表语义归并正确。修复了技术词误过滤、`loss → LoS` 错误归并，以及 Explore 论文查询参数不一致。

## 过滤规则

旧规则将达到“其他三个领域各至少 1% 提及率”的短语全部隐藏。31 组预先选定的会议—关键词中，22 组被隐藏，其中 15 组是应该保留的技术词。

现在只有同时满足以下条件的短语才会被隐藏：

1. 精确命中 `background.BOILERPLATE` 中的 22 个套话短语；
2. 跨领域频率仍满足原来的阈值。

名单是可审阅的保守编辑规则，不是语义分类器。未列入的短语默认保留；`high performance computing` 不继承 `high performance` 的排除。原来的 `--keep-common` 和网页开关仍能恢复这些套话。

| 会议 | 记录数 | 旧规则隐藏短语数 | 新规则隐藏短语数 | 固定检查集中恢复的技术词 |
|---|---:|---:|---:|---|
| ECTC | 3,655 | 80 | 7 | artificial intelligence、deep learning |
| ICASSP | 19,994 | 91 | 10 | deep learning、neural networks、real time |
| EMBC | 14,514 | 134 | 13 | machine learning、deep learning、neural networks、real time |
| IEEE S&P | 1,368 | 64 | 7 | machine learning、neural networks、end to end |
| GLOBECOM | 10,200 | 92 | 8 | reinforcement learning、neural networks、energy consumption |

这些技术词恢复了参与排名的资格，不保证都进入首页前几名。固定检查集中的 7 组套话（各会议的 high performance，以及 ECTC/GLOBECOM 的 low cost）仍被过滤。

## 计数与升降幅度

保留了三个阶段的快照：原始基线、只改过滤规则、完成缩写修复。机器可读结果见 [审计 JSON](trend-audit-2026-10-05.json)，包含逐年计数、前后半期份额、升降幅度、是否隐藏、样例 DOI，以及语料 SHA-256。

- 基线检查 102 组会议—关键词；只改过滤后检查 118 组，原有 102 组计数、份额、升降幅度全部不变。
- 最终 120 组检查均通过，包含固定关键词及修改前后榜单的代表词。原始 102 组中，101 组计数不变；变化的是下面查出的 ICASSP / line of sight。脚本直接扫描归一化后的 token 窗口，独立汇总逐年命中数，再复算 2016–2020 和 2021–2025 的合并份额。
- 分母是对应半期全部记录数，不是年度比例的简单平均。每篇论文对同一个词最多计一次。
- 该检查不调用生产代码的 `phrase_roles`、`momentum` 或 `papers_with` 来汇总，但共享 tokenizer 和缩写词典。因此它能验证计算一致性，不能独立证明语义准确率。

## 实际缩写错误：loss 被当成 LoS 的复数

ICASSP 的 `LoS → line of sight` 定义在语料中出现 26 次。旧代码将所有尾部 `s` 当成潜在复数，把普通单词 `loss` 读成了 `LoS`。

| ICASSP 的 line of sight | 原来 | 修复后 |
|---|---:|---:|
| 满足标题或摘要重复规则的记录数 | 650 | 14 |
| 2016–2020 份额 | 2.08% | 0.09% |
| 2021–2025 份额 | 3.98% | 0.06% |

原来命中的 [Beyond L2-loss functions for learning sparse models](https://doi.org/10.1109/icassp.2016.7472567) 和 [Reducing Spelling Inconsistencies in Code-Switching ASR Using Contextualized CTC Loss](https://doi.org/10.1109/icassp39728.2021.9413806) 讨论损失函数，不支持“line of sight 上升”的解读。

修复后的例子包括 [GNSS 多径抑制](https://doi.org/10.1109/icassp.2016.7472941) 和 [MuG 多径定位](https://doi.org/10.1109/icassp39728.2021.9414329)，正文摘要明确讨论视距信号/路径。

修复保留 token 的大小写到复数判断阶段：`loss`、`Loss`、`LOSS` 不展开为 LoS，明确写成 `LoSs`、`MBSs` 的复数仍归并。回归测试覆盖普通词与明确复数出现在同一文本、长形式收缩、定义处不重复计数，以及原有 RDLs/TSVs 行为。

## 论文内容抽查与解释边界

以下是有意选择的诊断样例，不是随机抽样，也不据此报告精确率。

| 会议 / 短语 | 样例 | 阅读判断 |
|---|---|---|
| ECTC / deep learning | [Volterra 核提取](https://doi.org/10.1109/ectc.2019.00291) | 标题明确，摘要描述神经网络训练和仿真方法，应保留。|
| ECTC / artificial intelligence | [降低封装翘曲的基板材料](https://doi.org/10.1109/ectc32696.2021.00129) | AI 在应用背景重复出现，但论文贡献是材料与可靠性；重复规则会计入，不能称为 AI 方法论文。|
| ICASSP / deep learning | [非母语语音评分](https://doi.org/10.1109/icassp.2016.7472857) | 明确比较深度学习语音识别架构，跨领域常见不应成为排除原因。|
| EMBC / machine learning | [ICU 死亡风险计算器](https://doi.org/10.1109/embc46164.2021.9631058) | 摘要描述机器学习方法及比较实验；即使标题没有该词，重复提及也有实际内容支持。|
| EMBC / magnetic resonance imaging | [XCloud-pFISTA](https://doi.org/10.1109/embc46164.2021.9630813) | 标题使用 MRI，摘要给出长形式定义，归并有依据。|
| IEEE S&P / end to end | [Verena](https://doi.org/10.1109/sp.2016.58) | 端到端完整性是论文核心保证，不是应按跨领域频率删除的套话。|
| GLOBECOM / reinforcement learning | [盲干扰对齐](https://doi.org/10.1109/glocom.2016.7841815) | 强化学习用于天线配置选择，标题和方法均支持。|
| GLOBECOM / energy consumption | [联邦元学习](https://doi.org/10.1109/globecom46510.2021.9685127) | 计算/通信能耗是设计与比较指标，词义有技术内容。|

网页、CLI 和 README 已改为说明“标题出现或摘要重复”的规则，不再保证命中的词一定是论文研究主题。下降也仅表示词汇份额下降，不能自动解释成技术衰落或成熟。

缩写还有未解决的语义边界：S&P 的 MITM 定义有 5 篇 man-in-the-middle、1 篇 meet-in-the-middle；ECTC/ICASSP 的 RF 也同时出现 radio frequency 和 random forest。局部定义优先于全语料多数定义，但没有局部定义时仍依赖多数规则；不同长形式收缩成同一个短写后也可能混合。新增测试保护局部定义优先，不能把它当作完整消歧。

定义提取本身也可能过短，例如 GLOBECOM 的 EE 常被提取为 `efficiency` 而非完整的 `energy efficiency`。本轮没有将这类需要重新评估的定义提取规则整体替换。

## 追溯修复与复核方式

Explore 的论文查询原先没有完整传递关键词长度和自定义停用词；局部缩写重新归一化时可能采用不同参数。现在查询沿用相同参数，新增测试覆盖只看单词、以及把缩写加入停用词的情况。

```bash
# 使用当前归一化规则复现旧的“仅看跨领域频率”过滤方式
.venv/bin/python -m scripts.audit_trends --label before
# 对照上一步：默认要求既有词的所有计数保持不变
.venv/bin/python -m scripts.audit_trends --label after

# 对照本次修复前保留的历史基线时，允许并记录缩写修复造成的计数变化
.venv/bin/python -m scripts.audit_trends --label after --allow-count-changes
.venv/bin/python -m pytest -q
```

历史 baseline 在修复缩写前采集；现在执行 `--label before` 只复现旧过滤规则，不重新引入旧缩写 bug，并会覆盖同名本地证据文件。历史的三个阶段摘要已经固化在本目录 JSON 中。包含完整摘要的本地证据在被 Git 忽略的 `data/trend-audit/`。

验证结果：84 项测试通过（包含 Streamlit AppTest），19 个报告和首页已重新生成。静态检查通过：38 段内联 JavaScript 语法有效，2,505 个详情面板的逐年数之和等于总数，340 组榜单/面板序列一致，图表容器和本地页面链接有效。本轮没有浏览器视觉验收。

本轮仍不是全库人工标注、官方论文集召回率验证或主题语义准确率评测。会议与年份覆盖限制见 [会议覆盖审计](venue-audit-2026-10-05.md)。
