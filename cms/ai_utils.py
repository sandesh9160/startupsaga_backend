import os
import json
import re
from collections import Counter
from google import genai
from django.conf import settings
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

def _get_client():
    """Returns a configured genai Client."""
    api_key = getattr(settings, 'GEMINI_API_KEY', None) or os.getenv('GEMINI_API_KEY')
    if not api_key:
        return None
    return genai.Client(api_key=api_key)

def _get_model_name():
    """
    Pick a Gemini model name with fallback options.
    """
    primary = getattr(settings, 'GEMINI_MODEL', None) or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    fallback_env = os.getenv("GEMINI_MODEL_FALLBACKS", "gemini-2.0-flash,gemini-flash-latest,gemini-1.5-flash")
    candidates = [m.strip() for m in ([primary] + fallback_env.split(",")) if m.strip()]
    
    # We'll return the first candidate for now. The new SDK doesn't have 
    # the same 'GenerativeModel' instantiation check as the old one.
    return candidates[0] if candidates else "gemini-2.0-flash"


_STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "for", "of", "to", "in", "on",
    "at", "by", "with", "from", "into", "about", "over", "after", "before", "under", "between",
    "is", "are", "was", "were", "be", "been", "being", "as", "it", "its", "this", "that", "these",
    "those", "their", "there", "here", "your", "our", "his", "her", "they", "them", "you", "we",
    "can", "could", "should", "would", "may", "might", "will", "than", "such", "also", "more",
    "most", "very", "using", "used", "use", "through", "across", "into", "india", "startupsaga"
}


def _clean_text(value):
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clip_text(text, limit):
    return text if len(text) <= limit else text[: limit - 1].rstrip(" ,.-") + "…"


def _normalize_keywords(value):
    if isinstance(value, list):
        raw = value
    else:
        raw = re.split(r",|\n", str(value or ""))

    seen = set()
    keywords = []
    for item in raw:
        cleaned = re.sub(r"\s+", " ", str(item).strip(" ,"))
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        keywords.append(cleaned)
    return keywords


def _extract_topic_keywords(title, description, content, page_type):
    title = _clean_text(title)
    description = _clean_text(description)
    content = _clean_text(content)
    combined = f"{title} {description} {content}".lower()

    words = re.findall(r"[a-zA-Z][a-zA-Z0-9+&-]{2,}", combined)
    counts = Counter(word for word in words if word not in _STOP_WORDS and not word.isdigit())

    type_labels = {
        "startup": ["startup", "startup profile", "indian startup", "startup story"],
        "story": ["startup story", "founder journey", "startup news"],
        "submission": ["startup submission", "founder story", "startup profile"],
        "hub": ["startup hub", "city startup ecosystem", "startup city"],
        "city": ["startup hub", "city startup ecosystem", "startup city"],
        "category": ["startup category", "industry startups", "startup ecosystem"],
        "page": ["startup ecosystem", "startup stories", "indian startups"],
    }

    phrases = []
    if title:
        phrases.append(title)

    title_parts = [part.strip() for part in re.split(r"[:|\-,/()]+", title) if part.strip()]
    phrases.extend(title_parts[:3])

    keyword_map = {
        "saas": "SaaS startups",
        "fintech": "Fintech startups",
        "healthtech": "Healthtech startups",
        "edtech": "Edtech startups",
        "ai": "AI startups",
        "deeptech": "Deeptech startups",
        "marketplace": "Marketplace startups",
        "b2b": "B2B startups",
        "b2c": "B2C startups",
        "d2c": "D2C startups",
        "logistics": "Logistics startups",
        "ecommerce": "E-commerce startups",
        "spacetech": "SpaceTech startups",
        "satellite": "Satellite startups",
    }

    for word, _count in counts.most_common(10):
        if word in keyword_map:
            phrases.append(keyword_map[word])
        elif len(word) > 3:
            phrases.append(word.title())

    phrases.extend(type_labels.get(page_type, type_labels["page"]))
    return _normalize_keywords(phrases)[:10]


def _build_fallback_seo(content_data):
    page_type = (content_data.get("type") or "page").lower()
    title = _clean_text(content_data.get("title"))
    description = _clean_text(content_data.get("description"))
    content = _clean_text(content_data.get("content"))

    description_source = description or content or title

    title_templates = {
        "startup": f"{title} | Startup Profile",
        "story": f"{title} | Startup Story",
        "submission": f"{title} | Startup Submission",
        "hub": f"Startups in {title}",
        "city": f"Startups in {title}",
        "category": f"{title} Startups",
        "page": title,
    }

    desc_templates = {
        "startup": f"Explore {title}, its founder journey, business model, growth story, and startup profile in the Indian startup ecosystem.",
        "story": f"Read the story behind {title}, including founder insights, business milestones, and startup lessons.",
        "submission": f"Review {title}, its founder background, startup journey, and business details.",
        "hub": f"Discover startups, founder stories, and ecosystem insights from {title}, one of India’s growing startup hubs.",
        "city": f"Discover startups, founder stories, and ecosystem insights from {title}, one of India’s growing startup hubs.",
        "category": f"Explore {title} startups, founder stories, funding updates, and ecosystem insights from India.",
        "page": description_source or title,
    }

    meta_title = _clip_text(title_templates.get(page_type, title or "StartupSaga.in"), 60)
    meta_description = _clip_text(desc_templates.get(page_type, description_source or title), 160)
    meta_keywords_list = _extract_topic_keywords(title, description, content, page_type)

    return {
        "meta_title": meta_title,
        "meta_description": meta_description,
        "meta_keywords": ", ".join(meta_keywords_list),
        "keywords": ", ".join(meta_keywords_list),
        "image_alt": _clip_text(f"{title} featured image", 100) if title else "Featured image",
        "og_title": meta_title,
        "og_description": meta_description,
    }


