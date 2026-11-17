import json
import logging
from typing import Optional, Dict
import requests

from config.settings import OPENROUTER_API_KEY, OPENROUTER_MODEL
from service.image_helper.get_image import CloudflareAccountCoordinator

logger = logging.getLogger("NewsSynthesizer")


class NewsSynthesizer:
    def __init__(self, api_key: str = OPENROUTER_API_KEY, model: str = OPENROUTER_MODEL):
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://openrouter.ai/api/v1/chat/completions"
        self.cf_coordinator = CloudflareAccountCoordinator()

    def synthesize(self, combined_text: str) -> Optional[Dict]:
        prompt = f"""
You are an elite, objective financial, tech, and macroeconomic news editor.
You have been provided with raw information and text extracted from multiple market and social intel feeds.

Raw Extracted Intel:
{combined_text}

Strict Editorial Rules:
1. Filter out all social media noise, conversational banter, emojis, and meme commentary.
2. If an item contains a factual event, financial statistic, or regulatory action, extract ONLY that hard fact.
3. Group distinct events into separate news items inside "news_items".
4. Top-level "headline" and "executive_summary" must synthesize the major macroeconomic/market narrative tying the key stories together.
5. Top-level "facts" must be an array of pure, high-impact quantifiable bullet points (each starting with "• ") capturing the key verifiable metrics across the news.
6. For EACH news item in "news_items":
   - "headline": Punchy, professional news headline for that specific story.
   - "category": Clean category (e.g., "Tech & Equities", "Cryptocurrency", "Macro & Infrastructure").
   - "facts": Array of 2-3 quantifiable, story-specific facts or metrics (each starting with "• ") relevant specifically to this story (e.g. percentages, prices, funding, record stats). Do NOT include generic headers or fluff.
   - "key_points": Cohesive, narrative context explaining what happened (each starting with "• ").
7. Top-level "significance_score": An integer from 1 to 10 rating the market and historical importance of this batch:
   - 1-6: Minor market noise, routine price twitches (<1.5%), social media banter, or repetitive updates.
   - 7-10: Major market developments, monetary policy decisions, severe liquidations (>3%), breakthrough tech, or geopolitical actions.

Output Format:
You MUST respond with a strictly valid JSON object matching this schema exactly (no markdown codeblocks, no commentary, no extra top-level keys):
{{
  "headline": "Main multi-market headline summarizing key developments",
  "significance_score": 8,
  "executive_summary": "Synthesized executive paragraph detailing major stories and market context...",
  "facts": [
    "• Hard quantifiable stat or record metric.",
    "• Specific financial value, percentage drawdown, or funding request."
  ],
  "news_items": [
    {{
      "headline": "Individual story headline",
      "category": "Tech & Equities",
      "facts": [
        "• Specific number or metric for this story.",
        "• Hard financial stat or milestone for this story."
      ],
      "key_points": [
        "• Narrative bullet 1 explaining what occurred.",
        "• Narrative bullet 2 providing context and follow-up."
      ]
    }}
  ]
}}
"""

        # 1. Primary Strategy: OpenRouter (if API key provided)
        if self.api_key:
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                }
                resp = requests.post(self.endpoint, headers=headers, json=payload, timeout=60)
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"].strip()
                    parsed = self._clean_and_parse_json(content)
                    if parsed:
                        return parsed
            except Exception as e:
                logger.warning(f"[NewsSynthesizer] OpenRouter attempt failed: {e}. Falling back...")

        # 2. Resilient Strategy: Google Gemini Key Pool (High speed, Free, Structured Output)
        try:
            import google.generativeai as genai
            from config.model_pool import coordinator

            total_keys = len(coordinator.raw_keys) if hasattr(coordinator, "raw_keys") else 1
            for key_round in range(max(1, total_keys)):
                active_key = coordinator.get_active_key()
                if not active_key:
                    break
                genai.configure(api_key=active_key)

                for model_name in ["models/gemini-flash-lite-latest", "models/gemini-flash-latest", "models/gemini-2.5-flash"]:
                    try:
                        g_model = genai.GenerativeModel(model_name)
                        response = g_model.generate_content(prompt)
                        if response and response.text:
                            parsed = self._clean_and_parse_json(response.text)
                            if parsed and parsed.get("headline"):
                                print(f"[NewsSynthesizer] Successfully synthesized news via Google Gemini ({model_name}) on Key #{key_round + 1}!")
                                return parsed
                    except Exception as gem_err:
                        logger.warning(f"[NewsSynthesizer] Gemini key #{key_round + 1} ({model_name}) error: {gem_err}")
                        continue

                # Advance to next Google key if all models on this key hit rate-limits
                coordinator.advance_key_round_robin()
        except Exception as e:
            logger.warning(f"[NewsSynthesizer] Gemini Pool unavailable: {e}")

        # 3. Fallback Strategy: Cloudflare Workers AI Account Pool (Zero API cost, High Reliability)
        cf_accounts = self.cf_coordinator.get_accounts()
        if cf_accounts:
            models_to_try = [
                "@cf/meta/llama-3.1-70b-instruct",
                "@cf/meta/llama-3.1-8b-instruct",
                "@cf/meta/llama-3.2-3b-instruct",
            ]
            for aid, tok in cf_accounts:
                for cf_model in models_to_try:
                    url = f"https://api.cloudflare.com/client/v4/accounts/{aid}/ai/run/{cf_model}"
                    headers = {
                        "Authorization": f"Bearer {tok}",
                        "Content-Type": "application/json",
                    }
                    payload = {
                        "messages": [
                            {"role": "system", "content": "You are a professional financial news editor. Respond strictly with valid JSON only."},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 2048,
                        "temperature": 0.2,
                    }
                    try:
                        resp = requests.post(url, headers=headers, json=payload, timeout=45)
                        if resp.status_code == 200:
                            raw_reply = resp.json().get("result", {}).get("response", "")
                            parsed = self._clean_and_parse_json(raw_reply)
                            if parsed and parsed.get("headline"):
                                print(f"[NewsSynthesizer] Successfully synthesized news via Cloudflare AI ({cf_model})!")
                                return parsed
                    except Exception as cf_err:
                        logger.warning(f"[NewsSynthesizer] Cloudflare model {cf_model} attempt error: {cf_err}")
                        continue

        print("[NewsSynthesizer] Error: All AI synthesis providers failed or are unconfigured.")
        return None

    def _clean_and_parse_json(self, content: str) -> Optional[Dict]:
        """Cleans markdown wrappers and sanitizes text to extract valid JSON."""
        if not content:
            return None
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # Find first '{' and last '}'
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end + 1]

        try:
            return json.loads(text)
        except Exception:
            return None
