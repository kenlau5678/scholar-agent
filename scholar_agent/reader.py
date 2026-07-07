from scholar_agent.llm import call_llm
from scholar_agent.pdf_reader import fetch_pdf_sections, format_sections_for_llm
from scholar_agent.evidence import extract_evidence_items


def build_fast_material(paper: dict) -> tuple[str, str, list[str]]:
    material = f"""
论文标题：
{paper["title"]}

作者：
{", ".join(paper["authors"])}

摘要：
{paper["summary"]}
"""

    return material, "fast_abstract", ["title", "abstract"]


def build_deep_material(
    paper: dict,
    max_pdf_pages: int = 20,
) -> tuple[str, str, list[str]]:
    pdf_url = paper.get("pdf_url")

    if not pdf_url:
        material, _, sections_found = build_fast_material(paper)
        return material, "fast_fallback_no_pdf", sections_found

    try:
        sections = fetch_pdf_sections(
            pdf_url=pdf_url,
            max_pages=max_pdf_pages,
            max_chars_per_section=5000,
        )

        if not sections:
            material, _, sections_found = build_fast_material(paper)
            return material, "fast_fallback_no_sections", sections_found

        section_text = format_sections_for_llm(sections)

        material = f"""
论文标题：
{paper["title"]}

作者：
{", ".join(paper["authors"])}

arXiv 摘要：
{paper["summary"]}

PDF 分区正文：
{section_text}
"""

        return material, "deep_pdf_sections", list(sections.keys())

    except Exception as e:
        material, _, sections_found = build_fast_material(paper)
        return material, f"fast_fallback_pdf_error: {e}", sections_found


def generate_paper_card(
    paper: dict,
    paper_index: int,
    reading_mode: str = "fast",
    max_pdf_pages: int = 20,
) -> dict:
    if reading_mode == "deep":
        material, source_type, sections_found = build_deep_material(
            paper,
            max_pdf_pages=max_pdf_pages,
        )
    else:
        material, source_type, sections_found = build_fast_material(paper)

    prompt = f"""
你是 Paper Reader Agent。

请基于下面提供的论文材料，抽取结构化阅读卡片。

重要要求：
1. 只能根据给定材料回答。
2. 不要编造材料里没有的信息。
3. 如果信息不足，请写“材料中未明确说明”。
4. 输出中文。
5. 保持结构清晰。
6. 如果材料包含 PDF 分区正文，请优先参考 Method / Experiments / Results / Limitations / Conclusion。
7. 不要使用外部知识。
8. 对于“局限性”，如果论文没有明确写 limitations，可以基于材料谨慎归纳，但必须标注“根据材料推断”。

论文材料：
{material}

请按以下格式输出：

论文标题：
研究问题：
核心方法：
使用模型/数据集：
实验指标：
主要结论：
局限性：
可借鉴点：
"""

    card_text = call_llm(prompt)

    evidence_items = extract_evidence_items(
        paper_index=paper_index,
        paper=paper,
        card_text=card_text,
        material=material,
        max_evidence=6,
    )

    return {
        "paper_id": paper["paper_id"],
        "title": paper["title"],
        "authors": paper["authors"],
        "published": paper["published"],
        "arxiv_url": paper["arxiv_url"],
        "pdf_url": paper["pdf_url"],
        "reading_mode_used": source_type,
        "sections_found": sections_found,
        "card": card_text,
        "evidence_items": evidence_items,
    }


def generate_paper_cards(
    papers: list[dict],
    reading_mode: str = "fast",
    max_pdf_pages: int = 20,
) -> list[dict]:
    cards = []

    for idx, paper in enumerate(papers, start=1):
        card = generate_paper_card(
            paper,
            paper_index=idx,
            reading_mode=reading_mode,
            max_pdf_pages=max_pdf_pages,
        )
        cards.append(card)

    return cards