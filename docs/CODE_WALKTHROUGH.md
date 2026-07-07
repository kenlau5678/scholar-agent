# ScholarAgent Code Walkthrough

这份文档解释 ScholarAgent 当前代码的结构、调用链、关键函数和后续扩展点。目标是让你以后回到这个项目时，能快速知道“某个功能在哪改”“数据从哪里来、到哪里去”“下一步怎么拆成更正式的后端”。

## 1. 项目整体定位

ScholarAgent 现在是一个基于 Streamlit 的文献调研原型系统。它不是简单地调用一次 LLM 生成综述，而是把调研拆成多个 agent-like 阶段：

```text
用户输入研究主题
  -> Planner 生成检索 query
  -> Search 从 arXiv 检索候选论文
  -> Ranker 用 LLM 筛选高相关论文
  -> Reader 生成论文阅读卡片
  -> Evidence 从论文材料中抽取可引用证据
  -> Comparison 生成横向对比表
  -> Writer 写 evidence-based 综述
  -> Critic 审查可信性
  -> Revision Workflow 按 Critic 反馈自动返工
```

当前 UI 是 `app.py`，核心研究逻辑放在 `scholar_agent/` 包里。这个划分很重要：以后如果加 FastAPI 或 React 前端，应尽量复用 `scholar_agent/`，而不是把核心逻辑写死在 Streamlit 页面里。

## 2. 目录结构

```text
scholar-agent/
|-- app.py
|-- requirements.txt
|-- .env.example
|-- README.md
|-- docs/
|   `-- CODE_WALKTHROUGH.md
`-- scholar_agent/
    |-- config.py
    |-- llm.py
    |-- planner.py
    |-- search_arxiv.py
    |-- ranker.py
    |-- pdf_reader.py
    |-- reader.py
    |-- evidence.py
    |-- comparison.py
    |-- writer.py
    |-- critic.py
    `-- revision_workflow.py
```

## 3. 入口文件：app.py

`app.py` 是 Streamlit 应用入口，主要负责：

- 页面配置
- 用户输入控件
- 调用各个 agent 模块
- 展示中间结果和最终报告
- 提供 Markdown 下载按钮

它不应该承担太多“业务逻辑”。目前它还直接串联了完整流程，后续推荐把这部分抽成 `scholar_agent/workflow.py`，让 `app.py` 只负责 UI。

### 主要 UI 控件

- `topic = st.text_area(...)`
  - 用户输入研究主题。
  - 默认主题是关于 RAG 降低大模型幻觉。

- `reading_mode = st.radio(...)`
  - `fast`：只读标题和摘要。
  - `deep`：下载并解析 PDF。

- `max_pdf_pages = st.slider(...)`
  - 深度模式下，每篇论文最多读取多少页 PDF。

- `top_k = st.slider(...)`
  - LLM ranker 最后保留多少篇论文。

### 主流程

点击按钮后，`app.py` 依次调用：

```python
queries = generate_queries(topic)
papers = search_papers_by_queries(queries, max_per_query=5)
ranked_papers = llm_rank_papers(topic, papers, top_k=top_k)
paper_cards = generate_paper_cards(ranked_papers, reading_mode, max_pdf_pages)
comparison_rows = generate_comparison_rows(paper_cards)
initial_survey = generate_survey(topic, paper_cards)
revision_result = run_critic_revision_loop(...)
```

`revision_result` 会返回最终版本：

```python
{
    "survey": ...,
    "paper_cards": ...,
    "critic_report": ...,
    "rounds": ...,
    "revision_count": ...,
    "reader_revision_count": ...,
}
```

## 4. 配置模块：config.py

`config.py` 负责从 `.env` 加载模型配置：

```python
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4.1-mini")
```

这里支持兼容 OpenAI API 格式的模型服务，因为 `OPENAI_BASE_URL` 可以改成其他 provider 的地址。

### 修改建议

以后如果要支持多个模型，可以扩展成：

- `PLANNER_MODEL`
- `RANKER_MODEL`
- `WRITER_MODEL`
- `CRITIC_MODEL`

这样便宜模型可以做检索规划和初筛，强模型可以做写作和审查。

## 5. LLM 封装：llm.py

`llm.py` 是所有 LLM 调用的统一入口。

### `call_llm(prompt, temperature=0.2)`

作用：

- 调用 chat completions API
- 使用统一 system prompt
- 返回纯文本

当前 system prompt 是：

```text
You are a rigorous research assistant.
Always be precise, structured, and citation-aware.
```

这会影响所有 agent 的默认行为。

### `call_llm_json(prompt, temperature=0.1)`

作用：

- 调用 `call_llm`
- 如果模型返回了 ```json 代码块，会先剥掉代码块
- 用 `json.loads` 解析
- 解析失败时抛出 `ValueError`

