from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0006_story_sections"),
    ]

    operations = [
        migrations.AddField(
            model_name="story",
            name="stage",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="story",
            name="view_count",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="story",
            name="trending_score",
            field=models.FloatField(default=0.0),
        ),
    ]