def _normalize_seo_payload(data, content_data):
    fallback = _build_fallback_seo(content_data)
    payload = data if isinstance(data, dict) else {}

    meta_title = _clean_text(payload.get("meta_title") or payload.get("title") or fallback["meta_title"])
    meta_description = _clean_text(payload.get("meta_description") or payload.get("description") or fallback["meta_description"])
    meta_keywords = payload.get("meta_keywords") or payload.get("keywords") or fallback["meta_keywords"]
    image_alt = _clean_text(payload.get("image_alt") or fallback["image_alt"])
    og_title = _clean_text(payload.get("og_title") or meta_title)
    og_description = _clean_text(payload.get("og_description") or meta_description)

    keywords_list = _normalize_keywords(meta_keywords)
    if not keywords_list:
        keywords_list = _normalize_keywords(fallback["meta_keywords"])

    return {
        "meta_title": _clip_text(meta_title or fallback["meta_title"], 60),
        "meta_description": _clip_text(meta_description or fallback["meta_description"], 160),
        "meta_keywords": ", ".join(keywords_list[:10]),
        "keywords": ", ".join(keywords_list[:10]),
        "image_alt": _clip_text(image_alt or fallback["image_alt"], 100),
        "og_title": _clip_text(og_title or fallback["meta_title"], 60),
        "og_description": _clip_text(og_description or fallback["meta_description"], 160),
    }

def generate_seo_suggestions(content_data):
    """
    Generates SEO suggestions using Google Gemini.
    """
    client = _get_client()
    if not client:
        return _build_fallback_seo(content_data)

    model_name = _get_model_name()

    prompt = f"""
    Act as an SEO Expert. Analyze the following content for a {content_data.get('type', 'page')} named "{content_data.get('title')}".
    Description: {content_data.get('description')}
    Content Snippet: {content_data.get('content', '')[:1000]}...

    Generate SEO Metadata in valid JSON format with these exact keys:
    - meta_title (max 60 chars)
    - meta_description (MUST BE EXACTLY 160 characters OR LESS. Do not exceed this limit.)
    - keywords (comma separated)
    - image_alt (max 100 chars, descriptive but concise alt text for the featured image)
    - og_title
    - og_description
    
    Do not include markdown formatting like ```json ... ```. Just return the raw JSON string.
    """
    try:
        response = client.models.generate_content(model=model_name, contents=prompt)
        text = response.text
        
        # Clean up if model returns markdown code block
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()
        
        data = json.loads(text)
        return _normalize_seo_payload(data, content_data)
    except Exception as e:
        fallback = _build_fallback_seo(content_data)
        fallback["warning"] = str(e)
        return fallback

def generate_ai_content(prompt_name, context_data):
    """
    Generates content based on a saved AIPrompt and context.
    """
    from .models import AIPrompt
    
    client = _get_client()
    if not client:
        return {"error": "AI service is not configured."}

    try:
        saved_prompt = AIPrompt.objects.get(name=prompt_name, is_active=True)
        full_prompt = saved_prompt.prompt_text
        
        # Simple string formatting if context is provided
        if context_data:
            for key, val in context_data.items():
                full_prompt = full_prompt.replace(f"{{{{{key}}}}}", str(val))
                full_prompt = full_prompt.replace(f"{{{key}}}", str(val))
        
        response = client.models.generate_content(model=_get_model_name(), contents=full_prompt)
        return {"content": response.text}
    except AIPrompt.DoesNotExist:
        if " " in prompt_name:
             response = client.models.generate_content(model=_get_model_name(), contents=prompt_name)
             return {"content": response.text}
        return {"error": f"AIPrompt '{prompt_name}' not found."}
    except Exception as e:
        return {"error": str(e)}

def generate_ai_content_direct(prompt_text):
    """
    Generates content directly from prompt text without using saved prompts.
    """
    client = _get_client()
    if not client:
        return {"error": "AI service is not configured."}
    
    try:
        response = client.models.generate_content(model=_get_model_name(), contents=prompt_text)
        return {"content": response.text}
    except Exception as e:
        return {"error": str(e)}

def CitySEOGenerator(name, description=""):
    """Backend version of City SEO Generator"""
    context = {"title": name, "description": description, "content": description, "type": "hub"}
    result = generate_ai_content("City SEO Generator", context)
    
    if "content" in result:
        try:
            text = result["content"]
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end != 0:
                return _normalize_seo_payload(json.loads(text[start:end]), context)
        except:
            pass

    return generate_seo_suggestions(context)

def CityDescription(name, current_description=""):
    """Backend version of City Description Rewriter"""
    context = {"name": name, "description": current_description or "No description provided."}
    result = generate_ai_content("City Description", context)
    return result.get("content")

def CityAltText(name):
    """Backend version of City Alt Text Generator"""
    context = {"name": name}
    result = generate_ai_content("City Alt Text", context)
    content = result.get("content", "")
    if content:
        content = content.strip().strip('"').strip("'")
    return content
