# Manually created - adds new About-page and Policy-page section types

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0022_startupsubmission_business_model'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pagesection',
            name='section_type',
            field=models.CharField(
                choices=[
                    ('hero', 'Hero Section'),
                    ('banner', 'Hero Banner'),
                    ('featured_stories', 'Featured Stories'),
                    ('latest_stories', 'Latest Stories'),
                    ('category_grid', 'Category Grid'),
                    ('city_grid', 'City Grid (Top Cities)'),
                    ('rising_hubs', 'Rising Startup Hubs (Tier 2/3)'),
                    ('startup_cards', 'Startup Cards'),
                    ('featured_startups', 'Featured Startups'),
                    ('cta', 'Call to Action'),
                    ('newsletter', 'Newsletter Section'),
                    ('custom_content', 'Custom Content Block'),
                    ('icons', 'Icons Grid'),
                    ('testimonials', 'Testimonials'),
                    ('footer_content', 'Footer Content'),
                    ('text_block', 'Text Block'),
                    ('text', 'Text Content'),
                    ('image', 'Image Block'),
                    ('video', 'Video Block'),
                    # About page types
                    ('mission_vision', 'Mission & Vision Cards'),
                    ('stats_bar', 'Statistics Bar'),
                    ('team_grid', 'Team Grid'),
                    ('values_grid', 'Values Grid'),
                    # Policy / content page types
                    ('policy_section', 'Policy Text Section'),
                    ('faq', 'FAQ Accordion'),
                    ('callout', 'Callout / Highlight Box'),
                    ('related_cards', 'Related Content Cards'),
                    ('image_gallery', 'Image Gallery'),
                    ('table_of_contents', 'Table of Contents'),
                ],
                max_length=50,
            ),
        ),
    ]
