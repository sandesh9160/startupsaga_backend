import os
import json
from google import genai
from django.conf import settings

def _get_client():
    """Returns a configured genai Client."""
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return None
    return genai.Client(api_key=api_key)

def _get_model_name():
    """
    Pick a Gemini model name with fallback options.
    The google-genai SDK expects 'models/' prefix.
    """
    primary = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    fallback_env = os.getenv("GEMINI_MODEL_FALLBACKS", "gemini-2.5-flash,gemini-2.5-pro")
    candidates = [m.strip() for m in ([primary] + fallback_env.split(",")) if m.strip()]
    
    name = candidates[0] if candidates else "gemini-2.0-flash"
    # The google-genai Client SDK requires 'models/' prefix
    if not name.startswith("models/"):
        name = f"models/{name}"
    return name

def generate_seo_suggestions(content_data):
    """
    Generates SEO suggestions using Google Gemini.
    """
    client = _get_client()
    if not client:
        return {"error": "AI service is not configured."}

    model_name = _get_model_name()

    # Try to use saved prompt if available
    from .models import AIPrompt
    try:
        saved_prompt = AIPrompt.objects.get(name="Global SEO Generator", is_active=True)
        prompt = saved_prompt.prompt_text
        prompt = prompt.replace("{type}", str(content_data.get('type', 'page')))
        prompt = prompt.replace("{title}", str(content_data.get('title', '')))
        prompt = prompt.replace("{description}", str(content_data.get('description', '')))
        prompt = prompt.replace("{content}", str(content_data.get('content', '')[:1000]))
    except AIPrompt.DoesNotExist:
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
        
        # Enforce limits strictly
        if 'meta_description' in data and len(data['meta_description']) > 160:
            data['meta_description'] = data['meta_description'][:160]
            
        return data
    except Exception as e:
        return {"error": str(e)}

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
                return json.loads(text[start:end])
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
