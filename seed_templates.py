from cms.models import NewsletterTemplate
import django
import os

# Clean up existing default if it's the only one
count = NewsletterTemplate.objects.count()
if count <= 1:
    NewsletterTemplate.objects.all().delete()

# Template 1: Weekly Digest
NewsletterTemplate.objects.get_or_create(
    name='Weekly Digest',
    defaults={
        'subject_format': 'StartupSaga Weekly: {first_story_title}',
        'header_title': 'StartupSaga',
        'header_subtitle': 'The pulse of the startup ecosystem delivered to your inbox.',
        'body_intro': 'Top Stories This Week',
        'body_text': '<p>Hello entrepreneurs!</p><p>We have curated the most impactful stories from the past week to keep you informed and inspired. From funding rounds to founder pivots, here is what is happening in the ecosystem.</p>',
        'accent_color': '#ea580c',
        'is_active': True,
        'font_family': "'Inter', sans-serif"
    }
)

# Template 2: Founder Spotlight
NewsletterTemplate.objects.get_or_create(
    name='Founder Spotlight',
    defaults={
        'subject_format': 'Founder Spotlight: {first_story_title}',
        'header_title': 'Founder Stories',
        'header_subtitle': 'Deep dives into the minds of those building the future.',
        'body_intro': 'Featured Founder',
        'body_text': '<p>Every great startup starts with a person and a problem. This week, we are looking at how persistence turned a failing side project into a global platform.</p>',
        'accent_color': '#9333ea',
        'is_active': False,
        'font_family': "'Montserrat', sans-serif"
    }
)

# Template 3: Ecosystem Update
NewsletterTemplate.objects.get_or_create(
    name='Ecosystem Update',
    defaults={
        'subject_format': 'Ecosystem Alert: {first_story_title}',
        'header_title': 'Ecosystem Pulse',
        'header_subtitle': 'Regulatory changes, funding trends, and market shifts.',
        'body_intro': 'Market Intelligence',
        'body_text': '<p>Stay ahead of the curve with our analysis of the latest trends. We break down the data so you can focus on building.</p>',
        'accent_color': '#2563eb',
        'is_active': False,
        'font_family': "'Roboto', sans-serif"
    }
)

print('3 Professional templates created successfully.')
