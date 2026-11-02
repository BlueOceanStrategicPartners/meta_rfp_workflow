from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("designer_studio", "0006_remove_designermediaasset_venue_map"),
        ("inventory", "0002_map_studio_fields"),
    ]

    operations = [
        migrations.DeleteModel(
            name="VenueMapZone",
        ),
        migrations.DeleteModel(
            name="InteractiveVenueMap",
        ),
    ]
