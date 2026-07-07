from scholar_agent.llm import call_llm_json


def llm_rank_papers(topic: str, papers: list[dict], top_k: int = 8) -> list[dict]:
    """
    用 LLM 判断论文和研究主题的相关性。
    score:
    5 = 高度相关，核心论文
    4 = 明显相关
    3 = 部分相关
    2 = 弱相关
    1 = 基本不相关
    0 = 完全不相关
    """

    paper_text = ""

    for i, paper in enumerate(papers):
        paper_text += f"""
Paper Index: {i}
Title: {paper["title"]}
Abstract: {paper["summary"][:1200]}
Source Query: {paper.get("source_query", "")}
---
"""

    prompt = f"""
你是 Paper Relevance Ranking Agent。

用户的研究主题是：

{topic}

下面是从 arXiv 检索到的候选论文。请判断每篇论文与研究主题的相关性。

评分规则：
5 = 高度相关，直接研究该主题
4 = 明显相关，可以作为主要参考论文
3 = 部分相关，可作为背景或补充
2 = 弱相关，不建议进入核心综述
1 = 基本不相关
0 = 完全不相关

特别注意：
- 如果论文只是名字里有 RAG，但研究对象是图像生成、医学 EHR、气候、遥感等，通常不应给高分。
- 本主题关注的是：RAG、LLM hallucination、factuality、grounded generation、citation verification、hallucination detection、hallucination mitigation。
- 不要因为标题里有 hallucination 就直接高分，要看是否和 LLM / RAG 相关。

候选论文：

{paper_text}

请只输出 JSON，不要解释。格式如下：

[
  {{
    "paper_index": 0,
    "score": 5,
    "reason": "直接研究 RAG 中的幻觉检测"
  }}
]
"""

    results = call_llm_json(prompt)

    scored = []

    for item in results:
        idx = item["paper_index"]
        if 0 <= idx < len(papers):
            paper = papers[idx].copy()
            paper["relevance_score"] = item.get("score", 0)
            paper["relevance_reason"] = item.get("reason", "")
            scored.append(paper)

    scored.sort(key=lambda x: x["relevance_score"], reverse=True)

    # 只保留 3 分以上的论文
    filtered = [p for p in scored if p["relevance_score"] >= 3]

    return filtered[:top_k]