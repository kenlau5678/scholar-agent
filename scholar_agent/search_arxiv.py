import requests
import feedparser
from urllib.parse import quote


def search_arxiv(query: str, max_results: int = 5) -> list[dict]:
    encoded_query = quote(query)

    url = (
        "http://export.arxiv.org/api/query?"
        f"search_query=all:{encoded_query}"
        f"&start=0"
        f"&max_results={max_results}"
        f"&sortBy=relevance"
        f"&sortOrder=descending"
    )

    response = requests.get(url, timeout=20)
    response.raise_for_status()

    feed = feedparser.parse(response.text)

    papers = []

    for entry in feed.entries:
        paper_id = entry.id.split("/abs/")[-1]

        pdf_url = None
        for link in entry.links:
            if link.get("type") == "application/pdf":
                pdf_url = link.get("href")

        papers.append({
            "paper_id": paper_id,
            "title": entry.title.replace("\n", " ").strip(),
            "authors": [author.name for author in entry.authors],
            "summary": entry.summary.replace("\n", " ").strip(),
            "published": entry.published,
            "arxiv_url": entry.id,
            "pdf_url": pdf_url,
            "source_query": query,
        })

    return papers


def search_papers_by_queries(queries: list[str], max_per_query: int = 5) -> list[dict]:
    all_papers = []
    seen_ids = set()

    for query in queries:
        try:
            papers = search_arxiv(query, max_results=max_per_query)
            for paper in papers:
                if paper["paper_id"] not in seen_ids:
                    seen_ids.add(paper["paper_id"])
                    all_papers.append(paper)
        except Exception as e:
            print(f"Search failed for query: {query}, error: {e}")

    return all_papers