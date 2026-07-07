from scholar_agent.llm import call_llm
from scholar_agent.evidence import format_evidence_for_writer


def generate_survey(topic: str, paper_cards: list[dict]) -> str:
    cards_text = ""

    for idx, card in enumerate(paper_cards, start=1):
        cards_text += f"""
[{idx}] {card["title"]}
arXiv: {card["arxiv_url"]}

{card["card"]}

---
"""

    evidence_text = format_evidence_for_writer(paper_cards)

    prompt = f"""
你是 Survey Writer Agent。

你需要基于论文阅读卡片和证据片段，生成一份中文技术综述。

研究主题：
{topic}

论文阅读卡片：
{cards_text}

可引用证据片段：
{evidence_text}

强制要求：
1. 综述中的关键技术判断、方法描述、实验结论、局限性判断，都必须引用 evidence_id。
2. 引用格式必须使用 evidence_id，例如 [P1-E2]、[P3-E1]。
3. 不要使用普通 [1]、[2] 作为正文引用。
4. 如果某个结论没有 evidence 支持，请不要写成确定结论，可以写成“材料中尚不足以判断”。
5. 不要引用不存在的 evidence_id。
6. 不要编造论文没有支持的内容。
7. 综述必须包含：
   - 研究背景
   - 问题拆解
   - 方法分类
   - 代表性论文对比
   - 当前方法不足
   - 后续可研究方向
   - Evidence-based References

输出格式：

# 题目

## 研究背景

## 问题拆解

## 方法分类

## 代表性论文对比

## 当前方法不足

## 后续可研究方向

## Evidence-based References

在 Evidence-based References 中，按如下格式列出：

[P1-E1] 论文标题。证据：quote。arXiv: url
"""

    return call_llm(prompt)


def revise_survey(
    topic: str,
    paper_cards: list[dict],
    survey: str,
    critic_feedback: dict,
) -> str:
    cards_text = ""

    for idx, card in enumerate(paper_cards, start=1):
        cards_text += f"""
[{idx}] {card["title"]}
arXiv: {card["arxiv_url"]}

{card["card"]}

---
"""

    evidence_text = format_evidence_for_writer(paper_cards)

    prompt = f"""
You are Survey Writer Agent. Rewrite the Chinese technical survey according to
the Critic Agent feedback.

Research topic:
{topic}

Available paper cards:
{cards_text}

Available evidence:
{evidence_text}

Current survey:
{survey}

Critic feedback:
{critic_feedback}

Mandatory revision rules:
1. Keep the output in Chinese.
2. Only use facts supported by the paper cards and evidence.
3. Every important method, result, limitation, and comparison claim must cite an existing evidence_id such as [P1-E2].
4. Remove nonexistent evidence_id citations.
5. If a claim is not supported, delete it or weaken it explicitly.
6. Do not invent new evidence_id values.
7. Preserve this structure:

# Title

## Research Background

## Problem Decomposition

## Method Taxonomy

## Representative Paper Comparison

## Current Limitations

## Future Research Directions

## Evidence-based References

In Evidence-based References, list only evidence_id values that actually appear in the available evidence.
Return the revised survey only. Do not include an explanation of the revision process.
"""

    return call_llm(prompt, temperature=0.1)
