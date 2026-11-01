import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("designer_studio", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="proposaltemplate",
            name="js_script",
            field=models.TextField(blank=True),
        ),
        migrations.CreateModel(
            name="DesignerMediaAsset",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("file", models.FileField(upload_to="designer_assets/%Y/%m/")),
                ("original_name", models.CharField(max_length=512)),
                ("content_type", models.CharField(blank=True, max_length=128)),
                ("file_size", models.PositiveIntegerField(default=0)),
                (
                    "media_type",
                    models.CharField(
                        choices=[("IMAGE", "Image"), ("VIDEO", "Video")], max_length=16
                    ),
                ),
                ("width", models.PositiveIntegerField(blank=True, null=True)),
                ("height", models.PositiveIntegerField(blank=True, null=True)),
                ("metadata_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "designer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="designer_media_assets",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="media_assets",
                        to="designer_studio.proposaltemplate",
                    ),
                ),
            ],
        ),
    ]
