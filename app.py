import streamlit as st
import pandas as pd
from datetime import datetime
import re
import textwrap

from scholar_agent.planner import generate_queries
from scholar_agent.search_arxiv import search_papers_by_queries
from scholar_agent.ranker import llm_rank_papers
from scholar_agent.reader import generate_paper_cards
from scholar_agent.comparison import generate_comparison_rows
from scholar_agent.writer import generate_survey
from scholar_agent.revision_workflow import run_critic_revision_loop


def safe_filename(text: str, max_length: int = 40) -> str:
    text = re.sub(r"[\\/:*?\"<>|]", "_", text)
    text = re.sub(r"\s+", "_", text)
    text = text.strip("_")

    if not text:
        text = "survey_report"

    return text[:max_length]


def explain_reading_mode(mode: str) -> str:
    if mode == "fast_abstract":
        return "快速模式：标题 + 摘要"
    if mode == "deep_pdf_sections":
        return "深入模式：PDF 分区阅读"
    if mode == "fast_fallback_no_pdf":
        return "回退模式：没有 PDF，使用摘要"
    if mode == "fast_fallback_no_sections":
        return "回退模式：未识别出论文 Section，使用摘要"
    if mode.startswith("fast_fallback_pdf_error"):
        return "回退模式：PDF 解析失败，使用摘要"

    return mode


def explain_sections(sections: list[str]) -> str:
    if not sections:
        return ""

    if "fallback_pdf_text" in sections:
        return "未成功识别论文 Section，已使用 PDF 正文节选"

    section_name_map = {
        "abstract": "Abstract",
        "introduction": "Introduction",
        "related_work": "Related Work",
        "method": "Method",
        "experiments": "Experiments",
        "results": "Results",
        "limitations": "Limitations",
        "conclusion": "Conclusion",
    }

    readable_sections = [
        section_name_map.get(section, section)
        for section in sections
    ]

    return ", ".join(readable_sections)


st.set_page_config(
    page_title="ScholarAgent",
    page_icon="📚",
    layout="wide",
)

st.title("📚 ScholarAgent")
st.caption("A Multi-Agent Literature Research System for Trustworthy Survey Generation")

topic = st.text_area(
    "请输入研究主题",
    value="请调研 RAG 中降低大模型幻觉的方法，并生成一份带引用的技术综述。",
    height=100,
)

reading_mode = st.radio(
    "论文阅读模式",
    options=["fast", "deep"],
    format_func=lambda x: "快速模式：只读标题 + 摘要" if x == "fast" else "深入模式：下载并解析 PDF",
    horizontal=True,
)

if reading_mode == "deep":
    max_pdf_pages = st.slider(
        "深入模式：每篇论文最多读取 PDF 页数",
        min_value=5,
        max_value=30,
        value=20,
    )
else:
    max_pdf_pages = 0

top_k = st.slider(
    "筛选论文数量",
    min_value=3,
    max_value=12,
    value=8,
)

