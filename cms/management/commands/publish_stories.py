from django.core.management.base import BaseCommand
from cms.models import Story

class Command(BaseCommand):
    help = 'Publish all draft stories'

    def handle(self, *args, **options):
        for s in Story.objects.all():
            self.stdout.write(f"  {s.title} | status={s.status}")
        updated = Story.objects.exclude(status='published').update(status='published')
        self.stdout.write(self.style.SUCCESS(f"\nPublished {updated} stories."))