它被这些模块使用：

- `ranker.py`
- `evidence.py`
- `comparison.py`
- `critic.py` 里的 structured critic

### 这里最值得增强的地方

当前 JSON 解析失败就报错或返回空。后续可以加：

- 自动 JSON 修复
- 重试
- token 用量日志
- 请求耗时统计
- prompt / response 保存

这会显著提升系统稳定性。

## 6. Research Planner：planner.py

核心函数：

```python
generate_queries(topic: str) -> list[str]
```

职责：

- 把用户输入的中文研究主题拆成 5-8 个英文检索 query
- query 适合 arXiv / Semantic Scholar 一类学术搜索
- 输出一行一个 query

调用链：

```text
app.py -> generate_queries -> call_llm
```

输出示例：

```text
retrieval augmented generation hallucination mitigation
RAG factual consistency evaluation
citation grounded generation large language models
```

### 维护注意

这个模块目前只做 query 生成，不做搜索。它的输出质量会直接影响后续 paper pool。如果检索结果经常偏题，优先改这里的 prompt。

## 7. arXiv Search：search_arxiv.py

核心函数：

```python
search_arxiv(query: str, max_results: int = 5) -> list[dict]
search_papers_by_queries(queries: list[str], max_per_query: int = 5) -> list[dict]
```

### `search_arxiv`

职责：

- 拼 arXiv API URL
- 用 `requests.get` 请求 arXiv Atom feed
- 用 `feedparser` 解析结果
- 提取论文元数据

每篇论文返回结构大致是：

```python
{
    "paper_id": "...",
    "title": "...",
    "authors": ["..."],
    "summary": "...",
    "published": "...",
    "arxiv_url": "...",
    "pdf_url": "...",
    "source_query": "...",
}
```

### `search_papers_by_queries`

职责：

- 对多个 query 分别调用 `search_arxiv`
- 用 `paper_id` 去重
- 搜索失败时打印错误并继续

### 维护注意

这里现在只有 arXiv。以后如果加 Semantic Scholar，可以新增 `search_semantic_scholar.py`，再统一成一个 `search_papers()` 聚合层。

## 8. Relevance Ranker：ranker.py

核心函数：

```python
llm_rank_papers(topic: str, papers: list[dict], top_k: int = 8) -> list[dict]
```

职责：

- 把候选论文标题、摘要、来源 query 拼成 prompt
- 让 LLM 给每篇论文打 0-5 分
- 只保留分数大于等于 3 的论文
- 按分数排序，取前 `top_k`

每篇返回论文会新增：

```python
paper["relevance_score"]
paper["relevance_reason"]
```

### 评分标准

prompt 里定义了：

- 5：高度相关，核心论文
- 4：明显相关
- 3：部分相关，可做背景或补充
- 2：弱相关，不建议进入核心综述
- 1：基本不相关
- 0：完全不相关

### 维护注意

这个模块是“过滤偏题论文”的关键。如果你发现结果混入很多不相关论文，优先调：

- query planner prompt
- ranker prompt
- `score >= 3` 的阈值
- `max_per_query`

## 9. PDF Reader：pdf_reader.py

这个模块负责 PDF 下载、文本抽取和 section 识别。

依赖：

```text
PyMuPDF
requests
```

代码里通过 `import fitz` 使用 PyMuPDF。

### `download_pdf(pdf_url)`

职责：

- 下载 PDF
- 保存到系统临时目录下的 `scholar_agent_pdfs`
- 返回本地 PDF 路径

注意：PDF 文件没有放进项目目录，不会被 git 管理。

### `extract_text_from_pdf(pdf_path, max_pages=20)`

职责：

- 用 PyMuPDF 打开 PDF
- 逐页抽取纯文本
- 最多读取 `max_pages`
- 调用 `clean_pdf_text`

### `find_section_headings(text)`

职责：

- 逐行扫描文本
- 识别类似 `Abstract`、`1 Introduction`、`2.1 Method` 的标题
- 映射成规范 section 名称

