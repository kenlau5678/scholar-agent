from openai import OpenAI
from scholar_agent.config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
import json
import re

client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
)


def call_llm(prompt: str, temperature: float = 0.2) -> str:
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a rigorous research assistant. "
                    "Always be precise, structured, and citation-aware."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=temperature,
    )

    return response.choices[0].message.content


def call_llm_json(prompt: str, temperature: float = 0.1):
    text = call_llm(prompt, temperature=temperature)

    # 去掉 ```json ... ``` 代码块
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise ValueError(f"LLM did not return valid JSON:\n{text}")