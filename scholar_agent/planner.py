from scholar_agent.llm import call_llm

def generate_queries(topic: str) -> list[str]:
    prompt = f"""
你是 Research Planner Agent。

用户研究主题是：

{topic}

请把这个研究主题拆解成 5-8 个英文论文检索 query。

要求：
1. query 要适合 arXiv / Semantic Scholar 检索
2. 每个 query 聚焦一个子方向
3. 不要解释
4. 只输出一行一个 query
5. query 尽量使用英文关键词

示例：
retrieval augmented generation hallucination mitigation
RAG factual consistency evaluation
citation grounded generation large language models
"""

    result = call_llm(prompt)

    queries = []
    for line in result.splitlines():
        line = line.strip("- ").strip()
        if line:
            queries.append(line)

    return queries[:8]