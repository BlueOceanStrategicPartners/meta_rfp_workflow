from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="interactivevenuemap",
            name="html_markup",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="interactivevenuemap",
            name="css_stylesheet",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="interactivevenuemap",
            name="js_script",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="interactivevenuemap",
            name="chat_history_json",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="interactivevenuemap",
            name="revision_history_json",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="interactivevenuemap",
            name="is_default",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="interactivevenuemap",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="venue_maps_authored",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="interactivevenuemap",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
