import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from cms.models import Story
try:
    s = Story.objects.get(slug='ai-startups-india-raise-record-2b-2025')
    print(f'FOUND: {s.title}')
    print(f'THUMBNAIL: {s.thumbnail.url if s.thumbnail else "None"}')
    print(f'OG: {s.og_image.url if s.og_image else "None"}')
except Exception as e:
    print(f'ERROR: {e}')
    print('STORIES:')
    for story in Story.objects.all():
        print(f'- {story.slug}')