规范 section 包括：

```text
abstract
introduction
related_work
method
experiments
results
limitations
conclusion
references
```

### `extract_sections(text, max_chars_per_section=5000)`

职责：

- 根据标题位置切分正文
- 跳过 references
- 过滤太短的 section
- 每个 section 最多保留一定字符数

### `fallback_select_relevant_text(text)`

如果 section 识别失败，系统不会直接放弃，而是选择：

- PDF 开头部分
- method / experiment / result / limitation / conclusion 附近片段

这就是 deep mode 的 fallback。

### `fetch_pdf_sections(pdf_url, max_pages, max_chars_per_section)`

这是外部主要调用入口：

```text
下载 PDF -> 抽取文本 -> section 切分 -> 如果失败就 fallback
```

返回一个 dict，例如：

```python
{
    "introduction": "...",
    "method": "...",
    "results": "...",
}
```

或：

```python
{
    "fallback_pdf_text": "..."
}
```

## 10. Paper Reader：reader.py

Reader 把论文材料转成结构化阅读卡片，并触发 evidence 抽取。

### `build_fast_material(paper)`

Fast mode 使用：

- title
- authors
- abstract / summary

返回：

```python
(material, "fast_abstract", ["title", "abstract"])
```

### `build_deep_material(paper, max_pdf_pages=20)`

Deep mode 使用：

- title
- authors
- arXiv abstract
- PDF section text

如果论文没有 PDF、PDF 下载失败、section 识别失败，会 fallback 到 fast mode 或 fallback text。

返回的 `source_type` 可能是：

```text
deep_pdf_sections
fast_fallback_no_pdf
fast_fallback_no_sections
fast_fallback_pdf_error: ...
```

### `generate_paper_card(...)`

职责：

1. 根据 reading mode 构造 material
2. 调用 LLM 生成阅读卡片
3. 调用 `extract_evidence_items` 抽取 evidence
4. 返回完整 card dict

返回结构：

```python
{
    "paper_id": "...",
    "title": "...",
    "authors": [...],
    "published": "...",
    "arxiv_url": "...",
    "pdf_url": "...",
    "reading_mode_used": "...",
    "sections_found": [...],
    "card": "...",
    "evidence_items": [...],
}
```

### `generate_paper_cards(...)`

简单循环，对多篇论文调用 `generate_paper_card`。

### 维护注意

如果你想提升“读论文质量”，优先改：

- `generate_paper_card` 的 prompt
- `pdf_reader.py` 的 section 抽取
- evidence 抽取 prompt

## 11. Evidence Extraction：evidence.py

Evidence 是这个项目最核心的可信性设计之一。

### `extract_evidence_items(...)`

输入：

- `paper_index`
- `paper`
- `card_text`
- `material`
- `max_evidence`

职责：

- 让 LLM 从论文材料中抽取可引用证据
- 证据 quote 必须来自材料本身
- 输出 JSON array
- 每条 evidence 都有 `evidence_id`

返回结构：

```python
{
    "evidence_id": "P1-E1",
    "paper_index": 1,
    "paper_title": "...",
    "section": "method",
    "claim_type": "method",
    "claim": "...",
    "quote": "...",
}
```

### `format_evidence_for_writer(paper_cards)`

职责：

- 把所有 paper card 里的 evidence 转成 Writer / Critic 可读的文本

输出类似：

```text
## Paper 1: ...

Evidence ID: P1-E1
Section: method
Claim Type: method
Supported Claim: ...
Quote: ...
---
```

### 维护注意

当前 evidence quote 的真实性主要依赖 LLM 遵守 prompt。以后更严谨的做法是：

- 对 quote 做字符串匹配验证
- 保存 quote 在 PDF text 中的位置
- 如果 quote 不在 material 中，就丢弃

这是提高可信度的重要下一步。

## 12. Comparison Agent：comparison.py

核心函数：

```python
generate_comparison_rows(paper_cards: list[dict]) -> list[dict]
```

职责：

- 基于所有阅读卡片生成横向对比表
- 输出 JSON array
- 每篇论文一行

每行包括：

```python
{
    "id": ...,
    "paper": "...",
    "method_category": "...",
    "core_innovation": "...",
    "techniques": "...",
    "evaluation": "...",
    "strengths": "...",
    "limitations": "...",
    "relation_to_topic": "...",
}
```

在 `app.py` 中，这个结果会被转成 pandas DataFrame 展示。

