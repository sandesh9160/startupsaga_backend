import io
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from cms.models import MediaItem

with io.open('media_debug.txt', 'w', encoding='utf-8') as f:
    count = MediaItem.objects.count()
    f.write(u'Count: {}\n'.format(count))
    for m in MediaItem.objects.all():
        f.write(u'ID: {} | Title: {} | URL: {}\n'.format(m.id, m.title, m.file.url if m.file else 'None'))
