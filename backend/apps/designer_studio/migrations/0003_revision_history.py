import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("designer_studio", "0002_js_script_designermediaasset"),
    ]

    operations = [
        migrations.AddField(
            model_name="proposaltemplate",
            name="revision_history_json",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
