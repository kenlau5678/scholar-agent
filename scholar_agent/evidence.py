from scholar_agent.llm import call_llm_json


def extract_evidence_items(
    paper_index: int,
    paper: dict,
    card_text: str,
    material: str,
    max_evidence: int = 6,
) -> list[dict]:
    """
    从论文材料和阅读卡片中抽取可引用证据。
    evidence_id 示例：P1-E1, P1-E2
    """

    prompt = f"""
你是 Evidence Extraction Agent。

你的任务是从论文材料中抽取可以支撑综述写作的证据片段。

重要要求：
1. evidence quote 必须来自“论文材料”的原文。
2. 不要编造材料中不存在的 quote。
3. 每条 evidence 应该支持一个清晰 claim。
4. 优先抽取方法、实验、结果、局限性、数据集、评测指标相关证据。
5. 如果材料不足，请少输出，不要硬凑。
6. quote 尽量短，控制在 1-3 句话。
7. 输出 JSON，不要输出 Markdown。

论文编号：
P{paper_index}

论文标题：
{paper["title"]}

论文阅读卡片：
{card_text}

论文材料：
{material[:25000]}

请输出 JSON array，格式如下：

[
  {{
    "evidence_id": "P{paper_index}-E1",
    "paper_index": {paper_index},
    "paper_title": "论文标题",
    "section": "abstract/introduction/method/experiments/results/limitations/conclusion/unknown",
    "claim_type": "method/result/dataset/metric/limitation/background",
    "claim": "这条证据可以支持的中文结论",
    "quote": "来自论文材料的原文证据片段"
  }}
]

最多输出 {max_evidence} 条。
"""

    try:
        evidence_items = call_llm_json(prompt)
    except Exception:
        return []

    cleaned = []

    for i, item in enumerate(evidence_items[:max_evidence], start=1):
        evidence_id = item.get("evidence_id") or f"P{paper_index}-E{i}"

        cleaned.append({
            "evidence_id": evidence_id,
            "paper_index": paper_index,
            "paper_title": paper["title"],
            "section": item.get("section", "unknown"),
            "claim_type": item.get("claim_type", "unknown"),
            "claim": item.get("claim", ""),
            "quote": item.get("quote", ""),
        })

    return cleaned


def format_evidence_for_writer(paper_cards: list[dict]) -> str:
    """
    给 Survey Writer Agent 使用的证据材料。
    """

    output = ""

    for i, card in enumerate(paper_cards, start=1):
        output += f"\n\n## Paper {i}: {card['title']}\n"

        evidence_items = card.get("evidence_items", [])

        if not evidence_items:
            output += "No evidence extracted.\n"
            continue

        for ev in evidence_items:
            output += f"""
Evidence ID: {ev["evidence_id"]}
Section: {ev.get("section", "unknown")}
Claim Type: {ev.get("claim_type", "unknown")}
Supported Claim: {ev.get("claim", "")}
Quote: {ev.get("quote", "")}
---
"""

    return output.strip()