## 13. Survey Writer：writer.py

Writer 有两个入口：

```python
generate_survey(topic, paper_cards)
revise_survey(topic, paper_cards, survey, critic_feedback)
```

### `generate_survey`

职责：

- 读取 paper cards
- 读取 evidence
- 写一份中文技术综述
- 强制关键结论引用 evidence_id

要求的章节：

```text
研究背景
问题拆解
方法分类
代表性论文对比
当前方法不足
后续可研究方向
Evidence-based References
```

### `revise_survey`

职责：

- 接收 Critic 的结构化反馈
- 在已有 survey 基础上重写
- 删除或弱化无证据支持的结论
- 移除不存在的 evidence_id
- 保持章节结构

这是自动返工循环里的 Writer 节点。

### 维护注意

如果你发现最终综述太长、太泛、引用不密集，优先改 `generate_survey` 和 `revise_survey` 的 prompt。

## 14. Critic Agent：critic.py

Critic 有两个入口：

```python
critique_survey(topic, paper_cards, survey) -> str
critique_survey_structured(topic, paper_cards, survey) -> dict
```

### `critique_survey`

返回 Markdown 风格审查报告，用于展示给用户。

它检查：

- 是否引用不存在的 evidence_id
- 关键结论是否都有证据
- quote 是否支持对应结论
- 是否有过度概括
- 是否写入论文没有支持的内容
- 是否把不相关论文当核心依据

### `critique_survey_structured`

返回 JSON dict，用于自动返工控制。

返回结构：

```python
{
    "overall_judgment": "credible|partly_credible|not_credible",
    "needs_revision": True,
    "needs_reader_revision": False,
    "reader_paper_indexes": [1, 3],
    "issues": [
        {
            "severity": "high|medium|low",
            "issue_type": "...",
            "location": "...",
            "problem": "...",
            "fix": "...",
        }
    ],
    "writer_instructions": "...",
    "reader_instructions": "...",
}
```

### fallback 逻辑

如果 structured critic 的 JSON 解析失败，函数会返回一个保守的 fallback：

- `needs_revision = True`
- `needs_reader_revision = False`
- 要求 Writer 保守重写

这样做的好处是系统不会因为 Critic JSON 格式错误而完全中断。

## 15. Revision Workflow：revision_workflow.py

这是自动返工功能的控制层。

核心函数：

```python
run_critic_revision_loop(
    topic,
    ranked_papers,
    paper_cards,
    initial_survey,
    reading_mode="fast",
    max_pdf_pages=20,
    max_rounds=2,
)
```

### 内部流程

每一轮：

1. 调用 `critique_survey_structured`
2. 如果不需要修改，停止
3. 如果需要 Reader 返工：
   - 读取 `reader_paper_indexes`
   - 验证 index 合法性
   - 对指定论文重新调用 `generate_paper_card`
4. 调用 `revise_survey`
5. 记录这一轮返工信息

最后：

```python
final_critic_report = critique_survey(...)
```

返回给 app 展示。

### `_valid_paper_indexes`

这个小函数负责清洗 Critic 返回的 paper index：

- 转成 int
- 去掉非法值
- 去重
- 确保 index 在论文数量范围内

这是必要的，因为 LLM 返回的结构化结果也可能有错误。

### 当前限制

Reader 返工目前只是“重新读指定论文”，还没有把 Critic 的 `reader_instructions` 传进 Reader prompt。以后可以扩展 `generate_paper_card`，加入 `reader_feedback` 参数，让 Reader 更有针对性地补证据。

## 16. 关键数据结构

### Paper

来自 `search_arxiv.py`：

```python
{
    "paper_id": str,
    "title": str,
    "authors": list[str],
    "summary": str,
    "published": str,
    "arxiv_url": str,
    "pdf_url": str | None,
    "source_query": str,
}
```

Ranker 会追加：

```python
"relevance_score": int
"relevance_reason": str
```

### Paper Card

来自 `reader.py`：

```python
{
    "paper_id": str,
    "title": str,
    "authors": list[str],
    "published": str,
    "arxiv_url": str,
    "pdf_url": str | None,
    "reading_mode_used": str,
    "sections_found": list[str],
    "card": str,
    "evidence_items": list[dict],
}
```

### Evidence Item

来自 `evidence.py`：

