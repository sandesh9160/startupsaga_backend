"""
Management command to audit and fix broken media references in the database.

Usage:
    python manage.py audit_media              # Audit only (dry run)
    python manage.py audit_media --fix        # Fix extension mismatches & clear missing refs
    python manage.py audit_media --fix-ext    # Only fix extension mismatches
    python manage.py audit_media --clear      # Only clear references to missing files
"""
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from cms.models import Category, City, Startup, Founder, Story, StartupSubmission, Page, PageSection, MediaItem


# All models and their ImageField names
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

# MediaItem uses FileField, not ImageField
FILE_FIELDS = [
    (MediaItem, ['file']),
]

# Common image extensions to try as alternatives
IMAGE_EXTENSIONS = ['.jpeg', '.jpg', '.png', '.webp', '.gif', '.svg', '.bmp', '.ico']


class Command(BaseCommand):
    help = 'Audit and fix broken media/image references stored in the database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix', action='store_true',
            help='Fix extension mismatches AND clear references to truly missing files.',
        )
        parser.add_argument(
            '--fix-ext', action='store_true',
            help='Only fix extension mismatches (rename DB path to match the file on disk).',
        )
        parser.add_argument(
            '--clear', action='store_true',
            help='Only clear DB references for truly missing files (set field to empty).',
        )

    def handle(self, *args, **options):
        fix_all = options['fix']
        fix_ext = options['fix_ext'] or fix_all
        clear_missing = options['clear'] or fix_all

        media_root = Path(settings.MEDIA_ROOT)
        self.stdout.write(self.style.NOTICE(f'\nMedia root: {media_root}\n'))

        total_checked = 0
        ok_count = 0
        missing_count = 0
        ext_mismatch_count = 0
        fixed_ext_count = 0
        cleared_count = 0

        all_fields = IMAGE_FIELDS + FILE_FIELDS

        for Model, fields in all_fields:
            model_name = Model.__name__
            for field_name in fields:
                # Build queryset: only rows where the field is not blank/null
                qs = Model.objects.exclude(**{field_name: ''}).exclude(**{f'{field_name}__isnull': True})
                for obj in qs:
                    field_value = getattr(obj, field_name)
                    if not field_value or not field_value.name:
                        continue

                    total_checked += 1
                    relative_path = field_value.name  # e.g. 'cities/images/pune.webp'
                    full_path = media_root / relative_path

                    if full_path.exists():
                        ok_count += 1
                        continue

                    # File doesn't exist – check for extension mismatch
                    stem = full_path.stem
                    parent = full_path.parent
                    alternative_found = None

                    for ext in IMAGE_EXTENSIONS:
                        candidate = parent / f'{stem}{ext}'
                        if candidate.exists():
                            alternative_found = candidate
                            break

                    if alternative_found:
                        ext_mismatch_count += 1
                        # Build new relative path
                        new_relative = str(alternative_found.relative_to(media_root)).replace('\\', '/')
                        self.stdout.write(
                            self.style.WARNING(
                                f'  EXT MISMATCH  {model_name}(pk={obj.pk}).{field_name}: '
                                f'{relative_path} → found as {alternative_found.name}'
                            )
                        )
                        if fix_ext:
                            field_value.name = new_relative
                            obj.save(update_fields=[field_name])
                            fixed_ext_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(f'    ✓ Fixed → {new_relative}')
                            )
                    else:
                        missing_count += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f'  MISSING       {model_name}(pk={obj.pk}).{field_name}: {relative_path}'
                            )
                        )
                        if clear_missing:
                            field_value.name = ''
                            obj.save(update_fields=[field_name])
                            cleared_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(f'    ✓ Cleared (set to empty)')
                            )

        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.NOTICE('  MEDIA AUDIT SUMMARY'))
        self.stdout.write('=' * 60)
        self.stdout.write(f'  Total image references checked : {total_checked}')
        self.stdout.write(self.style.SUCCESS(f'  OK (file exists)               : {ok_count}'))
        self.stdout.write(self.style.WARNING(f'  Extension mismatches           : {ext_mismatch_count}'))
        self.stdout.write(self.style.ERROR(f'  Truly missing files            : {missing_count}'))

        if fix_ext or clear_missing:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(f'  Fixed ext mismatches           : {fixed_ext_count}'))
            self.stdout.write(self.style.SUCCESS(f'  Cleared missing refs           : {cleared_count}'))
        else:
            self.stdout.write('')
            self.stdout.write(self.style.NOTICE(
                '  Run with --fix to auto-fix extension mismatches and clear missing refs.\n'
                '  Or use --fix-ext / --clear for granular control.'
            ))

        self.stdout.write('=' * 60 + '\n')
