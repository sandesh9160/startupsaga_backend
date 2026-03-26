from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0033_startup_content_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='startupsubmission',
            name='founded_year',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='startupsubmission',
            name='team_size',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='startupsubmission',
            name='sector',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='startupsubmission',
            name='industry_tags',
            field=models.JSONField(blank=True, help_text='List of industry tag strings', null=True),
        ),
        migrations.AddField(
            model_name='startupsubmission',
            name='founders_data',
            field=models.JSONField(blank=True, help_text='List of founders: [{"name": "...", "role": "...", "linkedin": "..."}]', null=True),
        ),
    ]
