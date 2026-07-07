import re
import tempfile
from pathlib import Path

import fitz
import requests


SECTION_ALIASES = {
    "abstract": [
        "abstract"
    ],
    "introduction": [
        "introduction",
        "intro"
    ],
    "related_work": [
        "related work",
        "background",
        "preliminaries"
    ],
    "method": [
        "method",
        "methods",
        "methodology",
        "approach",
        "proposed method",
        "framework",
        "model",
        "system"
    ],
    "experiments": [
        "experiment",
        "experiments",
        "experimental setup",
        "evaluation",
        "implementation details"
    ],
    "results": [
        "result",
        "results",
        "analysis",
        "discussion"
    ],
    "limitations": [
        "limitation",
        "limitations",
        "limitations and future work"
    ],
    "conclusion": [
        "conclusion",
        "conclusions",
        "future work"
    ],
    "references": [
        "references",
        "bibliography"
    ],
}


def download_pdf(pdf_url: str) -> Path:
    headers = {
        "User-Agent": "ScholarAgent/0.1"
    }

    response = requests.get(
        pdf_url,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    tmp_dir = Path(tempfile.gettempdir()) / "scholar_agent_pdfs"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    filename = pdf_url.split("/")[-1].replace(".pdf", "") + ".pdf"
    pdf_path = tmp_dir / filename

    with open(pdf_path, "wb") as f:
        f.write(response.content)

    return pdf_path


def clean_pdf_text(text: str) -> str:
    text = text.replace("\x00", " ")

    # 处理 PDF 常见断词
    text = re.sub(r"-\n", "", text)

    # 保留换行，因为 Section 标题通常依赖换行识别
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def extract_text_from_pdf(pdf_path: Path, max_pages: int = 20) -> str:
    doc = fitz.open(pdf_path)

    pages_text = []

    for page_index, page in enumerate(doc):
        if page_index >= max_pages:
            break

        text = page.get_text("text")
        pages_text.append(text)

    doc.close()

    full_text = "\n".join(pages_text)
    return clean_pdf_text(full_text)


def canonical_section_name(raw_title: str) -> str | None:
    title = raw_title.lower().strip()

    # 去掉编号，比如 "1 Introduction" / "2.1 Method"
    title = re.sub(r"^\d+(\.\d+)*\s*", "", title)
    title = re.sub(r"[^a-zA-Z ]", "", title)
    title = re.sub(r"\s+", " ", title).strip()

    for canonical, aliases in SECTION_ALIASES.items():
        for alias in aliases:
            if title == alias:
                return canonical

    return None


def find_section_headings(text: str) -> list[dict]:
    """
    尝试识别 PDF 中的 section heading。
    适合 arXiv 论文常见格式：
    Abstract
    1 Introduction
    2 Related Work
    3 Method
    4 Experiments
    """
    headings = []

    lines = text.splitlines()
    cursor = 0

    for line in lines:
        raw_line = line.strip()
        line_start = cursor
        cursor += len(line) + 1

        if not raw_line:
            continue

        # 太长的一般不是标题
        if len(raw_line) > 80:
            continue

        # 标题候选：可带数字编号
        # examples:
        # Abstract
        # 1 Introduction
        # 2.1 Retrieval-Augmented Generation
        match = re.match(
            r"^(\d+(\.\d+)*\s+)?([A-Za-z][A-Za-z\s\-&]+)$",
            raw_line
        )

        if not match:
            continue

        section_name = canonical_section_name(raw_line)

        if section_name:
            headings.append({
                "name": section_name,
                "raw_title": raw_line,
                "start": line_start,
            })

    # 按出现位置排序
    headings.sort(key=lambda x: x["start"])

    return headings


def extract_sections(text: str, max_chars_per_section: int = 5000) -> dict:
    headings = find_section_headings(text)

    if not headings:
        return {}

    sections = {}

    for i, heading in enumerate(headings):
        name = heading["name"]

        # references 后面的内容通常不适合给阅读 Agent
        if name == "references":
            continue

        start = heading["start"]

        if i + 1 < len(headings):
            end = headings[i + 1]["start"]
        else:
            end = len(text)

        content = text[start:end].strip()

        # 太短的 section 没有价值
        if len(content) < 200:
            continue

        content = content[:max_chars_per_section]

        # 同类 section 只保留第一次出现的主 section
        if name not in sections:
            sections[name] = content

    return sections


def fallback_select_relevant_text(text: str, max_chars: int = 20000) -> str:
    """
    如果 section 识别失败，就回退到旧策略：
    读取开头 + method / experiment / conclusion 附近内容。
    """
    if len(text) <= max_chars:
        return text

    head = text[:10000]

    keywords = [
        "method",
        "approach",
        "experiment",
        "evaluation",
        "result",
        "limitation",
        "conclusion",
    ]

    extra_parts = []
    lower_text = text.lower()

    for keyword in keywords:
        idx = lower_text.find(keyword)
        if idx != -1:
            start = max(0, idx - 1000)
            end = min(len(text), idx + 2500)
            extra_parts.append(text[start:end])

    selected = head + "\n\n" + "\n\n".join(extra_parts)

    return selected[:max_chars]


def fetch_pdf_sections(
    pdf_url: str,
    max_pages: int = 20,
    max_chars_per_section: int = 5000,
) -> dict:
    pdf_path = download_pdf(pdf_url)
    text = extract_text_from_pdf(pdf_path, max_pages=max_pages)

    sections = extract_sections(
        text,
        max_chars_per_section=max_chars_per_section,
    )

    if sections:
        return sections

    # section 识别失败时，返回 fallback
    fallback_text = fallback_select_relevant_text(text)

    return {
        "fallback_pdf_text": fallback_text
    }


def format_sections_for_llm(sections: dict) -> str:
    preferred_order = [
        "abstract",
        "introduction",
        "related_work",
        "method",
        "experiments",
        "results",
        "limitations",
        "conclusion",
        "fallback_pdf_text",
    ]

    output = ""

    for section_name in preferred_order:
        if section_name in sections:
            output += f"\n\n## {section_name}\n\n{sections[section_name]}"

    return output.strip()