if st.button("开始调研", type="primary"):
    if not topic.strip():
        st.warning("请输入研究主题")
        st.stop()

    with st.spinner("Research Planner Agent 正在生成检索 query..."):
        queries = generate_queries(topic)

    st.subheader("1. 自动生成的检索 Query")
    for q in queries:
        st.write("- " + q)

    with st.spinner("Paper Search Agent 正在检索 arXiv 论文..."):
        papers = search_papers_by_queries(
            queries,
            max_per_query=5,
        )

    st.subheader("2. 检索到的候选论文")
    st.write(f"共检索到 {len(papers)} 篇候选论文")

    if not papers:
        st.error("没有检索到论文，请换一个研究主题。")
        st.stop()

    with st.spinner("Relevance Ranking Agent 正在筛选高相关论文..."):
        ranked_papers = llm_rank_papers(
            topic,
            papers,
            top_k=top_k,
        )

    if not ranked_papers:
        st.error("没有筛选到足够相关的论文，请换一个更具体的研究主题。")
        st.stop()

    paper_table = pd.DataFrame([
        {
            "Title": p["title"],
            "Published": p["published"],
            "Score": p["relevance_score"],
            "Reason": p.get("relevance_reason", ""),
            "URL": p["arxiv_url"],
        }
        for p in ranked_papers
    ])

    st.dataframe(
        paper_table,
        use_container_width=True,
    )

    with st.spinner("Paper Reader Agent 正在生成论文阅读卡片..."):
        paper_cards = generate_paper_cards(
            ranked_papers,
            reading_mode=reading_mode,
            max_pdf_pages=max_pdf_pages,
        )

    st.subheader("3. 论文结构化阅读卡片")

    for i, card in enumerate(paper_cards, start=1):
        with st.expander(f"[{i}] {card['title']}"):
            st.caption(
                "实际阅读模式："
                + explain_reading_mode(
                    card.get("reading_mode_used", "unknown")
                )
            )

            sections_found = card.get("sections_found", [])
            section_text = explain_sections(sections_found)

            if section_text:
                st.caption("识别到的论文 Section：" + section_text)

            st.markdown(card["card"])
            st.write(card["arxiv_url"])

    evidence_rows = []

    for card in paper_cards:
        for ev in card.get("evidence_items", []):
            evidence_rows.append({
                "Evidence ID": ev.get("evidence_id", ""),
                "Paper": ev.get("paper_title", ""),
                "Section": ev.get("section", ""),
                "Claim Type": ev.get("claim_type", ""),
                "Supported Claim": ev.get("claim", ""),
                "Quote": ev.get("quote", ""),
            })

    st.subheader("4. Evidence 证据片段表")

    if evidence_rows:
        evidence_df = pd.DataFrame(evidence_rows)
        st.dataframe(
            evidence_df,
            use_container_width=True,
        )
    else:
        evidence_df = pd.DataFrame()
        st.warning("没有抽取到 evidence，后续综述可能可信度较低。")

    with st.spinner("Comparison Agent 正在生成论文横向对比表..."):
        comparison_rows = generate_comparison_rows(paper_cards)

    comparison_df = pd.DataFrame(comparison_rows)

    comparison_df = comparison_df.rename(columns={
        "id": "编号",
        "paper": "论文",
        "method_category": "方法类别",
        "core_innovation": "核心创新",
        "techniques": "使用技术",
        "evaluation": "评测方式",
        "strengths": "优点",
        "limitations": "局限性",
        "relation_to_topic": "与主题关系",
    })

    st.subheader("5. 多论文横向对比")
    st.dataframe(
        comparison_df,
        use_container_width=True,
    )

    with st.spinner("Survey Writer Agent 正在生成综述报告..."):
        initial_survey = generate_survey(
            topic,
            paper_cards,
        )

    with st.spinner("Critic Agent 正在审查，并自动触发 Reader / Writer 返工..."):
        revision_result = run_critic_revision_loop(
            topic=topic,
            ranked_papers=ranked_papers,
            paper_cards=paper_cards,
            initial_survey=initial_survey,
            reading_mode=reading_mode,
            max_pdf_pages=max_pdf_pages,
            max_rounds=2,
        )

    survey = revision_result["survey"]
    paper_cards = revision_result["paper_cards"]
    critic_report = revision_result["critic_report"]

    st.subheader("6. Evidence-based 调研综述")

    if revision_result["revision_count"]:
        st.success(
            f"Critic Agent 已自动触发 {revision_result['revision_count']} 次 Writer 返工，"
            f"Reader 补读 {revision_result['reader_revision_count']} 篇论文。"
        )
    else:
        st.info("Critic Agent 未发现需要自动返工的高风险问题。")

    st.markdown(survey)

    survey_report = textwrap.dedent(f"""
    # ScholarAgent Evidence-based Survey Report

    ## 研究主题

    {topic}

    ## 论文阅读模式

    {"快速模式：标题 + 摘要" if reading_mode == "fast" else "深入模式：PDF 全文解析"}

    ---

    {survey}
    """).strip()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = safe_filename(topic)

    st.download_button(
        label="下载综述报告 Markdown",
        data=survey_report,
        file_name=f"{filename}_{timestamp}.md",
        mime="text/markdown",
    )

    st.subheader("7. Critic Agent 可信性审查")
    st.markdown(critic_report)
