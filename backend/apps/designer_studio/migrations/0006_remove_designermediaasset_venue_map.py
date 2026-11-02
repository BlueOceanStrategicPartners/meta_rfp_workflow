from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("designer_studio", "0005_designeragentrule"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="designermediaasset",
            name="venue_map",
        ),
    ]
