from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0032_newslettertemplate_admin_body_intro_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name='startup',
                    name='content',
                    field=models.TextField(blank=True, default=''),
                ),
            ],
        ),
    ]
