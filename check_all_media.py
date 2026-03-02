
import os
import django
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.conf import settings
from cms.models import Category, City, Startup, Founder, Story, StartupSubmission, Page, PageSection

IMAGE_FIELDS = [
    (Category, ['icon', 'og_image']),
    (City, ['image', 'og_image']),
    (Startup, ['logo', 'og_image']),
    (Founder, ['photo']),
    (Story, ['thumbnail', 'og_image']),
    (StartupSubmission, ['logo', 'thumbnail']),
    (Page, ['og_image']),
    (PageSection, ['image', 'icon']),
]

media_root = Path(settings.MEDIA_ROOT)
missing = []

for Model, fields in IMAGE_FIELDS:
    for field_name in fields:
        qs = Model.objects.exclude(**{field_name: ''}).exclude(**{f'{field_name}__isnull': True})
        for obj in qs:
            field_value = getattr(obj, field_name)
            if field_value and field_value.name:
                full_path = media_root / field_value.name
                if not full_path.exists():
                    missing.append(f"{Model.__name__} (pk={obj.pk}) - {field_name}: {field_value.name}")

with open('all_missing_media.txt', 'w') as f:
    if not missing:
        f.write("No missing media found!")
    for m in missing:
        f.write(f"{m}\n")
