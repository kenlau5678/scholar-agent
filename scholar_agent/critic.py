from scholar_agent.llm import call_llm, call_llm_json
from scholar_agent.evidence import format_evidence_for_writer


def critique_survey(topic: str, paper_cards: list[dict], survey: str) -> str:
    cards_text = ""

    for idx, card in enumerate(paper_cards, start=1):
        cards_text += f"""
[{idx}] {card["title"]}
{card["card"]}
---
"""

    evidence_text = format_evidence_for_writer(paper_cards)

    prompt = f"""
你是 Critic Agent，负责检查科研综述的可信性和引用正确性。

研究主题：
{topic}

可用论文阅读卡片：
{cards_text}

可用 evidence：
{evidence_text}

待检查综述：
{survey}

请严格检查以下问题：

1. 综述是否引用了不存在的 evidence_id？
2. 每个关键结论是否都有 evidence_id 支撑？
3. evidence quote 是否真的能支持对应结论？
4. 是否存在把证据过度推广的问题？
5. 是否存在把论文没有说的内容写进综述的问题？
6. 是否有明显不相关论文被作为核心依据？
7. 哪些段落需要删除、弱化或补充引用？

输出格式：

## Critic Agent 审查结果

### 总体判断
可信 / 部分可信 / 不可信

### 引用完整性检查
- ...

### 证据支持性检查
- ...

### 可能的幻觉或过度概括
- ...

### 建议修改
- ...

### 可以保留的结论
- ...
"""

    return call_llm(prompt)


def critique_survey_structured(
    topic: str,
    paper_cards: list[dict],
    survey: str,
) -> dict:
    cards_text = ""

    for idx, card in enumerate(paper_cards, start=1):
        cards_text += f"""
Paper Index: {idx}
Title: {card["title"]}
Card:
{card["card"]}
---
"""

    evidence_text = format_evidence_for_writer(paper_cards)

    prompt = f"""
You are a strict Critic Agent for an evidence-based literature survey.

Research topic:
{topic}

Available paper cards:
{cards_text}

Available evidence:
{evidence_text}

Survey to audit:
{survey}

Decide whether the survey must be revised. Check:
- nonexistent evidence_id citations
- key claims without evidence_id support
- claims that overstate the evidence
- claims not supported by the paper cards
- missing or weak evidence that requires re-reading one or more papers

Return JSON only, with this schema:
{{
  "overall_judgment": "credible|partly_credible|not_credible",
  "needs_revision": true,
  "needs_reader_revision": false,
  "reader_paper_indexes": [1, 3],
  "issues": [
    {{
      "severity": "high|medium|low",
      "issue_type": "missing_citation|invalid_evidence_id|unsupported_claim|overgeneralization|weak_evidence|irrelevant_paper|structure",
      "location": "section or sentence if clear",
      "problem": "concise problem description",
      "fix": "concrete revision instruction"
    }}
  ],
  "writer_instructions": "specific instructions for rewriting the survey",
  "reader_instructions": "specific instructions for re-reading papers, or empty string"
}}

Use needs_reader_revision=true only when the existing paper card/evidence is insufficient and
the Reader Agent should re-read the original paper material. Keep reader_paper_indexes limited
to the paper indexes shown above.
"""

    try:
        result = call_llm_json(prompt, temperature=0.0)
    except Exception as exc:
        return {
            "overall_judgment": "partly_credible",
            "needs_revision": True,
            "needs_reader_revision": False,
            "reader_paper_indexes": [],
            "issues": [
                {
                    "severity": "medium",
                    "issue_type": "structure",
                    "location": "critic",
                    "problem": f"Structured critic failed: {exc}",
                    "fix": "Run a conservative writer revision using the markdown critic report.",
                }
            ],
            "writer_instructions": "Revise conservatively. Remove unsupported claims and ensure every key claim cites an existing evidence_id.",
            "reader_instructions": "",
        }

    result.setdefault("overall_judgment", "partly_credible")
    result.setdefault("needs_revision", True)
    result.setdefault("needs_reader_revision", False)
    result.setdefault("reader_paper_indexes", [])
    result.setdefault("issues", [])
    result.setdefault("writer_instructions", "")
    result.setdefault("reader_instructions", "")

    return result
