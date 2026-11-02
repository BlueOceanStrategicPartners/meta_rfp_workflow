from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("designer_studio", "0006_remove_designermediaasset_venue_map"),
    ]

    operations = [
        migrations.AddField(
            model_name="proposaltemplate",
            name="langgraph_thread_id",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
        migrations.AddField(
            model_name="proposaltemplate",
            name="langgraph_checkpoint_id",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
    ]
