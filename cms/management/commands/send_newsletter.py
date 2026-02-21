import datetime
from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from django.conf import settings
from cms.models import Story, NewsletterSubscription, NewsletterTemplate

class Command(BaseCommand):
    help = 'Sends weekly newsletter to active subscribers'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Print counts without sending emails')
        parser.add_argument('--force', action='store_true', help='Send even if no new stories')

    def handle(self, *args, **options):
        # 0. Get active template
        template_config = NewsletterTemplate.objects.filter(is_active=True).first()

        # 1. Get stories from last 7 days
        last_week = timezone.now() - datetime.timedelta(days=7)
        stories = Story.objects.filter(
            status='published', 
            published_at__gte=last_week
        ).order_by('-published_at')[:5]

        if not stories.exists() and not options['force']:
            self.stdout.write(self.style.WARNING('No new stories in the last 7 days. Skipping newsletter.'))
            return

        # 2. Get active subscribers
        subscribers = NewsletterSubscription.objects.filter(is_active=True)
        count = subscribers.count()

        if count == 0:
            self.stdout.write(self.style.WARNING('No active subscribers found.'))
            return

        self.stdout.write(self.style.SUCCESS(f'Preparing to send newsletter to {count} subscribers...'))

        # 3. Prepare common context
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:3000')

        # 4. Iterative sending (avoids BCC limits and allows personalized unsub links)
        success_count = 0
        fail_count = 0

        # Template defaults if no config exists
        defaults = {
            'subject_format': "StartupSaga Weekly: {first_story_title}",
            'font_family': "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
            'header_title': "StartupSaga",
            'header_subtitle': "Weekly stories, founder insights, and ecosystem updates",
            'body_intro': "Top Stories This Week",
            'footer_text': "© {year} StartupSaga. All rights reserved.\nYou received this email because you subscribed to our newsletter.",
            'accent_color': "#ea580c",
            'logo_url': None
        }

        for sub in subscribers:
            try:
                unsubscribe_url = f"{site_url}/unsubscribe?email={sub.email}&token={sub.token}"
                
                # Merge config with defaults
                first_story_title = stories[0].title if stories else 'Fresh Stories'
                subject = (template_config.subject_format if template_config else defaults['subject_format']).replace('{first_story_title}', first_story_title)
                
                context = {
                    'stories': stories,
                    'site_url': site_url,
                    'unsubscribe_url': unsubscribe_url,
                    'year': datetime.datetime.now().year,
                    'subscriber_email': sub.email,
                    # Dynamic customizations
                    'logo_url': template_config.logo_url if template_config else defaults['logo_url'],
                    'font_family': template_config.font_family if template_config else defaults['font_family'],
                    'header_title': template_config.header_title if template_config else defaults['header_title'],
                    'header_subtitle': template_config.header_subtitle if template_config else defaults['header_subtitle'],
                    'body_intro': template_config.body_intro if template_config else defaults['body_intro'],
                    'footer_text': (template_config.footer_text if template_config else defaults['footer_text']).replace('{year}', str(datetime.datetime.now().year)),
                    'accent_color': template_config.accent_color if template_config else defaults['accent_color'],
                }

                html_content = render_to_string('cms/emails/weekly_newsletter.html', context)
                text_content = strip_tags(html_content)

                from_email = settings.DEFAULT_FROM_EMAIL
                
                if not options['dry_run']:
                    msg = EmailMultiAlternatives(subject, text_content, from_email, [sub.email])
                    msg.attach_alternative(html_content, "text/html")
                    msg.send()
                    
                    sub.last_sent_at = timezone.now()
                    sub.save()
                
                success_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to send to {sub.email}: {str(e)}'))
                fail_count += 1

        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS(f'Dry run complete. Would have sent {success_count} emails.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Newsletter sent successfully! Success: {success_count}, Failed: {fail_count}'))
