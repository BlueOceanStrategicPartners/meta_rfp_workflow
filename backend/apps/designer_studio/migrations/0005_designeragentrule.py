from django.conf import settings
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("designer_studio", "0004_designermediaasset_venue_map"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DesignerAgentRule",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("body", models.TextField()),
                ("embedding_json", models.JSONField(blank=True, default=list)),
                ("search_tokens_json", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "designer",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="designer_agent_rules",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["sort_order", "created_at"],
            },
        ),
    ]
