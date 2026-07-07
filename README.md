# ScholarAgent

ScholarAgent is a Streamlit-based literature research assistant for evidence-grounded survey generation. It plans search queries, retrieves arXiv papers, ranks candidates with an LLM, reads abstracts or PDFs, extracts evidence snippets, writes a Chinese technical survey, and runs a Critic Agent that can automatically trigger Reader / Writer revisions.

## Features

- Research query planning from a user topic
- arXiv paper search and deduplication
- LLM-based relevance ranking
- Fast reading mode using title and abstract
- Deep reading mode using PDF section extraction
- Structured paper reading cards
- Evidence extraction with `evidence_id` citations
- Cross-paper comparison table
- Evidence-based survey writing
- Critic-driven revision loop:
  - audits unsupported claims and invalid evidence citations
  - optionally re-reads selected papers
  - rewrites the survey based on structured critic feedback

## Project Structure

```text
scholar-agent/
├── app.py
├── requirements.txt
├── .env.example
└── scholar_agent/
    ├── config.py
    ├── llm.py
    ├── planner.py
    ├── search_arxiv.py
    ├── ranker.py
    ├── pdf_reader.py
    ├── reader.py
    ├── evidence.py
    ├── comparison.py
    ├── writer.py
    ├── critic.py
    └── revision_workflow.py
```

## Workflow

```text
Topic
  -> Research Planner
  -> arXiv Search
  -> Relevance Ranking
  -> Paper Reader
  -> Evidence Extraction
  -> Comparison Agent
  -> Survey Writer
  -> Critic Agent
  -> optional Reader / Writer revision loop
  -> final survey and critic report
```

## Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create a local environment file:

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4.1-mini
```

## Run

```powershell
streamlit run app.py
```

Then open the local URL shown by Streamlit, usually:

```text
http://localhost:8501
```

## Configuration

The app supports two reading modes:

- Fast mode: uses paper titles and abstracts only.
- Deep mode: downloads and parses PDFs, then extracts important sections such as Introduction, Method, Experiments, Results, Limitations, and Conclusion.

The automatic revision loop currently runs up to 2 rounds. It is implemented in `scholar_agent/revision_workflow.py`.

## Notes

- `.env` is ignored by git and should not be committed.
- arXiv PDF parsing quality depends on the paper PDF format.
- The Critic Agent can improve citation discipline, but generated surveys should still be reviewed before serious academic use.

## Roadmap

- Add persistent run logs
- Cache arXiv and PDF results
- Add export formats for Markdown / DOCX
- Add human approval before revision
- Migrate the revision workflow to LangGraph when state persistence, branching, and resume support become necessary