```python
{
    "evidence_id": "P1-E1",
    "paper_index": 1,
    "paper_title": str,
    "section": str,
    "claim_type": str,
    "claim": str,
    "quote": str,
}
```

### Revision Result

来自 `revision_workflow.py`：

```python
{
    "survey": str,
    "paper_cards": list[dict],
    "critic_report": str,
    "rounds": list[dict],
    "revision_count": int,
    "reader_revision_count": int,
}
```

## 17. 现在最值得改的地方

### 17.1 抽出完整 workflow

现在 `app.py` 还直接串联研究流程。建议新增：

```text
scholar_agent/workflow.py
```

提供：

```python
run_research(
    topic: str,
    reading_mode: str,
    top_k: int,
    max_pdf_pages: int,
) -> dict
```

这样 Streamlit、FastAPI、命令行都可以复用同一个流程。

### 17.2 保存运行结果

建议每次运行保存：

```text
runs/
`-- 20260707_213000/
    |-- input.json
    |-- queries.json
    |-- papers.json
    |-- ranked_papers.json
    |-- paper_cards.json
    |-- comparison_rows.json
    |-- initial_survey.md
    |-- revision_rounds.json
    |-- final_survey.md
    `-- critic_report.md
```

这样可以复现、调试、展示。

### 17.3 加缓存

优先缓存：

- arXiv 搜索结果
- PDF 下载结果
- PDF section 抽取结果
- LLM 调用结果

缓存会节省时间和 token，也能让开发调试更舒服。

### 17.4 加 quote 验证

Evidence 可信性的下一步是验证：

```text
ev["quote"] 是否真的出现在 material 中
```

如果不出现，就删除该 evidence 或要求 LLM 重试。

### 17.5 前端准备

现在不需要马上创建 `frontend/`。正确的准备是：

- 保持 `scholar_agent/` 和 UI 解耦
- 把 workflow 封装成函数
- 以后用 FastAPI 暴露接口
- React / Next.js 前端只调用 API

推荐未来结构：

```text
scholar-agent/
|-- backend/
|   |-- api/
|   `-- scholar_agent/
|-- frontend/
|-- docs/
`-- README.md
```

## 18. 如果未来迁移到 LangGraph

当前代码已经很适合迁移，因为每个阶段都是清楚的函数。

可能的 LangGraph 节点：

```text
plan_queries
search_papers
rank_papers
read_papers
extract_evidence
compare_papers
write_survey
critic_review
revise_reader
revise_writer
```

状态对象可以包含：

```python
{
    "topic": str,
    "queries": list[str],
    "papers": list[dict],
    "ranked_papers": list[dict],
    "paper_cards": list[dict],
    "comparison_rows": list[dict],
    "survey": str,
    "critic_feedback": dict,
    "rounds": list[dict],
}
```

什么时候值得迁移：

- 需要断点恢复
- 需要人工审批节点
- 需要复杂条件分支
- 需要把每个 node 的状态持久化
- 需要后台任务队列

现在的轻量 `revision_workflow.py` 足够支撑原型，不必为了框架而提前迁移。

## 19. 常见问题定位

### 搜不到论文

优先看：

- `planner.py` 生成的 query 是否合理
- `search_arxiv.py` 是否请求失败
- arXiv API 是否临时不可用

### 搜到的论文不相关

优先看：

- `planner.py` prompt
- `ranker.py` prompt
- ranker 阈值是否太低

### deep mode 很慢

可能原因：

- PDF 下载慢
- PDF 页数太多
- 每篇论文都要 LLM 阅读和抽 evidence

优化方向：

- 降低 `max_pdf_pages`
- 加 PDF 缓存
- 并行读取论文

### 综述引用不存在的 evidence_id

优先看：

- `writer.py` prompt
- `critic.py` structured feedback 是否抓到了问题
- `revise_survey` 是否正确删除了无效引用

### evidence quote 不可靠

优先看：

- `evidence.py`
- 增加 quote 字符串匹配验证

## 20. 一个推荐的下一步开发顺序

1. 新增 `scholar_agent/workflow.py`，把 `app.py` 的主流程抽出来。
2. 新增 `runs/` 保存每次运行的完整产物。
3. 给 LLM 调用加日志和耗时统计。
4. 给 evidence quote 加真实性验证。
5. 加缓存。
6. 再考虑 FastAPI 或 LangGraph。

这个顺序的好处是：先让研究引擎稳定、可复现，再扩展 UI 和框架。
