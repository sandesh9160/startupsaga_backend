import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from cms.models import Startup

try:
    startups = Startup.objects.filter(name__icontains='Ola')
    for startup in startups:
        print(f"Name: {startup.name}")
        print(f"Slug: {startup.slug}")
        print(f"Legacy founder_name: {startup.founder_name}")
        print(f"Founders Data (JSON): {startup.founders_data}")
        print(f"Related Founders Count: {startup.founders.count()}")
        for founder in startup.founders.all():
            print(f"- Founder: {founder.name}")
        print("-" * 20)
except Exception as e:
    print(f"Error: {str(e)}")
