import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from cms.models import AIPrompt

count = AIPrompt.objects.count()
with open('db_check.txt', 'w', encoding='ascii') as f:
    f.write(f"AIPrompt count: {count}\n")
    if count > 0:
        for p in AIPrompt.objects.all():
            f.write(f"- {p.name} (active: {p.is_active})\n")
