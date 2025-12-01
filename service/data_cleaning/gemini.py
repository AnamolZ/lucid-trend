import json

def extract(raw, model):
    prompt = f"""
        You are an information extraction engine.
        
        Extract news/article data from the raw text.
        Output ONLY valid JSON:
        
        [
          {{
            "id": "string",
            "category": ["string","string"],
            "title": "string",
            "description": "string",
            "content": "string"
          }}
        ]
        
        Never include text outside JSON.
        
        Raw Input:
        {raw}
    """

    response = model.generate_content(
        prompt,
        generation_config={
            "response_mime_type": "application/json"
        }
    )

    return json.loads(response.text)

def detect_duplicates(posts, model):
    input_text = json.dumps(posts, ensure_ascii=False)
    
    prompt = f"""
        You are a content analysis engine.
        
        Given a list of news posts with 'id', 'title', and 'description', identify posts that are duplicates (even if the title or description differs slightly). 
        Output ONLY a JSON array of duplicate IDs.
        
        Input:
        {input_text}
    """
    
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    
    return json.loads(response.text)

def email_title(model):
    prompt = """
        You are a professional copywriter creating daily email titles for a tech newsletter.
        Generate **one highly engaging, concise, and professional email subject line** summarizing the latest technology news from the past 24 hours.
        Keep it general and trend-focused; do NOT mention specific categories, products, or technologies.
        Make it click-worthy and optionally use a simple emoji like 🔥, 🚀, or 💡.
        Example style: 'Tech's Rapid Evolution: Read today's latest news.'
        Output only the title as plain text, no quotes, JSON, or extra text.
    """

    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "text/plain"}
    )

    return response.text.strip()

def build_content_with_gemini(news_json, model):
    prompt = """
        You are generating professional newsletter content for a daily technology briefing.
        Extract only the most important and relevant points from the provided JSON.
        Produce clean HTML blocks with:
        <h2>Headline</h2>
        <p>3–5 sentence professional summary focusing on what happened, why it matters, and its industry impact.</p>
        Tone must be clear, objective, and editorial. No emojis or hype.
        Return only HTML blocks.
    """

    response = model.generate_content(
        prompt + "\n\nNews JSON:\n" + json.dumps(news_json)
    )
    return response.text.strip()

def image_suggestion(model, content):
    prompt = f"""
        Based strictly on the article content, extract the most accurate, 
        visually-representative concept and express it as exactly two words.

        Requirements:
        - Output must be exactly 2 words (e.g., "AI Agent", "Cybersecurity Breach", "Space Launch").
        - Words must clearly represent the main visual idea in the article.
        - No generic or vague nouns (e.g., "Agent", "System", "Thing").
        - No more than 2 words. No punctuation. No numbers.
        - No sentences, no lists, no explanations.

        Article Content:
        "{content}"

        Respond with exactly two words only.
    """
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "text/plain"}
    )
    keyword = response.text.strip()
    print(keyword)
    return keyword