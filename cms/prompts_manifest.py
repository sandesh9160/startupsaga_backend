
# Centralized location for all system AI prompts.
# This serves as the single source of truth for default templates.

SYSTEM_PROMPTS = [
    {
        "name": "Story Content Generator",
        "category": "story_write",
        "prompt_text": "Write an inspiring 800-word startup success story for: {title}. Include sections: The Problem, The Solution, Founder Journey, and Revenue Model. Use professional editorial tone.",
        "is_active": True
    },
    {
        "name": "Story SEO Generator",
        "category": "seo_gen",
        "prompt_text": 'Generate a compiled SEO meta title and meta description for a startup story titled "{title}".\nContent Snippet: {content}\n\nReturn strictly a JSON object with keys: "meta_title" and "meta_description".',
        "is_active": True
    },
    {
        "name": "Story Alt Text Generator",
        "category": "desc_gen",
        "prompt_text": 'Write a concise, descriptive alt text (max 15 words) for a cover image of a startup story titled "{title}". Focus on the subject matter or business context. Do not include "image of".',
        "is_active": True
    },
    {
        "name": "Slug Generator",
        "category": "general",
        "prompt_text": 'Generate a short, SEO-friendly URL slug (lowercase, hyphens only, max 5 words) for this title: "{title}". Return ONLY the slug, nothing else.',
        "is_active": True
    },
    {
        "name": "City SEO Generator",
        "category": "seo_gen",
        "prompt_text": 'Generate SEO metadata for a startup hub page for the city: {title}.\nDescription: {description}.\n\nReturn strictly a JSON object with keys: meta_title, meta_description, keywords.',
        "is_active": True
    },
    {
        "name": "City Description",
        "category": "desc_gen",
        "prompt_text": "Rewrite and enhance this city description for a startup ecosystem portal: {name}.\nCurrent description: {description}\n\nMake it professional, engaging, and highlight why it's a great place for startups. Use about 150-200 words.",
        "is_active": True
    },
    {
        "name": "City Alt Text",
        "category": "desc_gen",
        "prompt_text": 'Write a professional alt text for a cover image representing the startup ecosystem of {name}. Focus on the city skyline or innovation vibe. Max 15 words.',
        "is_active": True
    },
    {
        "name": "Global SEO Generator",
        "category": "seo_gen",
        "prompt_text": 'Act as an SEO Expert. Analyze the following content for a {type} named "{title}".\nDescription: {description}\nContent Snippet: {content}\n\nGenerate SEO Metadata in valid JSON format with these exact keys: meta_title, meta_description, keywords, image_alt, og_title, og_description.\n\nThe meta_description MUST BE EXACTLY 160 characters OR LESS. Do not include markdown formatting.',
        "is_active": True
    }
]
