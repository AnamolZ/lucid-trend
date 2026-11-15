import json
from typing import Optional, Dict
import requests

from config.settings import OPENROUTER_API_KEY, OPENROUTER_MODEL


class NewsSynthesizer:
    def __init__(self, api_key: str = OPENROUTER_API_KEY, model: str = OPENROUTER_MODEL):
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://openrouter.ai/api/v1/chat/completions"

    def synthesize(self, combined_text: str) -> Optional[Dict]:
        if not self.api_key:
            print("[AI] Error: Missing OPENROUTER_API_KEY in configuration.")
            return None

        prompt = f"""
You are an elite, objective financial, tech, and macroeconomic news editor.
You have been provided with raw information and text extracted from multiple Instagram news feeds.

Raw Extracted Intel:
{combined_text}

Strict Editorial Rules:
1. Filter out all social media noise, conversational banter, emojis, and meme commentary.
2. NEVER explain or treat memes, jokes, or engagement bait as news. If an image contains a factual event, financial statistic, or regulatory action, extract ONLY that hard fact.
3. Group distinct events into separate news items inside "news_items".
4. Top-level "headline" and "executive_summary" must synthesize the major macroeconomic/market narrative tying the key stories together.
5. Top-level "facts" must be an array of pure, high-impact quantifiable bullet points (each starting with "• ") capturing the key verifiable metrics, statistics, and figures across the news. Do NOT include sub-headlines, conversational prose, or headers in "facts".
6. For EACH news item in "news_items":
   - "headline": Punchy, professional news headline for that specific story.
   - "category": Clean category (e.g., "Tech & Equities", "Cryptocurrency", "Macro & Infrastructure").
   - "key_points": Cohesive, narrative context explaining what happened, historical context, and impacts (each starting with "• ").

Output Format:
You MUST respond with a strictly valid JSON object matching this schema exactly (no markdown codeblocks, no commentary, no extra top-level keys):
{{
  "headline": "Main multi-market headline summarizing key developments",
  "executive_summary": "Synthesized executive paragraph detailing major stories and market context...",
  "facts": [
    "• Hard quantifiable stat or record metric.",
    "• Specific financial value, percentage drawdown, or funding request."
  ],
  "news_items": [
    {{
      "headline": "Individual story headline",
      "category": "Tech & Equities",
      "key_points": [
        "• Narrative bullet 1 explaining what occurred.",
        "• Narrative bullet 2 providing context and follow-up."
      ]
    }}
  ]
}}
"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }

        try:
            resp = requests.post(self.endpoint, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()

            if content.startswith("```"):
                lines = content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                content = "\n".join(lines).strip()

            return json.loads(content)
        except Exception as e:
            print(f"[AI] Synthesis error: {e}")
            return None
