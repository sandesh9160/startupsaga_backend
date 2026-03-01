
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from cms.models import Startup

startups = Startup.objects.all()
with open('missing_logos.txt', 'w') as f:
    for s in startups:
        if s.logo:
            f.write(f"{s.name}: {s.logo.name}\n")
        else:
            f.write(f"{s.name}: NO LOGO\n")
