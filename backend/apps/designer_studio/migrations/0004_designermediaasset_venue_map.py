from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0002_map_studio_fields"),
        ("designer_studio", "0003_revision_history"),
    ]

    operations = [
        migrations.AddField(
            model_name="designermediaasset",
            name="venue_map",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="media_assets",
                to="inventory.interactivevenuemap",
            ),
        ),
    ]
