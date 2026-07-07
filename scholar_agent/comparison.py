from scholar_agent.llm import call_llm_json


def generate_comparison_rows(paper_cards: list[dict]) -> list[dict]:
    cards_text = ""

    for idx, card in enumerate(paper_cards, start=1):
        cards_text += f"""
Paper Number: {idx}
Title: {card["title"]}
Card:
{card["card"]}
---
"""

    prompt = f"""
你是 Comparison Agent。

请基于以下论文阅读卡片，生成一个结构化对比表。

要求：
1. 只输出 JSON，不要输出 Markdown，不要解释。
2. 必须基于阅读卡片，不要编造。
3. 信息不足就写“未明确说明”。
4. 每篇论文生成一行。

输出格式必须是 JSON array：

[
  {{
    "id": 1,
    "paper": "论文标题",
    "method_category": "方法类别",
    "core_innovation": "核心创新",
    "techniques": "使用的技术",
    "evaluation": "评测方式",
    "strengths": "优点",
    "limitations": "局限性",
    "relation_to_topic": "和用户主题的关系"
  }}
]

论文阅读卡片：

{cards_text}
"""

    rows = call_llm_json(prompt)

    cleaned_rows = []

    for row in rows:
        cleaned_rows.append({
            "id": row.get("id", ""),
            "paper": row.get("paper", ""),
            "method_category": row.get("method_category", "未明确说明"),
            "core_innovation": row.get("core_innovation", "未明确说明"),
            "techniques": row.get("techniques", "未明确说明"),
            "evaluation": row.get("evaluation", "未明确说明"),
            "strengths": row.get("strengths", "未明确说明"),
            "limitations": row.get("limitations", "未明确说明"),
            "relation_to_topic": row.get("relation_to_topic", "未明确说明"),
        })

    return cleaned_rows